# Design Log — ENADE-Time Distribuído

**Projeto 4 — ENADE-Time · Critério B**
Aluno responsável: **Lucas Eduardo Tavares Costa**

Registro cronológico das principais decisões de projeto, com a justificativa e as
consequências de cada uma. Serve de rastro para a defesa e para futuros mantenedores.

---

## D1 — Recorte do estudo (Computação, Norte/Nordeste, 6 ciclos)
**Decisão:** processar apenas `CO_GRUPO ∈ {40, 4004}` (Computação) em
`CO_REGIAO_CURSO ∈ {1, 2}`, edições 2005/2008/2011/2014/2017/2021.
**Por quê:** tornar o experimento tratável e reprodutível, mantendo
representatividade longitudinal (ciclos trienais da área).
**Consequência:** base final de 24.967 registros; demais pastas
`microdados_enade_*` permanecem no disco mas fora do recorte.

## D2 — Harmonização do código de curso (40 ↔ 4004)
**Decisão:** tratar 40 (2005/2008) e 4004 (2011+) como equivalentes via conjunto,
**sem** recodificar para um valor único (preserva o código original do ano).
**Por quê:** manter fidelidade ao dado bruto e permitir auditoria por ano.
**Consequência:** comparação longitudinal válida; o "mapa" da equivalência fica
documentado em `DICIONARIO_VARIAVEIS.md`, não embutido como recodificação cega.

## D3 — `CO_MODALIDADE` ausente em 2005/2008
**Decisão:** quando a coluna não existe no `arq1`, criá-la com NULL.
**Por quê:** os arquivos antigos não trazem a variável; imputar valor seria
inventar dado.
**Consequência:** modalidade fica nula nesses anos (coerente e auditável).

## D4 — Notas como média por curso (grão do `arq1`)
**Decisão:** a base consolidada está no grão de curso; cada nota é a média de
`NT_*` por `CO_CURSO` (do `arq3`).
**Por quê:** alinhar notas (nível aluno no `arq3`) ao cadastro de curso (`arq1`).
**Consequência:** linhas repetidas de um mesmo curso recebem a mesma média.

## D5 — PostgreSQL + Docker, sem ORM
**Decisão:** banco em container; API com SQL explícito (psycopg2), sem ORM.
**Por quê:** reprodutibilidade (container) e auditabilidade (SQL explícito) para
um projeto acadêmico de dados tabulares read-only.

## D6 — API read-only e CORS restrito
**Decisão:** expor apenas `GET`, sem mutações, CORS só para `localhost:5173/3000`.
**Por quê:** o dashboard nunca deve alterar dados; segurança por padrão.

## D7 — Métrica principal dos gráficos = Nota Geral (NT GER)
**Decisão:** gráficos principais usam `media_nt_ger`; tabelas mantêm FG/CE/GER.
**Por quê:** decisão pedagógica do projeto (Nota Geral como indicador-síntese).
**Consequência:** ranking de IES passou a ordenar por `media_nt_ger` no backend.

## D8 — Adição controlada de `MEDIA_NT_GER` e `MEDIA_NT_CE` (v1.0 → v1.1)
**Decisão:** acrescentar as duas notas ao consolidado por um utilitário dedicado
[`tools/adicionar_notas_ger_ce_consolidado.py`](../tools/adicionar_notas_ger_ce_consolidado.py),
com **backup automático**, **reconstrução a partir dos brutos** e **validação
linha-a-linha** contra a base anterior antes de gravar.
**Por quê:** evoluir o schema sem risco de corromper a base já validada.
**Consequência:** backup `*.backup_20260616_223051.csv` (v1.0, 11 colunas)
preservado; v1.1 com 13 colunas. Propagado ao schema/carga/validação (scripts
05/06/07), API e frontend.

## D9 — Incidente: `--reset` esvaziou o benchmark local
**Decisão/ocorrência:** ao recriar o schema com `scripts/05 --reset` (para
propagar as novas colunas), as tabelas `benchmark_execucao`/`benchmark_etapa`
foram dropadas; esses dados existiam **apenas** no banco (sem dump/CSV).
**Mitigação adotada:** **não** rerodar o benchmark nem fabricar dados; os números
oficiais permanecem em [`RESULTADOS_BENCHMARK.md`](RESULTADOS_BENCHMARK.md) e na
apresentação. As telas SPD do dashboard ficam temporariamente vazias.
**Pendência:** decidir, em etapa separada, entre restaurar de backup real ou
rerodar a suíte fora do OneDrive.

## D10 — Critério B: entregar Módulos 1 + 3
**Decisão:** priorizar ETL/Harmonização (Módulo 1, documentação) + Dashboard/
Exportação (Módulo 3, frontend), deixando o Módulo 2 (IC 95%, regressão/LOESS,
quebra estrutural) como complementar.
**Por quê:** Módulos 1 e 3 estão majoritariamente prontos e têm baixo risco;
Módulo 2 exige estatística inferencial pesada.
**Consequência:** criados 4 docs do Módulo 1 e a página `/enade/comparar` com
comparação de 2 grupos por NT GER, exportações (CSV/SVG/relatório) e alerta de
amostra reduzida.

## D11 — Migração para o ecossistema EnadeX com arquitetura híbrida
**Data:** 2026-09-01 (plano v3 aprovado).
**Decisão:** o subprojeto entra no monorepo `paulogosik/EnadeX` como `enade_time/`;
o **Postgres local (Docker) continua sendo o instrumento do experimento** e o
**Supabase passa a ser o contrato de publicação** (fato, dimensões, resultados do
benchmark e views), com a API lendo de um ou de outro conforme `ENADE_TIME_DB_URL`.
**Por quê:** mover a medição para um serviço de rede substituiria uma variável
controlada por uma que não controlamos — o mesmo erro do OneDrive (D9/RESULTADOS);
o plano free do Supabase pausa após 7 dias e derrubaria a demo; o experimento tem
de ser reprodutível offline. O custo de mover a persistência para a nuvem é medido
à parte (D17), não escondido.
**Consequência:** rotas como `APIRouter(prefix="/api/enade-time")`, porta standalone
8002, pool de conexões preguiçoso, papel de leitura dedicado no Supabase.
Verificação completa em [`RELATORIO_VERIFICACAO.md`](RELATORIO_VERIFICACAO.md).

## D12 — Nomes na convenção do grupo (`tbl_enade_time_*`) nos dois bancos
**Decisão:** `fato_enade → tbl_enade_time_fato`, `dim_x → tbl_enade_time_dim_x`,
`benchmark_* → tbl_enade_time_benchmark_*`, `v_benchmark_metricas →
v_enade_time_benchmark_metricas`, novas `v_enade_time_benchmark_resumo`,
`v_enade_time_curso_ano`, `tbl_enade_time_benchmark_carga`, `tbl_enade_time_publicacao`.
Renome local só no reempacotamento (Fase 2); no Supabase, na publicação (Fase 4);
sempre por `ALTER … RENAME`, com `--desfazer-renome` no script 14.
**Por quê:** `tbl_<subprojeto>_<analise>` é a convenção verificada no repositório
(`tbl_multi_enade_*`); nada consome os nomes atuais no Supabase.
**Pendência:** se o `DEVELOPMENT.md` do grupo (fora do repositório) trouxer outra
convenção, registrar aqui; a decisão foi tomada sem ele.
**Aplicado no banco local em 12/10/2026** (dump de segurança antes; 59 execuções, 354
etapas e 24.967 linhas preservadas). O script 14 renomeia de forma idempotente e agora
roda antes da migração v2; todo o SQL do projeto (API, scripts 05–13, ETL, geradores e
testes) usa os nomes novos, então instalações novas já nascem com eles. A coluna
`id` e os índices mantêm os nomes internos antigos (`idx_fato_*`, `fato_enade_id_seq`):
são só de implementação. O texto das seções D1–D11 e dos relatórios históricos
continua com os nomes da época.

## D13 — Bug do baseline no comparativo, ordem de despacho, máquina e campanha oficial
**Ocorrência:** `api/repositories/benchmark_repo.py::comparativo` dividia **todas** as
execuções pelo **sequencial mais recente**. Enquanto o banco tinha uma rodada só,
o número coincidia com a view; quando passou a ter duas (ids 1–3 de 21/06 e 4–6 de
21/08), o dashboard de 21/08 mostrou a execução **#3 (43,17 s, 21/06) dividida pelo
baseline #4 (112,93 s, 21/08) → 2,6157× / 65,39 %**, quando o valor pareado com o
próprio baseline (#1, 89,58 s) é **2,0749× / 51,87 %**; o sequencial #1 apareceu
com "speedup 1,26". Esse card entrou no documento acadêmico de 21/08. A rodada de
21/08 em si é consistente (1,5165× e 2,4632×). A rodada citada na apresentação
(243,55 / 198,57 / 218,97 s) foi perdida no `--reset` (D9) e **não tem suporte em
banco** — deixa de ser citada.
**Achados associados (verificados em 2026-09-01):**
- O `ProcessPoolExecutor` entrega cada tarefa ao primeiro worker livre **na ordem de
  submissão**; o script 09 submetia os anos em ordem crescente. Os pids da rodada de
  21/08 confirmam a atribuição gulosa `[[2005, 2017], [2008], [2011, 2021], [2014]]`.
  Tetos de speedup só por granularidade + escalonamento (tempos por ano do sequencial
  de 21/08): ordem crescente p=2 1,81× · p=3 2,70× · p=4 3,01× · p=6 5,04×; LPT
  1,98× · 2,83× · 3,27× · 5,04×. O medido de 21/08 estava a 84 % (p=2) e 82 % (p=4)
  do teto da ordem real.
- A máquina é um **i5-1135G7: 4 núcleos físicos / 8 lógicos** (o `cpu_count = 8`
  gravado era lógico); NVMe; 24 GB. p=4 satura os núcleos físicos; p=6 roda em
  hyperthreads; com 6 unidades de trabalho, p=8 tem dois workers ociosos por
  construção. Após a primeira passada, os 3 GB de microdados ficam no cache de
  páginas.
- O sequencial do smoke pós-migração leu 814 MB do disco; a paralela seguinte, 5,7 MB
  — o pipeline em regime quente não é limitado por disco.
**Decisão:**
1. **Uma definição de métrica:** `v_benchmark_metricas` pareia cada paralela com o
   sequencial da **mesma suíte** (`suite_id`); linhas antigas mantêm o pareamento
   temporal (ids 1–6 devolvem exatamente o que devolviam). A API **só lê** as views;
   o recálculo em Python vira checagem cruzada (`scripts/13_validar_metricas.py`,
   `tests/test_view_metricas.py`).
2. **Schema aditivo** (`scripts/14_migrar_schema_v2.py`, nunca `--reset`): `campanha_id`,
   `suite_id`, `oficial`, `execucao_uid`, `ordem_submissao`, `cpu_fisicos`,
   `cpu_logicos`, `cpu_percent_medio`, `disco_bytes_lidos`, `cache_quente`,
   `aquecimento`; `v_benchmark_resumo` (mediana/mín/máx/IQR/n por campanha × workers
   × ordem). Backfill factual: `ordem_submissao = 'crescente'` nas paralelas antigas,
   `cpu_logicos = cpu_count_maquina`; `cpu_fisicos` fica NULL nas antigas.
3. **Ordem de submissão como variável:** `09 --ordem {crescente|lpt}` (LPT = Graham
   1969, com os tempos por ano do sequencial da própria suíte).
4. **Campanha oficial** (`10 --oficial`): aquecimento descartado + 5 suítes ×
   (1 sequencial + {2, 3, 4, 6} × {crescente, lpt}) = 45 execuções; CPU ociosa medida
   por 10 s antes; CPU média e bytes de disco por execução; `cache_quente = TRUE`
   declarado. p=8 fora da campanha (granularidade).
   **Execução real (01–02/09/2026):** a campanha `899faa82…` foi interrompida por
   desligamento da máquina durante a 4ª suíte e retomada no dia seguinte com
   `10 --campanha-id` (novo aquecimento — o cache esfriou no reinício). A suíte
   interrompida gravou 3 execuções válidas antes da queda (sequencial + 2w e 3w
   crescente, pareadas ao próprio sequencial) e **permanece no banco como suíte
   parcial** — nada foi apagado. Resultado: **5 suítes completas + 1 parcial,
   48 execuções oficiais**; o n por configuração varia entre 5 e 6 e está nas
   tabelas de `RESULTADOS_BENCHMARK.md`.
5. **Resposta do comparativo retrocompatível:** `itens[]` (execuções) + `resumo[]`
   (agregados) + `maquina`; dashboard usa `resumo[]` (mediana ± mín–máx).
6. Documento e apresentação passam a ser **gerados a partir das views**
   (`docs/geradores/`), e `verificar_numeros.py` confere cada número citado.
**Números oficiais:** [`RESULTADOS_BENCHMARK.md`](RESULTADOS_BENCHMARK.md).

## D14 — Incidente: chave de serviço do Supabase exposta
**Ocorrência:** a `SUPABASE_KEY` compartilhada pelo grupo (formato `sb_secret_…`,
equivalente a `service_role`, BYPASSRLS) foi exposta fora do repositório.
**Ação:** rotação individual no painel (*Settings → API Keys*: nova secret key,
distribuição, exclusão da comprometida) — a cargo do Lucas, 2026-09-01; não afeta
`anon`/`publishable` nem o JWT secret. Comunicado ao líder em
[`COMUNICADO_SEGURANCA.md`](COMUNICADO_SEGURANCA.md) com dois itens: revogar
`EXECUTE` da RPC `truncar_tabela` (SECURITY DEFINER, executável por `anon`) e o
modelo de chaves do grupo (17 tabelas com RLS sem policy só funcionam com a chave
de serviço).
**Regra daqui em diante:** meus scripts de escrita usam a senha do banco (papel
próprio), nunca a chave do grupo; segredos nunca em código nem em commit.
**Atualização (2026-09-02):** por decisão do Lucas, a **rotação foi adiada** para
o fim do projeto (dados públicos, sem PII — os microdados já são anonimizados
pelo INEP). O comunicado foi enviado ao líder. Consequência aceita: até a
rotação, quem tiver a chave exposta pode ler/escrever/truncar qualquer tabela
do projeto — a cópia local continua sendo a canônica e a republicação é
idempotente (detecção via `13 --cruzado` e `/health` a partir da Fase 4).

## D15 — Contrato de integração com o E-XplainENADE (swap point)
**Decisão:** publicar `v_enade_time_curso_ano` (582 linhas, curso × ano) com os
identificadores exatos do `load_raw()` do JP — `"NU_ANO", "CO_CURSO", "NT_GER",
"NT_FG", "NT_CE", "QT_ALUNOS", "CO_GRUPO", "CO_REGIAO", "TP_CATEGAD_BIN"` — e
`COMMENT ON COLUMN` avisando que `QT_ALUNOS` aqui é inscritos (linhas do arq1), não
`TP_PRES == 555`. É **extensão longitudinal** (2005–2017 para os 82 cursos do
recorte), não substituição: o recorte dele (753 cursos, CC+SI, Brasil, 2021) segue
em `tbl_arq*_2021`. Formalização com o JP pendente (evidência dos dois lados).

## D16 — Unidade analítica é curso-ano (582), não 24.967
**Fato:** as 13 colunas do consolidado são função de (ano, curso): 582 pares, 24.385
linhas integralmente duplicadas. Médias sobre a fato são ponderadas por matrícula;
N para inferência é 582.
**Consequência:** `v_enade_time_curso_ano` como resposta preparada; KPI "Total de
registros" rotulado como inscrições; `AlertaAmostra` passa a contar cursos
(`total_cursos` na API); documentado em `DICIONARIO_VARIAVEIS` e `GUIA_APRESENTACAO`.
**Implementado em 12/10/2026:**
- `resumo-anual/regiao/uf/ies` devolvem `total_cursos` (`COUNT(DISTINCT co_curso)`), campo
  aditivo. Conferido no dado: somar os cursos distintos de cada ano dá exatamente 582, e por
  região também fecha (`tests/test_repositorios.py`).
- O dashboard (módulo `/enade-time` do `EnadeX_Frontend`) alerta quando o grupo tem menos de
  30 **cursos** no ano, mostrando as inscrições ao lado. Contra uma API antiga, volta a contar
  inscrições. O efeito é grande: por UF e ano a mediana é de 5 a 10 cursos, e o alerta antigo
  (n < 30 inscrições) marcava só 5 dos 92 pares UF×ano, subestimando a fragilidade.
- `min_cursos` do ranking de IES contava inscrições (`COUNT(*)`) apesar do nome; passou a
  contar cursos distintos. Muda o resultado de `resumo-ies` com `min_cursos > 1` (exceção
  documentada no `diff_golden`, sem outras regressões nas 30 rotas).
- O verificador de números (`docs/geradores/verificar_numeros.py`) não conferia nenhum
  speedup: a regex terminava em `\b`, e depois de "×" não há fronteira de palavra. Corrigido
  (com teste): passou de 43/39 para 98/122 números conferidos no .pptx/.docx, todos
  rastreados às views em modo estrito.

## D17 — Eixo de carga local × nuvem como medição situada (essencial)
**Decisão:** medir, com o mesmo instrumental, a etapa de carga das 24.967 linhas em
três estratégias — `COPY` local, `COPY` via Session Pooler e `upsert` PostgREST em
lotes — n = 10, sempre em **tabela vazia** (destino dedicado `*_fato_bench`, truncado
por DSN antes de cada repetição), com RTT medido no canal testado, bytes de payload,
host e rede logados. Reportado como **custo de publicação** (mediana/IQR), nunca como
speedup. Execução na Fase 7 do plano.

---

## Convenções de ambiente
- Diretório oficial: `C:\Projetos\ENADE` (rodar **fora** do OneDrive).
- Comandos Node em `frontend/`; Python/Docker na raiz.
- Nada de alterar dados brutos, CSV consolidado, scripts 01–10, schema, benchmark
  ou carga sem decisão explícita.
