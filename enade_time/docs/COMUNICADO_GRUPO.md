# ENADE-Time Distribuído entrou no EnadeX — o que chegou e o que vem

**De:** Lucas Eduardo Tavares Costa · **Data:** 02/09/2026 · **Atualizado:** 12/10/2026
**Branch:** `enade-time/migracao` → pasta **`enade_time/`** (nada fora dela foi alterado)

---

## O que é

O Projeto 4 do ecossistema (Critério B, Módulos 1 e 3): a **base longitudinal do
ENADE 2005–2021** para Computação no Norte/Nordeste (24.967 inscrições =
**582 cursos-ano**, a unidade analítica), o **experimento de processamento
paralelo** da disciplina de SPD e o **dashboard** (módulo `/enade-time` do
`EnadeX_Frontend`, em Next.js) que exibe tudo.

## Como rodar (da raiz do EnadeX, como o educluster)

```powershell
cd C:\...\EnadeX
$env:PYTHONPATH='.'
pip install -r enade_time\requirements.txt
cd enade_time; docker compose up -d postgres; cd ..     # banco local do subprojeto
python enade_time\scripts\07_validar_banco.py            # → BASE VALIDADA (24.967)
python enade_time\enade_time_rotas.py                    # API standalone na PORTA 8002
```

Swagger: `http://localhost:8002/docs` — **20 endpoints read-only** sob
`/api/enade-time/*` (health, dimensões, análises, benchmark).

**Sem Docker:** a API também lê do Supabase do grupo, onde os dados estão publicados
(`python enade_time\enade_time_rotas.py --fonte supabase`). Ela usa um papel
**somente leitura** (`enade_time_reader`) por DSN próprio, na variável
`ENADE_TIME_DB_URL_SUPABASE` do `.env` (nunca versionado). Quem quiser esse acesso pede a
mim em privado; não existe senha no repositório. O `/health` informa `fonte`
(`local`/`supabase`) e a data da última publicação.

### Para o líder: ligar ao `api_main.py` central (2 linhas)

```python
from enade_time.enade_time_rotas import router as enade_time_router
app.include_router(enade_time_router)
```

O router é autocontido: **não precisa de lifespan**. O pool de conexões nasce na
primeira requisição e, se o Postgres do ENADE-Time estiver fora, as rotas
respondem **503 com os cabeçalhos CORS** — a API central continua de pé e as
rotas dos outros subprojetos não são afetadas. Só falta acrescentar
`psycopg2-binary`, `pydantic-settings` e `uvicorn` ao `requirements.txt` da raiz.
(Atenção: a linha `# app.include_router(enade_time_router)` comentada hoje no
`api_main.py` dá `NameError` se for apenas descomentada — falta o import acima.)

Portas combinadas: 8000 = api_main · 8001 = educluster · **8002 = enade_time** ·
8003 = e_xplainenade.

## Dashboard: já está no frontend do grupo

O módulo **`/enade-time`** foi publicado no `EnadeX_Frontend` (somente em
`app/enade-time/` e `lib/enade-time/`; no código compartilhado só o `href` e o
período do card na home e a dependência `@tanstack/react-query`). Ele fala com
a API acima pela variável `NEXT_PUBLIC_ENADE_TIME_API_URL` (padrão
`http://localhost:8002`; com o router no `api_main`, `http://localhost:8000`).
Sem banco acessível (local ou Supabase), o módulo mostra "Banco indisponível" e
volta sozinho quando ele reaparece. A SPA
original (Vite), em `enade_time/frontend/`, fica preservada como artefato do TCC.
Detalhes e verificação: `enade_time/docs/FRONTEND_ECOSSISTEMA.md`.

## O que foi entregue nesta branch

- **Convenções do repositório respeitadas:** pasta `snake_case` importável,
  `enade_time_rotas.py` com `APIRouter` prefixado (sem colisão de rotas),
  `requirements.txt`/`.gitignore` próprios, imports qualificados
  `enade_time.*` — roda da raiz com `PYTHONPATH=.`.
- **Microdados brutos (3+ GB) NÃO entram no git** — quem for rodar o ETL
  aponta `ENADE_TIME_MICRODADOS_DIR` (ver `enade_time/.env.example`). O CSV
  consolidado (5 MB) está versionado em `dados_processados/`.
- **Benchmark v2, refeito com rigor antes de migrar:** campanha oficial com
  repetições (5 suítes completas + 1 parcial preservada), duas ordens de
  submissão (crescente × LPT/Graham), máquina declarada (4 núcleos físicos /
  8 lógicos), cache aquecido e instrumentação de CPU/disco por execução.
  Speedup/eficiência têm **uma única definição, em views SQL** — a API só lê.
  Resultado-chave: melhor configuração **6 workers·crescente, 2,701× mediana**;
  a perda é decomposta em granularidade+escalonamento / contenção de CPU /
  overhead (`docs/RESULTADOS_BENCHMARK.md`, gerado do banco).
- **Qualidade:** 120 testes pytest (`enade_time/tests`, os que dependem do banco
  são pulados sem o Postgres local), regressão "golden" das rotas, e `docs/geradores/verificar_numeros.py`
  garante que **nenhum número** do documento/slides existe sem linha no banco.
- Correção documentada de um bug real: o comparativo antigo usava "o sequencial
  mais recente" como baseline e misturou rodadas (`docs/DESIGN_LOG.md`, D13).

## Publicado no Supabase (12/10) e o que ainda vem

**Já está lá**, com os nomes na convenção do grupo (`tbl_enade_time_*`, `v_enade_time_*`;
mesmos nomes no banco local), RLS ligada, leitura pública só de `SELECT` e `md5` linha a
linha conferido contra o banco local:
- `tbl_enade_time_fato` (24.967 linhas, consumível por `consultar_dados`) e as 7 dimensões;
- `tbl_enade_time_benchmark_execucao`, `_etapa` e `_carga`, e as views de benchmark;
- **`v_enade_time_curso_ano` (582 linhas)** — o *swap point* combinado com o
  E-XplainENADE, com os MESMOS nomes de coluna do `load_raw()` do JP
  (`NU_ANO, CO_CURSO, NT_GER, NT_FG, NT_CE, QT_ALUNOS, CO_GRUPO, CO_REGIAO,
  TP_CATEGAD_BIN`): extensão longitudinal 2005–2017 para o recorte comum. A diferença
  de definição de `QT_ALUNOS` (inscritos × presentes) está documentada na view.
- O **custo de publicar** a base (COPY local × COPY pelo pooler, com controles que isolam
  índices e chaves estrangeiras) foi medido e aparece em `/enade-time/spd/carga`. É uma
  medição situada (uma rede, uma máquina, n = 10), não um speedup. O upsert pelo PostgREST
  ainda não foi medido: precisa da `SUPABASE_URL` e da chave pública na máquina da medição.

**Falta:**
1. Contrato do swap point confirmado pelo JP (ver pedidos abaixo).
2. Medir o upsert pelo PostgREST (`util_db` do grupo).
3. PR da branch para a `main`, com as propostas em `enade_time/docs/PROPOSTAS_COMPARTILHADAS.md`
   (arquivos fora de `enade_time/` que o líder pode adotar; nenhum foi alterado por mim).
4. Router no `api_main` central: 2 linhas, acima. Falta a decisão do líder.

## Pedidos ao grupo

- **Segurança (já enviado ao líder, urgente):** revogar `EXECUTE` da RPC
  `truncar_tabela` para `anon`/`authenticated` no Supabase e revisar o modelo
  de chaves — detalhes em `enade_time/docs/COMUNICADO_SEGURANCA.md`.
- **JP:** confirmar o contrato do swap point (nomes acima; a diferença de
  definição de `QT_ALUNOS` — inscritos × presentes — vai documentada na view).
- **Líder:** compartilhar o `DEVELOPMENT.md`/atas (as decisões citadas no
  código do E-XplainENADE estão fora do repositório) — não bloqueia, mas evita
  conflito de nomenclatura na publicação.

Dúvidas ou algo que interfira no subprojeto de vocês: me chamem. Nada fora de
`enade_time/` foi tocado, e tudo o que está aqui roda de ponta a ponta hoje.
