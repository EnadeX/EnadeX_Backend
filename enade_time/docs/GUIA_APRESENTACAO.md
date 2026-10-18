# Guia de apresentação oral

Roteiro sugerido para apresentar o projeto **ENADE-Time Distribuído** em
**8 a 12 minutos**. As falas estão em linguagem simples e direta, para
serem usadas como referência (não como script literal). Adapte conforme
o público.

> **Números:** nenhum número de benchmark está escrito neste guia. Leia-os
> de [`RESULTADOS_BENCHMARK.md`](RESULTADOS_BENCHMARK.md) (gerado das views
> do banco) ou do dashboard — os dois mostram a **mesma** campanha oficial.
> Onde este guia diz "X", cite o valor da tabela.

## Estrutura geral (≈ 10 min)

| Bloco | Tempo | Conteúdo |
|---|---:|---|
| 1 | 0:30 | Problema e objetivo |
| 2 | 1:00 | Base de dados ENADE (e o grão) |
| 3 | 1:00 | Pipeline e granularidade do paralelismo |
| 4 | 0:45 | Banco PostgreSQL e a definição única das métricas |
| 5 | 1:30 | Desenho do experimento (campanha) |
| 6 | 1:30 | Resultados: três perdas |
| 7 | 1:00 | Histórico e o erro do baseline |
| 8 | 1:30 | Dashboard (demo ao vivo) |
| 9 | 0:45 | Conclusão técnica |

## Antes de começar

- Deixar abertos:
  - Docker Desktop com `enade_postgres` `(healthy)` — e **só** ele.
  - Terminal com `uvicorn` rodando (`/docs` aberto).
  - Navegador com a Visão Geral e uma aba em `/spd/comparativo`.
  - `RESULTADOS_BENCHMARK.md` em outra janela.
- Se a demo incluir uma execução ao vivo, rode-a com `--obs demo` (nasce
  `oficial = FALSE`) e use a diferença para a mediana oficial como argumento
  (bloco 8).

---

## 1. Problema e objetivo (0:30)

> *"O ENADE produz, a cada três anos, milhões de linhas de microdados.
> Processá-los é caro. Este projeto investiga: **dá para ganhar tempo
> paralelizando esse trabalho?** Quanto — e, principalmente, **onde o ganho
> se perde**: na granularidade do trabalho, no escalonamento, na contenção
> ou no overhead?"*

Pontos a fixar: objetivo **acadêmico** (SPD em cenário real); não é "rodar
mais rápido", é **medir e explicar**.

## 2. Base de dados ENADE — e o grão (1:00)

> *"Microdados oficiais do INEP, Computação, Norte e Nordeste, seis edições
> trienais. Depois de filtrar e validar, a base tem 24.967 linhas — mas a
> unidade analítica é **curso-ano: 582 observações**. As 24.967 linhas são
> inscrições; a replicação funciona como peso por matrícula nas médias."*

**Resposta pronta se perguntarem sobre N:**
> *"O N para inferência é 582, não 24.967. A view `v_enade_time_curso_ano`
> materializa exatamente esse grão, com os nomes de coluna que o
> E-XplainENADE consome."*

## 3. Pipeline e granularidade (1:00)

> *"Três etapas: ler os TXT brutos, filtrar pelo recorte e agregar. O trabalho
> é dividido **por ano** — 6 unidades independentes, de tamanhos diferentes.
> Isso é ótimo para paralelizar sem sincronização, e é também a primeira
> limitação: com 6 unidades, o speedup tem um teto que não depende de
> Amdahl."*

## 4. Banco e a definição única das métricas (0:45)

> *"Postgres 16 em Docker. Além da tabela fato e das dimensões, o benchmark
> grava cada execução e cada etapa. Speedup e eficiência têm **uma única
> definição**, em SQL: a view `v_enade_time_benchmark_metricas` pareia cada execução
> paralela com o sequencial da **própria suíte**. A API não recalcula nada;
> ela só lê a view. Um script em Python recalcula tudo a partir das tabelas
> para conferir — e falha se um número divergir."*

## 5. Desenho do experimento (1:30)

> *"A campanha oficial tem cinco suítes completas — mais uma parcial, que
> sobreviveu a uma queda da máquina e permanece no banco (o n por configuração
> está na tabela). Em cada suíte completa: um sequencial e, depois,
> 2, 3, 4 e 6 workers, cada tamanho em **duas ordens de submissão**. Por quê
> duas ordens? Porque o executor entrega cada ano ao primeiro worker livre,
> na ordem em que foi submetido — ele não balanceia. Submeter os anos maiores
> primeiro (LPT, Graham 1969) muda o makespan sem mudar uma linha dos
> workers."*

Declare a máquina e as condições (do `RESULTADOS_BENCHMARK.md`):
- **4 núcleos físicos / 8 lógicos** — p = 4 satura os físicos; p = 6 roda em
  hyperthreads; p = 8 não entrou porque com 6 unidades dois workers ficariam
  ociosos.
- **Cache quente** declarado: uma passada de aquecimento foi descartada; nas
  execuções oficiais o disco quase não é lido.
- CPU ociosa medida antes de começar; Docker só com o Postgres.

## 6. Resultados — três perdas (1:30)

Abrir a tabela de configurações e a tabela de tetos em
`RESULTADOS_BENCHMARK.md` (ou `/spd/comparativo`).

> *"A melhor configuração foi **X workers · ordem Y**, speedup mediano **S**
> (mín–máx entre suítes), eficiência **E**. Agora, onde se perde o resto?"*

1. **Granularidade + escalonamento** — *"Com os tempos por ano do
   sequencial, o teto da ordem usada em p = 4 é **T×**; o medido é **P %**
   disso. Essa parte é matemática: não há código que a recupere sem mudar a
   granularidade."*
2. **Contenção** — *"Cada etapa fica **I×** mais lenta em paralelo — e o
   disco está praticamente parado (**D MB** lidos por execução). É CPU em 4
   núcleos físicos, não I/O."*
3. **Overhead** — *"Spawn, coleta e gravação custam cerca de **O s** por
   execução — pequeno."*

Hipóteses (dizer se confirmadas ou refutadas, com os números da tabela):
H1 p = 6 não supera p = 4; H2 disco ≈ 0 em regime quente; H3 LPT ≥ crescente.

**Resposta pronta sobre Karp–Flatt:**
> *"A 'fração sequencial' de Karp–Flatt que o dashboard mostra embute as três
> perdas — não é uma seção serial do código."*

## 7. Histórico e o erro do baseline (1:00)

> *"Transparência: houve três rodadas antes desta campanha. A primeira, de
> junho, foi contaminada pelo OneDrive. A rodada da apresentação anterior
> foi apagada num reset do schema e não tem suporte em banco — não a cito.
> E o dashboard de agosto misturou duas rodadas porque o comparativo dividia
> tudo pelo sequencial mais recente: uma execução de junho apareceu com
> speedup inflado. A correção está na view, na API, nos testes e num script
> que confere os números do documento e dos slides."*

Números exatos do efeito (execução, baseline errado, speedup exibido ×
correto): tabela "Histórico" em `RESULTADOS_BENCHMARK.md`.

## 8. Dashboard — demo (1:30)

Roteiro de cliques:

1. **Visão geral** — KPIs; baseline = mediana da campanha; card da melhor
   configuração (workers · ordem).
2. **SPD → Comparativo** — mediana ± mín–máx; eficiência com uma linha por
   ordem; card de condições de medição; interpretação gerada dos dados.
3. **SPD → Execuções** (histórico) — as rodadas antigas com `pareamento =
   temporal` e a campanha com `suite`.
4. **`/spd/etapas/<id>`** de uma paralela LPT — os anos maiores nos primeiros
   pids: a ordem de submissão visível.
5. (Opcional) **execução ao vivo** `09 --workers 4 --ordem lpt --obs demo`:
   > *"Isto é uma demonstração com API, dashboard e navegador abertos; a
   > medição oficial foi feita em ambiente controlado — a diferença entre
   > este tempo e a mediana oficial é o tamanho do que o ambiente
   > contamina."*

Falas curtas: *"cada gráfico vem da view, sem mock"*; *"o texto de
interpretação é gerado dos dados — se a campanha mudar, ele muda"*.

## 9. Conclusão técnica (0:45)

1. **Paralelismo tem teto e tem custo** — e o teto aqui é de granularidade e
   escalonamento antes de ser de Amdahl.
2. **Medir > supor, três vezes** — OneDrive contaminou o I/O; o baseline
   errado inflou um speedup; a explicação por "disco" não sobreviveu aos
   bytes medidos.
3. **Uma definição, várias telas** — view SQL como fonte única; API,
   dashboard, documento e slides leem a mesma coisa e um script confere.

---

## Perguntas frequentes que a banca pode fazer

**"Por que 24.967 se são só 582 cursos?"**
> As linhas são inscrições (grão do arq1); as 13 colunas são função de
> (ano, curso). A unidade analítica é curso-ano — 582 — e as réplicas atuam
> como peso por matrícula. A view `v_enade_time_curso_ano` tem 582 linhas.

**"E se vocês tivessem mais núcleos físicos?"**
> O ponto ótimo desloca, mas o teto de escalonamento dos 6 anos permanece:
> em p = 6 ele é o tempo do maior ano. Para subir mais é preciso reduzir a
> granularidade (particionar dentro do ano), não só adicionar núcleos.

**"Por que medir duas ordens de submissão?"**
> Porque o executor não balanceia: entrega ao primeiro worker livre na ordem
> de submissão. A diferença entre LPT e crescente é perda de escalonamento
> pura — o código dos workers é o mesmo. Sem medir as duas, essa perda seria
> atribuída erradamente a "overhead".

**"O cache quente não infla o speedup?"**
> Ele afeta sequencial e paralelas igualmente — todas rodam quentes — e está
> declarado. A passada fria é o aquecimento, descartado. O que o cache quente
> mostra é que, em regime, o gargalo é CPU, não disco.

**"Como sabem que os números do speedup estão certos?"**
> Definição única na view; API só lê; `13_validar_metricas.py` e os testes
> recalculam a partir das tabelas; `verificar_numeros.py` confere o documento
> e os slides. E o erro anterior está documentado com os números — foi
> justamente essa checagem que o expôs.

**"O que aconteceria com 8 workers?"**
> Com 6 unidades, dois workers ficam ociosos por construção; o teto é o
> mesmo de 6. Só mediria overhead de spawn — por isso ficou fora da campanha.

**"Por que não Spark/Dask?"**
> O volume final é pequeno; um framework distribuído teria overhead maior que
> o ganho e esconderia exatamente as perdas que o experimento quer expor.
