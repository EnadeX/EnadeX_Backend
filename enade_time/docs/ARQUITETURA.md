# Arquitetura — ENADE-Time Distribuído

## Visão geral em camadas

```
┌─────────────────────────────────────────────────────────────────────────┐
│  6. Dashboard React/Vite          (frontend)                            │
│     ├─ React Router · TanStack Query · Axios · Recharts · Tailwind      │
│     └─ Consome HTTP → http://localhost:8000                             │
├─────────────────────────────────────────────────────────────────────────┤
│  5. API FastAPI read-only         (api/)                                │
│     ├─ FastAPI + Pydantic v2 + psycopg2.ThreadedConnectionPool          │
│     └─ Routers: health, dim, analises, benchmark                        │
├─────────────────────────────────────────────────────────────────────────┤
│  4. Banco PostgreSQL 16           (Docker — enade_postgres)             │
│     ├─ Tabelas dim_* · fato_enade · benchmark_execucao · benchmark_etapa│
│     └─ View v_benchmark_metricas (speedup, eficiência, throughput)      │
├─────────────────────────────────────────────────────────────────────────┤
│  3. Benchmark sequencial/paralelo (scripts/08, 09, 10 + etl/)           │
│     └─ multiprocessing.Pool · psutil · grava em benchmark_execucao      │
├─────────────────────────────────────────────────────────────────────────┤
│  2. ETL e carga                   (scripts/02, 03, 05, 06)              │
│     ├─ pandas: filtro/consolidação · psycopg2: COPY FROM STDIN          │
│     └─ Gera dados_processados/*.csv                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Dados brutos                  (microdados_enade_*/)                 │
│     └─ Arquivos TXT oficiais do INEP (LGPD) — somente leitura           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Fluxo de dados

```
microdados_enade_*/  ──►  scripts/ ETL  ──►  dados_processados/  ──►  PostgreSQL
       (TXT INEP)        (02, 03, …)         (CSV consolidado)        (COPY FROM)
                                                                           │
                                                                           ▼
                                                                       FastAPI
                                                                           │
                                                                           ▼
                                                                   React Dashboard
```

1. **Microdados brutos** (TXT/CSV LGPD do INEP) ficam em
   `microdados_enade_*\` — **nunca são alterados**.
2. **Scripts ETL** (02 e 03) leem, filtram e consolidam em
   `dados_processados\microdados_enade_2005_2021_filtrado_consolidado.csv`.
3. **Scripts 05 e 06** criam o schema dimensional e carregam o CSV no
   PostgreSQL via `COPY FROM STDIN`.
4. **Scripts 08, 09, 10** rodam o experimento de paralelismo e gravam
   resultados em `benchmark_execucao` / `benchmark_etapa`. O 10 organiza
   uma **campanha** (aquecimento descartado + N suítes; em cada suíte um
   sequencial e as paralelas em duas ordens de submissão); o 09 escolhe a
   ordem (`--ordem crescente|lpt`) — o `ProcessPoolExecutor` entrega cada
   ano ao primeiro worker livre na ordem submetida. A instrumentação (CPU
   média, bytes lidos do disco, núcleos físicos/lógicos) roda só no processo
   principal; `etl/processar_ano.py` continua puro.
5. **API FastAPI** expõe endpoints read-only sobre as tabelas/views.
6. **Frontend React** consome a API e apresenta análises e gráficos.

## Modelo de dados

**Tabela fato:**
- `fato_enade` (24.967 linhas) — `id, nu_ano, co_curso, co_ies,
  co_categad, co_orgacad, co_grupo, co_modalidade, co_munic_curso,
  co_uf_curso, co_regiao_curso, media_nt_fg`.

**Dimensões (todas em singular):**
- `dim_regiao, dim_uf, dim_ano, dim_grupo, dim_modalidade,
  dim_categoria_adm, dim_organizacao_acad`.

**Benchmark (schema v2 — `scripts/14_migrar_schema_v2.py`, aditivo):**
- `benchmark_execucao` — uma linha por execução completa do ETL. Além de
  tempo/throughput/memória, guarda `campanha_id`, `suite_id`, `oficial`,
  `ordem_submissao` (`crescente` | `lpt`), `cpu_fisicos`, `cpu_logicos`,
  `cpu_percent_medio`, `disco_bytes_lidos`, `cache_quente`, `aquecimento`,
  `execucao_uid`.
- `benchmark_etapa` — uma linha por ano processado dentro de uma
  execução (permite drill-down por `worker_pid`).
- `v_benchmark_metricas` (view) — **definição única** de `speedup` e
  `eficiencia`: pareia cada execução paralela com o sequencial da **mesma
  suíte**; linhas antigas sem suíte usam o sequencial imediatamente anterior
  (`pareamento = 'temporal'`).
- `v_benchmark_resumo` (view) — mediana, mín, máx, IQR e `n` por
  (campanha, workers, ordem de submissão).
- `tbl_enade_time_publicacao` — log das publicações no Supabase.

Hierarquia: **campanha** (1 por `10 --oficial`) → **suíte** = repetição
(sequencial + paralelas pareadas) → **execução** → **etapa** (ano).

## Decisões técnicas

### Por que PostgreSQL?

- **Tipos numéricos nativos** (`NUMERIC`, `INTEGER`) e `CHECK` constraints
  preservam a integridade do score ENADE (0–100).
- **`COPY FROM STDIN`** carrega milhões de linhas em segundos — muito
  mais eficiente que `INSERT` linha a linha.
- **Views** (`v_benchmark_metricas`, `v_benchmark_resumo`) são a **única**
  definição das métricas de paralelismo. A API só lê as views; o Python
  recalcula a partir das tabelas apenas para **conferir**
  (`scripts/13_validar_metricas.py`, `tests/`). Essa inversão nasceu de um
  erro real: o endpoint de comparativo recalculava speedup contra "o
  sequencial mais recente" e, com duas rodadas no banco, inflou um resultado
  (DESIGN_LOG D13).
- **Docker** garante reprodutibilidade — o mesmo `docker-compose up -d`
  funciona em qualquer máquina.
- Alternativas consideradas:
  - **SQLite**: descartado porque o experimento de I/O paralelo precisa
    de um servidor real que aceite múltiplas conexões simultâneas dos
    workers.
  - **DuckDB**: ótimo para analítica, mas tira o protagonismo do
    componente "servidor de banco" que o currículo de SPD pede.

### Por que FastAPI (e não Flask/Django)?

- **Tipagem forte** com Pydantic v2 — schemas viram contrato HTTP e
  documentação OpenAPI automaticamente.
- **Swagger nativo** em `/docs` — útil para apresentação acadêmica.
- **Async-ready** (mesmo que neste projeto a API seja síncrona) — sem
  custo de mudar depois.
- **ThreadedConnectionPool** do psycopg2 lida bem com o modelo
  request-per-thread do FastAPI síncrono.
- Por que **sem ORM**: o domínio é tabular e read-only; SQLAlchemy
  adicionaria complexidade sem ganho. SQL explícito é mais auditável
  para um projeto acadêmico.

> **Atualização (12/10/2026):** o dashboard canônico é hoje o módulo
> `/enade-time` do `EnadeX_Frontend` (Next.js 16 + TanStack Query + Recharts), no
> repositório de frontend do grupo. A SPA React + Vite descrita abaixo foi a
> implementação original, validada no TCC, e permanece em `frontend/` como
> artefato. As justificativas a seguir valem para ela.

### Por que React + Vite?

- **Vite** entrega HMR rápido e build pequeno; sem a complexidade do
  Webpack/Next.
- **TypeScript** espelha os Pydantic schemas — toda mudança de campo
  vira erro de tipo no IDE, evitando regressões silenciosas.
- **TanStack Query** elimina o estado de servidor manual (loading,
  error, cache, retry) e mostra um único `QueryBoundary` em todas as
  páginas.
- **Recharts** é declarativo (composição React), suficiente para os
  gráficos científicos do dashboard (linha, barra, ranking).
- **SPA pura** (sem SSR) é apropriada para uma ferramenta interna —
  o servidor estático é o `npm run preview` ou um Nginx futuro.

### Por que separar `frontend/` e `api/`?

- **Independência de deploy** — em Fase 5 cada um receberá seu próprio
  Dockerfile, podendo escalar isoladamente.
- **Independência de stack** — atualizar pacote Python não força
  reinstalar Node, e vice-versa.
- **CORS explícito** — força declarar quem pode chamar a API
  (origins de localhost), padrão de produção.
- **Permite múltiplos clientes** — o mesmo backend poderia servir um
  app mobile ou um CLI no futuro sem refatoração.

### Por que preservar `microdados_enade_*\` brutos?

- **Reprodutibilidade científica**: qualquer revisor pode reexecutar o
  ETL e comparar os CSVs gerados com `dados_processados\`.
- **LGPD**: os arquivos do INEP já passam por anonimização — não é
  necessário rederivar para esconder dados.
- **Auditoria de filtros**: se o recorte mudar (ex.: incluir 2023), só
  basta ajustar o script 02 — os brutos continuam disponíveis.
- **Custo zero de manter**: o INEP nem sempre republica versões antigas
  com os mesmos identificadores; perder os brutos significa perder
  acesso ao recorte usado no experimento.

## Princípios atravessadores

- **Read-only do dado bruto**: nenhum script altera os TXT em
  `microdados_enade_*\`.
- **Read-only da API**: nenhum endpoint POST/PUT/DELETE — a Fase 3
  expõe apenas leitura.
- **Estado de servidor no banco, estado de cliente na URL**: filtros
  do dashboard ficam em query string (deep-link), nada de Redux global.
- **Tipos como contrato**: Pydantic do backend ↔ interfaces TS do
  frontend mantêm acoplamento estrito.
