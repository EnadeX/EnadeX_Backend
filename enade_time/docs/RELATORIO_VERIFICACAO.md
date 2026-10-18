# Relatório de verificação — estado real antes da migração para o EnadeX

**Projeto 4 — ENADE-Time · Critério B**
Aluno responsável: **Lucas Eduardo Tavares Costa**
Data da verificação: **2026-09-01**
Fontes: filesystem de `C:\Projetos\ENADE`, git local, clone de
`https://github.com/paulogosik/EnadeX` (branch `main`, commit `c4f9964`),
MCP do Supabase (projeto `yghryywuxfwzvfjknpgk`), `Win32_Processor`/`psutil`
da máquina de medição.

Este documento registra o que foi **encontrado**, não o que foi planejado.
Serve de linha de base para o `DESIGN_LOG` (D11–D17) e para a Fase 0 do plano
de migração. Onde a documentação anterior do projeto ou a leitura externa do
repositório divergiam da realidade, a divergência está marcada.

---

## 1. Projeto local (`C:\Projetos\ENADE`)

| Item | Verificado | Divergência / consequência |
|---|---|---|
| Árvore | `scripts/` (01–11 + `03_validar_csvs`, `04_gerar_graficos`), `etl/` (`processar_ano.py`, `bench_db.py`), `api/` (main, settings, database, dependencies, 4 routers, 3 repositórios, 3 schemas, Dockerfile), `frontend/src` (66 arquivos), `tools/` (1), `docs/` (12 `.md`), `dados_processados/` (5,3 MB), `apresentacao/` (gitignorada: pptx, docx, `gerar_*.py`, screenshots, terminal_logs). | `LIMPEZA_SUGERIDA.md` e `apresentacao/` não constavam na leitura externa. |
| Git | `main`, **1 commit** (`b04f4f1`), remote único `lucasetculbra/enade-time-distribuido`. **36 arquivos modificados + ~15 novos não commitados** (v1.1/Fase 5 inteira). | Commit do trabalho pendente antes de qualquer move. |
| `.env` local | `POSTGRES_*`, `SUPABASE_PROJECT_REF`, `SUPABASE_DB_PASSWORD`. Nunca commitado (`git log --all -- .env` vazio; sem `eyJ…`/`sb_…` no histórico). | Não contém `SUPABASE_KEY`. A chave exposta é a `SUPABASE_KEY` do `.env` **do grupo**, formato `sb_secret_…` (= `service_role`, BYPASSRLS). |
| Dependências | venv Python 3.13.14: pandas 3.0.3, numpy 2.4.6, psutil 7.2.2, fastapi 0.136, psycopg2-binary 2.9.12, python-dotenv, python-docx 1.2, python-pptx 1.0.2. **Ausentes: `supabase`, `pytest`, `httpx`.** `psutil.disk_io_counters()` e `psutil.cpu_percent(percpu=True)` funcionam. | `requirements.txt` + `requirements-dev.txt` no `enade_time/`. |
| **Máquina de medição** | `Win32_Processor`: **11th Gen Intel Core i5-1135G7 @ 2,40 GHz — 4 núcleos físicos, 8 lógicos** (`psutil.cpu_count(logical=False) = 4`), L2 5 MB, L3 8 MB; **NVMe Samsung MZVLQ256HAJD (238 GB)**; RAM 24.299 MB; notebook Samsung 550XDA; Windows 11. **Disco C: com 2 GB livres na data.** | `cpu_count_maquina = 8` gravado nas execuções anteriores é o número **lógico**. p = 4 satura os núcleos físicos; p = 6 roda em hyperthreads. 24 GB de RAM contra 3,08 GB de arquivos → após a 1ª passada tudo está no cache de páginas. |
| CSV consolidado v1.1 | 24.967 × 13; por ano 5.748 / 8.740 / 2.463 / 2.388 / 2.537 / 3.091; 192 nulos em cada nota (coincidentes); `CO_MODALIDADE` 14.488 nulos; `CO_MUNIC_CURSO` 456 nulos. **216 `CO_CURSO` distintos, 582 pares (ano, curso), 24.385 linhas integralmente duplicadas.** | As 13 colunas são função de (ano, curso): os "24.967 registros" são inscrições replicando **582 observações**; médias sobre a fato são ponderadas por matrícula; N para inferência não é 24.967. O `AlertaAmostra` do frontend conta `total_registros` (inscrições). |
| Tamanhos | 6 pastas usadas de microdados = **3,08 GB** (508 + 741 + 287 + 515 + 531 + 500 MB); 15 pastas = 6,4 GB; `frontend/node_modules` 177 MB; bundle 717 KB. | 9 pastas fora do recorte (≈ 3,26 GB) são arquiváveis. |
| Postgres local | **Confirmado no banco (Fase 0, Docker subiu):** `fato_enade` 24.967; `benchmark_execucao` **6 linhas**, `benchmark_etapa` 36. ids **1–3** = suíte de 21/06 (18:54 UTC; 89,5773 / 68,3998 / 43,1718 s; obs. "repopular SPD apos reset") e ids **4–6** = 21/08 (12:49 UTC; 112,9257 / 74,4648 / 45,8451 s). `v_benchmark_metricas`: #2 1,3096× · #3 2,0749× · #5 1,5165× · #6 2,4632×. O golden de `/api/benchmark/comparativo` reproduz o bug: #3 → 2,6157×, #2 → 1,6510×, #1 (sequencial) → 1,2607×. | A rodada citada na apresentação (243,55 / 198,57 / 218,97 s) **não existe em banco nenhum** — foi apagada no `--reset` do schema (D9). Os ids se repetem porque o `BIGSERIAL` reiniciou. |
| **Bug do baseline** | `api/repositories/benchmark_repo.py::comparativo` escolhe **o sequencial mais recente** como baseline e divide **todas** as execuções por ele, inclusive paralelas de outras rodadas e o outro sequencial. | **Efeito nos números publicados:** o card "melhor configuração 4 workers, 2,6157×, 65,39 %" do documento (screenshot do comparativo, 21/08) é a **execução #3 de 21/06 (43,17 s) dividida pelo baseline de 21/08 (112,93 s)**; contra o próprio baseline (89,58 s) ela dá **≈ 2,075× e 51,9 %**. O sequencial #1 aparece com "speedup 1,26". A rodada de 21/08 é **internamente consistente** (74,46 s → 1,5165× / 75,82 %; 45,85 s → 2,4632× / 61,58 %), então a conclusão "4 workers vence" **sobrevive, com 2,4632× e 61,58 %**. A apresentação ("2 workers vence e 4 piora") **não tem suporte em banco**: slides 10, 11 e 14 precisam ser refeitos a partir da campanha oficial. |
| `v_benchmark_metricas` | `LEFT JOIN LATERAL` pega o sequencial imediatamente anterior no tempo. Correta para rodadas isoladas; frágil quando rodadas se misturam. | Pareamento por `suite_id` (plano, D8). |
| **Ordem de despacho** | `scripts/09` submete `ANOS` em ordem crescente; `ProcessPoolExecutor` entrega ao primeiro worker livre. No log de 4 workers (21/08): pid 12432 → 2005 e depois 2017; pid 20892 → 2011 e depois 2021 — exatamente a atribuição do **escalonamento guloso na ordem de submissão** `[[2005, 2017], [2008], [2011, 2021], [2014]]`. | O executor **não faz LPT**. |
| **Tetos por granularidade + escalonamento** (tempos por ano do sequencial de 21/08: 13,69 · 19,42 · 15,12 · 20,47 · 21,77 · 22,42 s; soma 112,89 s; 0,04 s fora das etapas) | Ver tabela abaixo. | Com 6 unidades, p = 8 não pode superar p = 6 por construção; p = 6 é inatingível nesta máquina (4 núcleos físicos). |
| **Decomposição da perda (21/08)** | p = 2: ideal 56,45 s → escalonamento (ordem real) 62,31 s → etapas medidas infladas **1,22×** → makespan 72,85 s → wall 74,46 s (overhead fora das etapas 1,61 s). p = 4: 28,22 → 37,54 → infladas **1,24×** → 44,70 → 45,85 s (overhead 1,15 s). Medido = **84 % (p = 2) e 82 % (p = 4) do teto da ordem real** (76 % / 75 % do teto LPT). | Três perdas separáveis: **granularidade + escalonamento**, **contenção** (inflação das etapas — candidata a CPU em 4 núcleos físicos, a confirmar com bytes de disco), **overhead** (spawn/coleta, ~1–2 s). O Karp–Flatt embute as três. |
| Geradores | `apresentacao/gerar_apresentacao.py`: números **hardcoded** (243,55 / 198,57 / 218,97; "2 workers vence"). `apresentacao/documento_final/gerar_documento.py`: nenhum número como texto; embute `screenshots/*.png` e `terminal_logs/*.txt`. **Nenhum dos dois lê banco.** | Passam a ler `v_benchmark_resumo` / `v_benchmark_metricas` da campanha oficial. |
| API | **18 endpoints** (health 1 · dim 7 · analises 5 · benchmark 5), não 15. Prefixo `/api` em `api/main.py`; pool no `lifespan`; CORS `GET` para 5173/3000; `settings` lê `.env` do CWD. | Textos que dizem "15" serão corrigidos. |
| Frontend | `VITE_API_BASE_URL` (default `http://localhost:8000`); **18 caminhos `/api/...` literais** em `src/api/*.ts`; 11 páginas + 2 redirects + 404. `Home.tsx` e os 4 gráficos consomem `comparativo.itens[]`, `tempo_baseline_seg`, `baseline_sequencial_id`; `Comparativo.tsx` calcula Karp–Flatt sobre `itens[]`. Node 24.14 / npm 11.9. | A resposta do `comparativo` tem de manter `itens[]` e ganhar `resumo[]`. |
| `scripts/11` | `COPY FROM STDIN` via Session Pooler com senha do banco (não usa `util_db`); autodetecção `aws-1`/`aws-0`/IPv6; trunca antes; reusa `preparar_buffer` do script 06. | Vira a estratégia "COPY via pooler" do eixo de carga. |
| Workers | `processar_ano` top-level, sem I/O, sem banco, sem print, exceção capturada; `RAIZ = Path(__file__).parent.parent`. | Após o move, `RAIZ` apontaria para `enade_time/` → `ENADE_TIME_MICRODADOS_DIR`. |
| `docs/LIMPEZA_SUGERIDA.md` | Propõe, só depois da banca, arquivar 9 pastas de microdados fora do recorte (2010, 2012, 2013, 2015, 2016, 2018, 2019, 2022, 2023 ≈ 3,26 GB), apagar caches, regra do OneDrive, checklist. | Com 2 GB livres, o arquivamento das 9 pastas antecipa para a Fase 0. |

**Tetos de speedup por granularidade + escalonamento (6 unidades, tempos do sequencial de 21/08):**

| p | Ordem crescente (real do `09`) makespan → teto | LPT (Graham 1969) makespan → teto | Medido 21/08 | % do teto real | % do teto LPT |
|--:|---|---|---|---|---|
| 2 | 62,31 s → **1,81×** | 56,96 s → 1,98× | 1,5165× | 84 % | 76 % |
| 3 | 41,84 s → **2,70×** | 39,89 s → 2,83× | — | — | — |
| 4 | 37,54 s → **3,01×** | 34,54 s → 3,27× | 2,4632× | 82 % | 75 % |
| 6 | 22,42 s → **5,04×** | 22,42 s → 5,04× | — | inatingível: 4 núcleos físicos | — |
| 8 | 22,42 s → 5,04× | 22,42 s → 5,04× | — | dois workers ociosos por construção | — |

---

## 2. Repositório EnadeX (`paulogosik/EnadeX`, clone de 2026-09-01)

| Item | Verificado |
|---|---|
| Estado | `main` com 14 commits, último `c4f9964` (30/08/2026, Cintriano). Existe `origin/develop`, **5 commits atrás de `main`** (não usada). Nenhuma pasta `Enade-Time`/`enade_time`. `api_main.py` = **0 bytes**. `README.md` = `# EnadeX`. |
| Higiene | `.gitignore` de 3 linhas (`.env`, `*.png`, `.idea/`). **22 `.pyc` versionados** (`util/` 3, `educluster/` 19). `requirements.txt` da raiz em **UTF-16 LE + CRLF** (numpy 2.4.2, pandas 3.0.1, python-dateutil, setuptools, six, tzdata). |
| `util/` | Sem `__init__.py`. `credenciais_banco()` monta `https://{SUPABASE_URL}.supabase.co` sem validar; `consultar_dados` pagina de 1000; `upsert_supabase` manda o DataFrame inteiro numa chamada e **engole exceções** (retorna `False` e imprime); `truncar_tabela_supabase` chama a RPC `truncar_tabela`. `.env_example`: `SUPABASE_KEY=` / `SUPABASE_URL=`. |
| `multi_enade/` | Instância própria `FastAPI()`, porta 8000, rotas **sem namespace** (`/api/relatorio-regressao|cluster|associacao`); lê `tbl_arq3/4/21/29_2021` e faz `upsert_supabase` em `tbl_multi_enade_*`; sem README/requirements/.gitignore/`__init__.py`. |
| `educluster/` | Único pacote Python real; instância própria FastAPI, porta 8001, prefixo `/api/educluster`; `origem` default `local`; espera microdados em `<pai do EnadeX>/microdados/microdados_Enade_2021_LGPD/2.DADOS`; README lista 5 modelos, disco tem 6. |
| `E-XplainENADE/` | `APIRouter(prefix="/api/e-xplainenade")`; `__main__` na porta **8001 (colide com educluster)**; imports `from config…`/`from modules…` só resolvem com a pasta no `sys.path`; hífen impede `import`. `.gitignore` ignora `CLAUDE.md`, `DEVELOPMENT.md`, `docs/`. **Swap point** em `modules/etl.py` nomeando "ENADE-Time (Lucas)". `load_raw()` devolve `CO_CURSO, NT_GER, NT_FG, NT_CE, QT_ALUNOS, CO_GRUPO, CO_REGIAO, TP_CATEGAD_BIN` (+ 12 colunas QE/turno/sexo/idade), em maiúsculas; `TP_CATEGAD_BIN = {1,2,3 → 0; 4,5 → 1}` (7 → NaN); `CO_REGIAO` = rename de `CO_REGIAO_CURSO`; `QT_ALUNOS` = presentes (`TP_PRES == 555`), peso do WLS. Recorte: `CO_GRUPO ∈ {4004, 4006}`, Brasil, 2021. |
| Documentação fora do repositório | `git log --all` para `CLAUDE.md`, `DEVELOPMENT.md`, `docs/`: **vazio em todos os branches**. As combinações do grupo citadas no código do E-XplainENADE (decisões de 20, 26, 27, 29 e 30/08) estão fora do repositório. |
| Não verificável | PRs/issues/wiki do GitHub (`gh` não instalado). |

---

## 3. Supabase (`yghryywuxfwzvfjknpgk`, org EnadeX, us-east-2, PostgreSQL 17.6)

| Item | Verificado |
|---|---|
| Plano | **`free`** (500 MB de banco; pausa após 7 dias sem uso). Banco usa **68 MB**. |
| Tabelas (25) | 14 × `tbl_arq{1,2,3,4,5,6,10,11,14,16,21,23,27,29}_2021` com **25.522 linhas cada** (o `list_tables` mostra `rows: 0` em 4 delas por estatística desatualizada; `COUNT(*)` confirma 25.522). Recorte: `CO_GRUPO ∈ {4004 (329 cursos), 4006 (424)}`, **5 regiões**, 2021, 753 cursos = recorte do E-XplainENADE. `tbl_multi_enade_regressao` 648, `_clusters` 707, `_associacao` 4. **`enade_time_distribuido` 24.967** + `dim_regiao` 2, `dim_uf` 16, `dim_grupo` 2, `dim_categoria_adm` 6, `dim_organizacao_acad` 6, `dim_modalidade` 2, `dim_ano` 6 (migrações de 06/08/2026). **Nenhuma view, nenhuma tabela de benchmark.** Os 82 cursos de 2021 do ENADE-Time estão todos em `tbl_arq1_2021` (82/82). |
| Tipagem | Duas gerações de carga: `tbl_arq1/2/5/6/10/11/14/16/23/27/29`: `id uuid`, resto `text`; `tbl_arq3`: `id text`, `NU_ANO integer`, notas `real`; `tbl_arq4/21`: `id text`, `NU_ANO integer`; `tbl_arq29`: `NU_ANO bigint`. **`CO_CURSO` é `text` em todas.** `enade_time_distribuido` tem tipos corretos (`smallint/integer/numeric(7,4)`), CHECKs, 11 índices, 7 FKs; `id` é **IDENTITY ALWAYS**. |
| RLS / policies / grants | RLS ligado em todas. Policies só nas 8 tabelas do ENADE-Time (`leitura publica`, SELECT para `anon`+`authenticated`). As 17 tabelas dos colegas têm **RLS sem policy** → só a chave de serviço as lê/grava. `anon`/`authenticated`/`service_role` têm `DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE` em todas (default). |
| RPC `truncar_tabela(text)` | `plpgsql`, **`SECURITY DEFINER`, executável por `anon` e `authenticated`**, `search_path` mutável, `TRUNCATE public.%I RESTART IDENTITY CASCADE`. Advisors: WARN. Ver `COMUNICADO_SEGURANCA.md`. |
| Chaves | Legacy `anon` (JWT) ativa + `sb_publishable_…` ativa; a `sb_secret_…` comprometida (rotação individual). |
| Extensões | Apenas padrão (`pgcrypto`, `pg_stat_statements`, `uuid-ossp`, `supabase_vault`, `plpgsql`). |

---

## 4. Síntese — o que muda em relação ao que estava documentado

1. Há **3 rodadas** de benchmark, não 2; a da apresentação não existe em banco; a de 21/08 é consistente; o documento exibiu a #3 com baseline errado.
2. O executor despacha na **ordem de submissão**; o medido está a 82–84 % do teto da ordem real.
3. A máquina tem **4 núcleos físicos / 8 lógicos**, NVMe, e opera com **cache quente** após a primeira passada.
4. **Fato e dimensões já estão publicadas** no Supabase desde 06/08/2026.
5. A **chave de serviço do grupo foi exposta** e a RPC de truncate está aberta à anon key.
6. 18 endpoints / 11 páginas; `pytest`, `httpx` e `supabase` ausentes do venv; trabalho não commitado; **2 GB livres em C:**.
7. Os geradores de documento e apresentação **não leem banco**.
