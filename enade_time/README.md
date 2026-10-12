# ENADE-Time Distribuído

> **Dentro do ecossistema EnadeX** — este subprojeto vive em `enade_time/` e
> roda a partir da **raiz do EnadeX** com `PYTHONPATH=.` (mesmo padrão do
> educluster):
>
> ```powershell
> cd C:\Projetos\EnadeX
> $env:PYTHONPATH='.'
> pip install -r enade_time\requirements.txt
> cd enade_time; docker compose up -d postgres; cd ..
> python enade_time\scripts\07_validar_banco.py     # BASE VALIDADA
> python enade_time\enade_time_rotas.py               # API standalone na PORTA 8002
> #  → Swagger: http://localhost:8002/docs  (rotas sob /api/enade-time/*)
> ```
>
> Para o `api_main.py` central: `from enade_time.enade_time_rotas import router`
> (ver o docstring de `enade_time_rotas.py` sobre o ciclo de vida do pool).
> Os microdados brutos do INEP (3+ GB) ficam **fora** do repositório —
> ver `ENADE_TIME_MICRODADOS_DIR` em `.env.example`. Os caminhos
> `C:\Projetos\ENADE` citados abaixo referem-se ao repositório original
> ([lucasetculbra/enade-time-distribuido](https://github.com/lucasetculbra/enade-time-distribuido));
> dentro do EnadeX, prefixe os comandos com `enade_time\`.


**Sistema Paralelo de Análise Longitudinal dos Microdados do ENADE**

Projeto acadêmico da disciplina de **Sistemas Paralelos e Distribuídos (SPD)**.
Integra um pipeline ETL paralelo em Python sobre os microdados oficiais do
ENADE (INEP), com banco PostgreSQL, API FastAPI read-only e dashboard React
para visualização longitudinal e dos resultados do experimento de paralelismo.

> Diretório oficial do projeto: **`C:\Projetos\ENADE`**.
> A cópia antiga em OneDrive é apenas backup informal e **não deve** ser
> usada para execução (gera contenção de I/O nos benchmarks).

---

## Objetivo acadêmico

1. **Aplicar conceitos de paralelismo** (Lei de Amdahl, speedup, eficiência,
   throughput) a um cenário real de processamento de dados públicos.
2. **Construir um pipeline completo** — desde leitura dos arquivos brutos
   do INEP até um dashboard navegável — demonstrando integração entre
   camadas de dados, serviços HTTP e interface.
3. **Mensurar empiricamente** o ganho de paralelismo do ETL com diferentes
   números de workers, identificando o ponto ótimo no hardware disponível.

**Recorte do estudo:**
- Cursos de Computação: `CO_GRUPO ∈ {40, 4004}`. É o **mesmo curso** — o INEP
  mudou o código entre ciclos (40 em 2005/2008, 4004 de 2011 em diante), e o
  pipeline trata os dois como equivalentes. Detalhes em
  [`docs/DICIONARIO_VARIAVEIS.md`](docs/DICIONARIO_VARIAVEIS.md).
- Regiões: Norte e Nordeste (`CO_REGIAO_CURSO ∈ {1, 2}`).
- Edições do ENADE: 2005, 2008, 2011, 2014, 2017, 2021.
- Total consolidado em `fato_enade`: **24.967 registros** (inscrições) —
  **582 cursos-ano**, que é a unidade analítica (ver `docs/DICIONARIO_VARIAVEIS.md`).

---

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem do ETL/benchmark | Python 3.13 (`multiprocessing`, `pandas`, `psycopg2`, `psutil`) |
| Banco de dados | PostgreSQL 16 (Docker Compose) |
| Orquestração local | Docker Compose |
| API | FastAPI + Pydantic v2 + psycopg2 (ThreadedConnectionPool) |
| Dashboard (canônico) | Next.js 16 (App Router) + TypeScript — módulo `/enade-time` do `EnadeX_Frontend` |
| Dashboard (artefato do TCC) | SPA React 18 + TypeScript + Vite, em `frontend/` |
| Cache HTTP/estado | TanStack Query 5 |
| Gráficos | Recharts |
| Estilo | Tailwind CSS |
| Roteamento | React Router 6 |

---

## Estrutura de pastas

```
C:\Projetos\ENADE\
├── README.md                  ← este arquivo
├── docker-compose.yml         ← PostgreSQL 16 + serviço opcional da API
├── .env.example               ← template de variáveis do banco
├── docs/                      ← documentação acadêmica da Fase 5
│   ├── README.md
│   ├── GUIA_EXECUCAO.md
│   ├── ARQUITETURA.md
│   ├── RESULTADOS_BENCHMARK.md
│   ├── EVIDENCIAS_TESTES.md
│   ├── GUIA_APRESENTACAO.md
│   ├── LIMPEZA_SUGERIDA.md
│   └── PROXIMOS_PASSOS.md
├── scripts/                   ← scripts numerados (Fases 1, 2, carga externa, benchmark v2)
│   ├── 01_inspecionar_estrutura.py
│   ├── 02_processar_microdados_enade.py
│   ├── 03_gerar_bases_analise.py
│   ├── 03_validar_csvs.py
│   ├── 04_gerar_graficos_e_relatorio.py
│   ├── 05_criar_schema_postgres.py
│   ├── 06_carregar_dados_postgres.py
│   ├── 07_validar_banco.py
│   ├── 08_benchmark_sequencial.py      ← instrumentado (CPU, disco, suíte/campanha)
│   ├── 09_benchmark_paralelo.py        ← --ordem crescente|lpt (ordem de submissão)
│   ├── 10_rodar_suite_benchmark.py     ← campanha oficial: suítes × ordens × repetições
│   ├── 11_carregar_supabase.py         ← mesma carga, destino Supabase
│   ├── 13_validar_metricas.py          ← checagem cruzada Python × views × API
│   └── 14_migrar_schema_v2.py          ← migração ADITIVA (nunca --reset em banco com dados)
├── etl/                       ← módulo auxiliar dos scripts de benchmark
├── tests/                     ← pytest: filtros, repositórios, views de benchmark, rotas
├── docs/geradores/            ← documento e apresentação gerados a partir das views do banco
├── api/                       ← FastAPI read-only (Fase 3)
│   ├── Dockerfile
│   ├── main.py
│   ├── settings.py
│   ├── database.py
│   ├── dependencies.py
│   ├── requirements.txt
│   ├── routers/  repositories/  schemas/
├── frontend/                  ← SPA React/Vite original (artefato do TCC; o dashboard canônico
│                                está em EnadeX_Frontend/app/enade-time)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── NOTAS_ORGANIZACAO.md
│   └── src/  (api, hooks, components, pages, …)
├── dados_processados/         ← CSVs filtrados/consolidados (entrada do COPY)
├── microdados_enade_*/        ← arquivos brutos do INEP (somente leitura)
└── .venv/                     ← virtualenv Python local (recriável)
```

---

## Como rodar o projeto completo

> Roteiro resumido. Versão completa com troubleshooting em
> [`docs/GUIA_EXECUCAO.md`](docs/GUIA_EXECUCAO.md).

**Pré-requisitos:** Docker Desktop, Python 3.13, Node.js ≥ 20.

### 1. Subir o PostgreSQL

```powershell
cd C:\Projetos\ENADE
docker compose up -d postgres
docker compose ps
```

### 2. Validar o banco (deve reportar 24.967 linhas em `fato_enade`)

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\07_validar_banco.py
```

> Se o banco estiver vazio (primeira execução), rode antes:
> `python scripts\05_criar_schema_postgres.py` e
> `python scripts\06_carregar_dados_postgres.py`.

### 3. Subir a API (FastAPI)

Da raiz do EnadeX, no host (porta 8002):

```powershell
$env:PYTHONPATH='.'
pip install -r enade_time\requirements.txt   # primeira vez apenas
python enade_time\enade_time_rotas.py
```

O pool de conexões é criado na primeira requisição; com o Postgres fora do ar as
rotas respondem 503 (com CORS) e voltam sozinhas quando o banco volta.

Ou em container (sobe banco + API de uma vez):

```powershell
docker compose --profile api up -d --build
```

### 4. Subir o frontend (em outro terminal)

**Dashboard canônico** — módulo `/enade-time` do `EnadeX_Frontend` (Next.js):

```powershell
cd C:\Projetos\EnadeX_Frontend
pnpm install --frozen-lockfile    # primeira vez apenas (pnpm 12.3.4)
pnpm dev -p 3000                  # http://localhost:3000/enade-time
```

A API padrão é `http://localhost:8002`; para outra URL, defina
`NEXT_PUBLIC_ENADE_TIME_API_URL` antes do build/dev. Detalhes em
`docs/FRONTEND_ECOSSISTEMA.md`.

**SPA original (Vite)** — mantida como artefato do TCC:

```powershell
cd C:\Projetos\ENADE\frontend
npm install      # primeira vez apenas
npm run dev      # http://localhost:5173
```

Para o build de produção servido localmente:
```powershell
npm run build
npm run preview -- --host 0.0.0.0 --port 3000
```

---

## URLs locais

| Recurso | URL |
|---|---|
| API (FastAPI, standalone) | http://localhost:8002 |
| Swagger UI | http://localhost:8002/docs |
| Health da API | http://localhost:8002/api/enade-time/health |
| Dashboard (EnadeX_Frontend) | http://localhost:3000/enade-time |
| SPA original Vite (dev) | http://localhost:5173 |
| PostgreSQL | localhost:5432 (db `enade_db`, user `enade_user`) |

---

## Fases concluídas

| Fase | Descrição | Status |
|---|---|---|
| 1 | Schema PostgreSQL + carga do CSV consolidado | concluída |
| 2 | Benchmark sequencial × paralelo (2 e 4 workers) | concluída |
| 3 | API FastAPI read-only | concluída |
| 4 | Dashboard React/Vite | concluída |
| 5 | Empacotamento e documentação final | concluída |
| 6 | Benchmark v2 — correção do baseline do comparativo, ordem de submissão (LPT), campanha oficial com repetições e instrumentação; migração para o ecossistema EnadeX | **atual** |

Próximos passos (não implementados nesta entrega): ver
[`docs/PROXIMOS_PASSOS.md`](docs/PROXIMOS_PASSOS.md).

---

## Documentação

Consulte [`docs/README.md`](docs/README.md) para o índice completo.
Principais documentos:

- **[Guia de execução passo a passo](docs/GUIA_EXECUCAO.md)** — do zero ao dashboard.
- **[Arquitetura](docs/ARQUITETURA.md)** — camadas, fluxos e decisões técnicas.
- **[Resultados do benchmark](docs/RESULTADOS_BENCHMARK.md)** — números oficiais da Fase 2.
- **[Guia de apresentação](docs/GUIA_APRESENTACAO.md)** — roteiro oral de 8–12 min.
