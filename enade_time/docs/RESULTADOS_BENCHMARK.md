# Resultados do benchmark — campanha oficial

> **Gerado automaticamente** por `docs/geradores/gerar_resultados_md.py` em 12 de outubro de 2026, a partir das views `v_enade_time_benchmark_resumo` e `v_enade_time_benchmark_metricas` do banco local. Não edite números à mão: rode o gerador. Campanha `899faa82-2cb8-4a02-91fe-eefb89b308d3`.

## Desenho do experimento

- **Campanha:** 5 suítes completas + 1 parcial — interrompida por desligamento da máquina; as execuções já gravadas permanecem válidas (pareamento por suíte) e elevam o n de algumas configurações. Em cada suíte completa, 1 sequencial (baseline da suíte) + 4 tamanhos de pool (2, 3, 4, 6 workers) × 2 ordens de submissão (crescente e LPT) = 9 execuções; total de 48 execuções oficiais (`oficial = TRUE`), entre 01/09/2026 16:14 e 02/09/2026 13:49 UTC. O n de cada configuração está na tabela.
- **Pareamento:** cada paralela é comparada com o sequencial da **própria suíte** (`v_enade_time_benchmark_metricas`, `pareamento = 'suite'`); mediana, mínimo, máximo e IQR por configuração em `v_enade_time_benchmark_resumo`.
- **Ordens de submissão:** `crescente` (2005 → 2021, comportamento histórico do script 09) e `lpt` (maior tempo primeiro — Graham, 1969 — com os tempos por ano do sequencial da mesma suíte). O `ProcessPoolExecutor` entrega cada ano ao primeiro worker livre na ordem de submissão; ele **não** balanceia.
- **Máquina:** Intel64 Family 6 Model 140 Stepping 1, GenuineIntel — **4 núcleos físicos / 8 lógicos** (Intel Core i5-1135G7), NVMe Samsung, 24 GB RAM, Windows 11. p = 4 satura os núcleos físicos; p = 6 roda em hyperthreads.
- **Cache:** passada de aquecimento descartada antes da campanha (leu **51 MB** do disco); todas as execuções oficiais com **cache de páginas quente** — mediana de **17,3 MB** lidos por execução.
- **Carga de fundo declarada:** CPU ociosa por 10 s antes de medir = **40,4 %**; containers ativos: não registrado; CPU média do sistema durante as execuções: 67,0 %. Sem API nem frontend rodando. Diretório fora do OneDrive.
- **Pipeline por execução:** leitura dos TXT (arq1 + arq3 dos 6 anos, 5.340.372 linhas), filtro e agregação com pandas; workers puros (sem I/O em disco, sem banco); só o processo principal grava (1 linha em `tbl_enade_time_benchmark_execucao` + 6 em `tbl_enade_time_benchmark_etapa`). p = 8 fica fora da campanha: com 6 unidades de trabalho, dois workers ficariam ociosos por construção.

## Resultados por configuração

| Configuração | n | Tempo (s) — mediana [mín–máx] | IQR (s) | Speedup (mediana) | Speedup mín–máx | Eficiência (mediana) | Throughput (linhas/s) |
|---|--:|---|--:|--:|---|--:|--:|
| Sequencial (1) | 6 | 89,56 [83,42–91,13] | 5,56 | 1,0000× | — | 100,0 % | 59.633 |
| 2 workers · crescente | 6 | 56,26 [53,76–57,38] | 2,49 | 1,5750× | 1,47×–1,67× | 78,8 % | 94.946 |
| 2 workers · LPT | 5 | 48,45 [45,36–51,02] | 3,69 | 1,8392× | 1,74×–1,87× | 92,0 % | 110.232 |
| 3 workers · crescente | 6 | 42,10 [37,54–45,53] | 4,97 | 2,0693× | 1,97×–2,41× | 69,0 % | 126.859 |
| 3 workers · LPT | 5 | 38,90 [36,17–48,79] | 1,52 | 2,3042× | 1,82×–2,33× | 76,8 % | 137.276 |
| 4 workers · crescente | 5 | 40,20 [35,92–46,09] | 5,17 | 2,2498× | 1,93×–2,32× | 56,2 % | 132.839 |
| 4 workers · LPT | 5 | 40,75 [36,29–43,00] | 5,65 | 2,1216× | 2,06×–2,46× | 53,0 % | 131.052 |
| **6 workers · crescente** | 5 | 33,35 [28,60–36,06] | 3,88 | 2,7010× | 2,53×–2,92× | 45,0 % | 160.153 |
| 6 workers · LPT | 5 | 36,49 [33,09–39,30] | 5,12 | 2,4300× | 2,32×–2,52× | 40,5 % | 146.341 |

> **Melhor configuração: 6 workers · crescente** — speedup mediano **2,7010×** (mín–máx 2,53×–2,92×), eficiência **45,0 %**, contra um sequencial mediano de **89,56 s** [83,42–91,13].

## Tetos de escalonamento e decomposição da perda

Três perdas separadas, medidas por suíte e agregadas por mediana:

1. **Granularidade + escalonamento** — do ideal (soma dos tempos por ano ÷ p) ao **teto** da ordem usada (makespan do escalonamento guloso com os tempos por ano do sequencial da mesma suíte).
2. **Contenção** — do teto ao **makespan medido** (maior soma de tempos por worker); aparece como **inflação das etapas** (soma dos tempos por ano em paralelo ÷ soma no sequencial).
3. **Overhead** — do makespan medido ao wall-clock (spawn dos processos, coleta, gravação).

| p | Ordem | n | Ideal (s) | Teto ordem usada → S | Teto LPT → S | Makespan medido (s) | Inflação | Wall (s) | Overhead (s) | S medido | % do teto (ordem usada) | CPU % | Disco (MB) |
|--:|---|--:|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 2 | crescente | 6 | 44,76 | 47,58 → 1,88× | 45,03 → 1,97× | 55,25 | 1,18× | 56,26 | 1,1 | 1,5750× | 85 % | 57,9 | 33,9 |
| 2 | LPT | 5 | 44,31 | 44,56 → 1,96× | 44,56 → 1,96× | 47,49 | 1,06× | 48,45 | 0,9 | 1,8392× | 94 % | 48,3 | 14,6 |
| 3 | crescente | 6 | 29,84 | 30,93 → 2,83× | 30,77 → 2,90× | 40,88 | 1,36× | 42,10 | 1,1 | 2,0693× | 73 % | 68,8 | 19,3 |
| 3 | LPT | 5 | 29,54 | 30,38 → 2,89× | 30,38 → 2,89× | 37,83 | 1,21× | 38,90 | 1,1 | 2,3042× | 80 % | 61,7 | 18,9 |
| 4 | crescente | 5 | 22,16 | 28,76 → 3,01× | 27,74 → 3,22× | 39,14 | 1,42× | 40,20 | 1,1 | 2,2498× | 73 % | 67,8 | 17,8 |
| 4 | LPT | 5 | 22,16 | 27,74 → 3,22× | 27,74 → 3,22× | 39,59 | 1,56× | 40,75 | 1,3 | 2,1216× | 66 % | 75,5 | 9,3 |
| 6 | crescente | 5 | 14,77 | 17,62 → 4,96× | 17,62 → 4,96× | 31,80 | 1,84× | 33,35 | 1,5 | 2,7010× | 55 % | 90,1 | 16,5 |
| 6 | LPT | 5 | 14,77 | 17,62 → 4,96× | 17,62 → 4,96× | 35,00 | 2,07× | 36,49 | 1,5 | 2,4300× | 48 % | 94,2 | 7,0 |

Sequencial: n = 6, mediana 89,56 s, CPU 46,2 %, disco 71,0 MB. Aquecimento: 51 MB lidos.

## Hipóteses pré-registradas

- **H1 — p = 6 não supera p = 4 (LPT):** speedup mediano p = 4 2,1216× × p = 6 2,4300× → **refutada**. Com 4 núcleos físicos, p = 6 roda em hyperthreads e o teto de granularidade (6 unidades) não cresce a partir de 6.
- **H1 — p = 6 não supera p = 4 (crescente):** speedup mediano p = 4 2,2498× × p = 6 2,7010× → **refutada**. Com 4 núcleos físicos, p = 6 roda em hyperthreads e o teto de granularidade (6 unidades) não cresce a partir de 6.
- **H2 — cache quente ⇒ limitado por CPU, não por disco:** mediana de 17,3 MB lidos nas execuções quentes contra 51 MB no aquecimento. A explicação anterior ("4 workers lendo do mesmo disco geram contenção") **não se sustenta** nos bytes medidos: a contenção é de CPU (parsing com pandas) em 4 núcleos físicos.
- **H3 — LPT ≥ crescente:** p = 2: LPT 1,8392× × crescente 1,5750× (confirmada); p = 3: LPT 2,3042× × crescente 2,0693× (confirmada); p = 4: LPT 2,1216× × crescente 2,2498× (refutada). A diferença entre as ordens é perda de escalonamento — o código dos workers é idêntico.

> A métrica de **Karp–Flatt** mostrada no dashboard estima uma "fração sequencial" a partir do speedup; ela **embute** as três perdas acima e não deve ser lida como uma seção serial do código.

## Histórico das medições e o erro do baseline

O banco preserva todas as rodadas anteriores (nenhuma linha foi apagada ou sobrescrita; ids 1–6 mantêm o pareamento temporal com o sequencial imediatamente anterior, `pareamento = 'temporal'`).

| Data | Sequencial | T(1) | Paralela | T(p) | Speedup | Eficiência | Ordem |
|---|---|--:|---|--:|--:|--:|---|
| 21/06/2026 | #1 | 89,58 s | #2 (2 workers) | 68,40 s | 1,3096× | 65,5 % | crescente |
| 21/06/2026 | #1 | 89,58 s | #3 (4 workers) | 43,17 s | 2,0749× | 51,9 % | crescente |
| 21/08/2026 | #4 | 112,93 s | #5 (2 workers) | 74,46 s | 1,5165× | 75,8 % | crescente |
| 21/08/2026 | #4 | 112,93 s | #6 (4 workers) | 45,85 s | 2,4632× | 61,6 % | crescente |

**O erro:** a versão anterior de `/api/benchmark/comparativo` dividia todas as execuções pelo sequencial **mais recente**. Com duas rodadas no banco, o dashboard de 21/08/2026 exibiu:

| Execução | Baseline usado (errado) | Speedup exibido | Eficiência exibida | Baseline pareado | Speedup correto | Eficiência correta |
|---|---|--:|--:|---|--:|--:|
| #2 (2 workers, 68,40 s) | #4 (112,93 s) | 1,6510× | 82,5 % | #1 | 1,3096× | 65,5 % |
| #3 (4 workers, 43,17 s) | #4 (112,93 s) | 2,6157× | 65,4 % | #1 | 2,0749× | 51,9 % |
| #89 (2 workers, 53,01 s) | #4 (112,93 s) | 2,1302× | 106,5 % | #80 | 1,5736× | 78,7 % |

Esse card entrou no documento acadêmico de 21/08/2026. **Correção (DESIGN_LOG D13):** a view pareia por suíte; a API só lê a view; `scripts/13_validar_metricas.py` e `tests/` recalculam em Python e falham em qualquer divergência; documento, slides e este arquivo são gerados das views e conferidos por `docs/geradores/verificar_numeros.py`.

**A rodada citada na apresentação anterior** (sequencial de aproximadamente 243 s; "2 workers vence e 4 piora") foi apagada em um `--reset` do schema (DESIGN_LOG D9) e **não tem suporte em banco** — deixou de ser citada como resultado. A conclusão daquela rodada não é reproduzida pela campanha oficial.

Outras campanhas no banco (não oficiais): `6e6c1ccc` em 01/09/2026 (2 exec., [campanha 6e6c1ccc] smoke pos-migracao v2).

## Custo de publicação (eixo de carga)

Medição à parte do experimento de SPD (DESIGN_LOG D17): quanto custa publicar a base num destino. Fonte: `v_enade_time_benchmark_carga_resumo` (carga `0d2c38f2`).

| Estratégia | n | Mediana | Mín – máx | IQR | Throughput | RTT mediano |
| --- | --: | --: | --: | --: | --: | --: |
| COPY no Postgres local | 10 | 5,89 s | 5,39 s – 6,67 s | 0,63 s | 4.240 linhas/s | 0,6 ms |
| COPY pelo Session Pooler (Supabase) | 10 | 7,54 s | 5,78 s – 12,47 s | 1,16 s | 3.313 linhas/s | 176,3 ms |
| Controle: COPY local, sem índices nem FKs | 10 | 0,09 s | 0,07 s – 0,14 s | 0,02 s | 276.120 linhas/s | 0,6 ms |
| Controle: COPY pelo pooler, sem índices nem FKs | 10 | 4,31 s | 3,50 s – 11,25 s | 1,20 s | 5.796 linhas/s | 174,0 ms |
| Controle: COPY local, só PK e índices | 10 | 0,70 s | 0,55 s – 0,91 s | 0,20 s | 35.520 linhas/s | 0,6 ms |
| Controle: COPY local, só PK e FKs | 10 | 5,38 s | 4,76 s – 5,84 s | 0,42 s | 4.642 linhas/s | 0,5 ms |

Cada repetição carrega as 24.967 linhas numa tabela vazia e dedicada (1.767.079 bytes), com o TRUNCATE por conexão direta fora do tempo medido e o md5 do destino conferido contra a tabela fato; 10 repetições por estratégia, intercaladas, com a rede em wifi. É custo de publicação, não ganho de paralelismo, e vale para estas condições (rede, RTT e host): uma medição situada, não uma propriedade do Supabase.

A mediana do COPY no Postgres local foi 5,89 s e a do COPY pelo Session Pooler do Supabase, 7,54 s, com RTT mediano de 0,6 ms e 176,3 ms (cerca de 284 vezes maior na nuvem). O IQR foi de 0,63 s no local e de 1,16 s na nuvem. Em outra rodada, feita antes com o mesmo protocolo, as medianas foram 5,62 s e 5,59 s: a distância entre o local e a nuvem varia de uma rodada para a outra com a rede, e é por isso que o resultado vale como medição situada.

A cauda da nuvem (a repetição mais lenta levou 12,47 s) não acompanhou o RTT medido antes de cada carga: o RTT não a explica. Pode ser a vazão do enlace durante o envio, que não foi medida.

Os controles localizam o custo. No Postgres local, sem índices nem chaves estrangeiras o mesmo COPY leva 0,09 s; só com a PK e os índices secundários, 0,70 s; só com a PK e as FKs, 5,38 s; com tudo, como na tabela fato, 5,89 s. Quase todo o tempo é manutenção de estrutura, e dentro dela as chaves estrangeiras pesam muito mais do que os índices. Pelo Session Pooler, mesmo sem estrutura a carga leva 4,31 s: esse é o custo de transporte (conexão, TLS e envio do payload) nas condições da medição, e responde por boa parte dos 7,54 s da carga completa na nuvem. Hipótese a testar, não medida aqui: carregar sem as chaves estrangeiras e criá-las depois (a validação em bloco evita um gatilho por linha) reduziria o custo de uma republicação.

O upsert em lotes pelo PostgREST (util_db do grupo) não foi medido nesta rodada: exige SUPABASE_URL e SUPABASE_KEY públicas na máquina da medição.

## Reprodução

```powershell
cd C:\Projetos\ENADE
.\.venv\Scripts\Activate.ps1
docker compose up -d postgres
python scripts\14_migrar_schema_v2.py --status        # schema v2 (aditivo)
python scripts\10_rodar_suite_benchmark.py --oficial --obs "nova campanha"   # ~45 min
python scripts\13_validar_metricas.py --api http://localhost:8002 --prefixo /api/enade-time
python scripts\15_benchmark_carga.py --reps 10   # eixo de carga (local x nuvem)
python docs\geradores\gerar_resultados_md.py          # regenera este arquivo
```

Auditoria direta no banco:

```sql
SELECT * FROM v_enade_time_benchmark_resumo WHERE campanha_id = '899faa82-2cb8-4a02-91fe-eefb89b308d3' ORDER BY num_workers, ordem_submissao;
SELECT execucao_id, num_workers, ordem_submissao, speedup, eficiencia, baseline_execucao_id, pareamento
  FROM v_enade_time_benchmark_metricas WHERE campanha_id = '899faa82-2cb8-4a02-91fe-eefb89b308d3' ORDER BY suite_id, num_workers, ordem_submissao;
```

Lições registradas: clientes de sincronização em nuvem contaminam I/O (2026-06); um baseline escolhido por recência mistura rodadas (2026-08); uma explicação por "disco" não sobrevive aos bytes medidos (2026-09). Medir > supor.
