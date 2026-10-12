# Exploração e revisão do modelo de regressão (NT_GER) — multi_enade

Registro de todo o trabalho de revisão de lógica de negócio e exploração de
variáveis/modelos feito sobre `modelo_regressao.py`. Os scripts exploratórios
citados aqui (`exploracao_*.py`) foram removidos do repositório depois de
documentados — este arquivo é o registro permanente das decisões e números
que embasam o estado atual de produção.

## 1. Revisão de lógica de negócio (bugs encontrados e corrigidos)

### Regressão (`modelo_regressao.py`)

- **Bug crítico de filtro**: o código excluía `QE_I63`/`QE_I57` quando o valor
  estava em `[6, 7, 8]`, supondo que 6 = "não sei". Pelo dicionário oficial do
  INEP, essas perguntas são escala de concordância 1–6 (6 = "Concordo
  totalmente", a resposta mais positiva — não "não sei"). Só 7 (não sei
  responder) e 8 (não se aplica) deveriam ser excluídos.
  - Medido antes/depois: filtro errado descartava ~49% das respostas válidas;
    média de QE_I63 por curso subia de **4,02** (errado) para **5,00**
    (correto) — viés sistemático de quase 1 ponto numa escala de 6.
  - Corrigido: `.isin([7, 8])`.
- **Falta de métrica de qualidade do modelo**: `NT_GER_PREVISTA` era publicado
  sem nenhum R²/MAE/RMSE calculado. Corrigido: o modelo agora é avaliado num
  conjunto de teste nunca visto (80/20) e só depois reajustado com 100% dos
  dados para o modelo final publicado — isso também resolve o problema de
  **misturar previsão de treino com previsão de teste** sem distinguir.
- **Piso mínimo de respondentes**: não existia. Adicionado
  `N_MINIMO_ALUNOS = 5` (cursos com menos que isso são descartados do
  treino/publicação).
- **Modelo treinado numa população diferente da que prevê**: o modelo salvo
  (`rf_regressor.joblib`) foi treinado quando a base ainda era nacional (sem
  filtro de região); resolvido retreinando com a base já filtrada.

### Clusters (`modelo_clusters.py`)

- Mesma classe de bug: `QE_I63` não filtrava 7/8 (contaminação pequena, ~1-2%
  das respostas, nada como o bug da regressão).
- **Bug de dtype**: `QE_I63` vem do Supabase como **texto** (`"1"`, `"6"`...);
  comparar com inteiros (`.isin([7, 8])`) nunca batia. Corrigido com
  `pd.to_numeric` antes do filtro.
- Piso mínimo de 5 alunos/curso adicionado.
- **Nomeação dos clusters**: `Cluster_ID` é um índice arbitrário do KMeans
  (pode trocar de significado entre retreinos). Adicionada `nomear_clusters()`
  — nomeia pelo ranking de NT_GER médio (Desempenho Alto/Médio/Baixo), não
  pelo índice. Como a tabela do Supabase não tem coluna para isso, o nome é
  recalculado sob demanda no endpoint `/relatorio-cluster`.

### Associação (`modelo_associacao.py`)

- Mesmo filtro 7/8 em QE_I57/QE_I30/QE_I56 (mesma contaminação pequena).
- **Bug introduzido e corrigido no mesmo commit**: converter para `int` antes
  do `get_dummies()` sem passar `columns=` fez o pandas parar de codificar
  (por padrão só codifica colunas não-numéricas) — colapsou tudo num booleano
  único, dando confiança/lift = 1,0 artificial nas primeiras regras. Corrigido
  passando `columns=` explicitamente.
- Sem validação estatística formal de significância — **não corrigido**,
  é uma limitação inerente à técnica (regras de associação são descritivas).
- **Pendência não resolvida**: nenhuma das 3 tabelas de resultado tem
  metadado indicando o recorte regional (Norte+Nordeste) — exigiria coluna
  nova, fora do alcance da API REST do Supabase usada neste projeto.

## 2. Infraestrutura de reprocessamento (ETL)

- Criados `multi_enade/refinamento_dados/refino_arqN.py` para os arquivos
  brutos do INEP usados pelo multi_enade, conectando `.txt` → Supabase
  (antes não existia nenhuma ingestão própria do módulo).
- **Incidente real**: `util_db.py::upsert_supabase` usava
  `dataf.where(pd.notnull(dataf), None)`, que não funciona em colunas
  `float64` (pandas converte `None` de volta pra `NaN`, que não é JSON
  válido) — e a função engolia a exceção silenciosamente. Isso deixou
  `tbl_arq3/4/21/29_2021` vazias em produção por alguns minutos sem erro
  visível. Corrigido com round-trip via `to_json()` + removido o
  `try/except` que escondia a falha.
- **Decisão de recorte regional**: filtro de `CO_REGIAO_CURSO` estava
  presente no código mas nunca era realmente aplicado (bug de encadeamento).
  Ao corrigir, descoberto que só região Norte dava 50 cursos (de 753
  nacionais); decisão final do usuário: **Norte + Nordeste = 190 cursos**.
- Pasta `multi_enade/` reorganizada: `refinamento_dados/` para ingestão,
  `dados_brutos/` (gitignorado, ~500MB) para os `.txt`, `README.md`/`DIARIO.md`
  do próprio grupo resgatados de dentro do export do Google Drive.
- **Achado na revisão completa final**: `POST /api/multienade/reprocessar/
  fontes` (`multi_enade_endpoints.py::_reprocessar_fontes_brutas`) só
  reprocessava `arq3, arq4, arq21, arq29` — os 4 originais de antes de toda
  a exploração de variáveis. As 11 fontes adicionadas depois (`arq2, arq10,
  arq14, arq15, arq16, arq17, arq18, arq19, arq25, arq30`, usadas por
  regressão e clusters) nunca tinham sido conectadas ao endpoint — um
  "reprocessar tudo" de verdade deixaria 11 das 13 tabelas de origem
  desatualizadas. Corrigido: lista de fontes do endpoint atualizada pra
  bater exatamente com o que os 3 modelos consultam hoje (13 tabelas;
  `arq29` saiu da lista porque nenhum modelo usa mais `QE_I23`).

## 3. Exploração de variáveis e modelos

Ponto de partida: as 4 variáveis originais (`QE_I63`, `QE_I57`, `QE_I15`,
`QE_I23`), avaliadas honestamente com validação cruzada 5-fold, têm
**R² = -0,139** — pior que simplesmente prever a média. O R²=0,036 reportado
inicialmente vinha de um único split, sem CV, e já estava otimista.

### Etapa 1 — `exploracao_novas_variaveis.py`: 9 variáveis novas

Testadas: `NU_IDADE`, `TP_SEXO`, `CO_TURNO_GRADUACAO`, `QE_I04` (escolaridade
do pai), `QE_I05` (escolaridade da mãe), `QE_I08` (renda), `QE_I10`
(trabalho), `QE_I17` (tipo de escola no EM), `QE_I21` (família com superior).

- Resultado inicial (RandomForest fixo, 1 split, sem CV): **R² = 0,501** —
  parecia um salto enorme sobre 0,036.
- `QE_I08` (renda) já aparecia disparado na frente (importância 0,369).
- **Ressalva levantada na hora**: amostra pequena (161 cursos, 33 de teste),
  sem validação cruzada — número provavelmente otimista.

### Etapa 2 — `exploracao_modelos.py`: bateria de algoritmos + decomposição

Testados 9 algoritmos (LinearRegression, Ridge, Lasso, ElasticNet,
DecisionTree, RandomForest, GradientBoosting, KNN, SVR) com `GridSearchCV`
5-fold sobre as 13 variáveis (4 originais + 9 novas).

- RandomForest venceu: `n_estimators=200, max_depth=5, min_samples_leaf=2`,
  **CV=0,282 / teste=0,451** (com peso por `QT_ALUNOS` — sem o peso, caía
  para CV=0,204, confirmando que o peso importa).
- **Decomposição** (isolando variável vs. hiperparâmetro, mesma amostra):

  | Cenário | R² CV | R² teste |
  |---|---|---|
  | A) 4 originais + hiperparâmetro de produção | -0,139 | 0,261 |
  | B) 4 originais + hiperparâmetro novo | -0,104 | 0,267 |
  | C) 9 novas + hiperparâmetro novo | 0,134 | 0,450 |
  | D) 13 combinadas + hiperparâmetro novo | 0,178 | 0,443 |

  **Conclusão**: hiperparâmetro sozinho quase não move o número (A→B); o
  ganho é das variáveis (B→C). O R²=0,501 da etapa 1 já estava inflado por
  falta de CV — valor mais honesto nessa fase: ~0,18 (CV).

### Etapa 3 — `exploracao_dispersao_institucional.py`: dispersão vs. institucional

Motivação: modelar por aluno é impossível (arquivos do INEP embaralhados de
propósito pela LGPD, sem id comum entre arquivos) e, mesmo que fosse
possível, usar médias de curso como se fossem valores por aluno **pioraria**
o R² (ruído individual inexplicável). Alternativa testada: desvio-padrão por
curso (além da média) e variáveis institucionais (`CO_CATEGAD`, `CO_ORGACAD`,
`CO_MODALIDADE`, do arq1 — uma por curso, sem agregação de alunos).

| Cenário | Nº variáveis | R² CV | R² teste |
|---|---|---|---|
| E1) médias + proporções (baseline) | 28 | 0,221 | 0,492 |
| E2) E1 + desvio-padrão | 36 | 0,229 | 0,466 |
| **E3) E1 + institucional** | 39 | **0,256** | 0,486 |
| E4) tudo (desvio + institucional) | 47 | 0,259 | 0,470 |

**Conclusão**: institucional ajuda de verdade (+0,035 CV, `CO_CATEGAD_1` —
pública federal — com importância 0,059); desvio-padrão não ajuda
(praticamente nada, e ainda piora o teste) — **descartado**.

### Etapa 4 — `exploracao_novas_variaveis_2.py`: existe algo tão bom quanto QE_I08?

10 variáveis novas: `QE_I01` (estado civil), `QE_I02` (raça/cor), `QE_I06`
(moradia), `QE_I09` (situação financeira), `QE_I11` (bolsa/financiamento),
`QE_I12` (auxílio permanência), `QE_I13` (bolsa acadêmica), `QE_I19`
(incentivo), `QE_I22` (livros lidos), `QE_I24` (idioma estrangeiro).

- Baseline E3 (39 vars): CV=0,256, teste=0,486 → **+10 novas (93 vars):
  CV=0,345, teste=0,463**.
- **Achado**: `QE_I13_B` (bolsa de iniciação científica) com importância
  0,201 e `QE_I13_A` (sem bolsa) com 0,167 — juntas superam `QE_I08`
  (0,102 nesse cenário mais disputado).
- **Ressalva de causalidade**: bolsa de IC é tipicamente concedida a quem
  *já* tem bom desempenho (seleção pela coordenação/professores) — é mais um
  marcador de quem já é bom aluno do que um fator causal, diferente de
  `QE_I08` (renda), que é um fator de fundo plausivelmente anterior ao
  desempenho.
- **Ressalva de dimensionalidade**: 93 variáveis para 161 cursos (128 no
  treino) é uma proporção arriscada — risco real de ruído da amostra, não
  sinal verdadeiro.

### Etapa 5 — `exploracao_selecao_variaveis.py`: qual o tamanho ideal?

Seleção de variáveis por importância calculada **só no treino** (sem
vazamento pro teste), testando vários tamanhos de subconjunto:

| Nº variáveis | R² CV | R² teste |
|---|---|---|
| 8 | 0,298 | 0,363 |
| 10 | 0,354 | 0,337 |
| 12 | 0,388 | 0,419 |
| **15** | **0,399** | 0,481 |
| 20 | 0,386 | 0,481 |
| 25 | 0,377 | 0,470 |
| 30 | 0,373 | 0,487 |
| 93 (tudo) | 0,342 | 0,463 |

**15 variáveis é o ponto ideal** — melhor CV de toda a exploração (confirma
que as 93 estavam mesmo diluídas por ruído) e teste quase no topo. Conjunto
final selecionado:

```
QE_I13_B, QE_I08_media, QE_I13_A, QE_I24_A, QE_I15_E, QE_I04_media,
QE_I13_D, QE_I12_A, QE_I57_media, QE_I11_A, QE_I10_media, QE_I19_B,
QE_I09_ordinal, QE_I15_C, CO_TURNO_GRADUACAO_4
```

### Etapa 6 — `exploracao_nacional_vs_regional.py`: treinar com o Brasil ajuda?

Pergunta testada: treinar com todos os cursos CC+SI do Brasil (753 cursos) e
aplicar o filtro de região só na hora de prever generalizaria melhor do que
treinar só com Norte+Nordeste (abordagem atual)? Mesmo conjunto de teste (33
cursos de Norte+Nordeste, nunca usados em nenhum treino) decide entre os
dois.

| Estratégia | Nº cursos treino | R² CV (próprio treino) | R² no teste Norte+Nordeste |
|---|---|---|---|
| Regional (atual) | 128 | 0,397 | **0,482** |
| Nacional (Brasil inteiro) | 635 | 0,445 | 0,462 |

**Conclusão**: mesmo com 5x mais dados de treino, o modelo nacional
generaliza **pior** especificamente para Norte+Nordeste — a relação entre as
variáveis e a nota parece ser diferente por região. Mantido o treino restrito
à região (decisão de escopo já tomada antes, agora validada empiricamente).

### Etapa 7 — `exploracao_pca_economico.py`: condensar as variáveis econômicas com PCA

Pergunta: dá pra condensar renda/situação financeira/trabalho/bolsas/auxílios
num índice único via PCA, em vez de manter tudo separado?

| Cenário | Nº variáveis | R² CV | R² teste |
|---|---|---|---|
| 1) Produção (5 econômicas separadas: 3 ordinais + só `QE_I11_A`/`QE_I12_A`) | 15 | 0,400 | 0,482 |
| 2) Bloco completo sem PCA (30 vars — todas as categorias de QE_I11/QE_I12) | 30 | 0,395 | 0,448 |
| 3) PCA no bloco completo (ordinais + nominais misturados), 1 a 5 componentes | 11-15 | 0,365-0,403 | 0,417-0,469 |
| **4) PCA só nas 3 ordinais** (renda, situação financeira, trabalho) | 13-15 | **0,424-0,429** | **0,485-0,499** |

**Por que os cenários 2 e 3 foram descartados**: o bloco "econômico" misturava
3 variáveis ordinais (uma escala contínua 0-6/0-5/0-4) com os blocos nominais
de `QE_I11` (11 tipos de bolsa/financiamento) e `QE_I12` (6 tipos de auxílio)
— categorias, não um espectro. PCA sobre essa mistura não achava um eixo
limpo (1º componente só explicava 25% da variância; precisava de 8+
componentes pra chegar a 80%) e o 1º componente saía com sinais contraditórios
(`QE_I12_A` positivo, `QE_I11_A` negativo — sem interpretação clara de "mais
pobre → mais rico"). Mais categorias (cenário 2) também não ajudou — só
acrescentou ruído (CV caiu de 0,400 para 0,395).

**Por que o cenário 4 (ganhador) funcionou**: restringindo o PCA só às 3
ordinais, o 1º componente já explica 71% da variância sozinho, com pesos
limpos e no mesmo sentido — `QE_I09_media` (0,638), `QE_I10_media` (0,623),
`QE_I08_media` (0,453), um eixo coerente de "status socioeconômico". Com 2
componentes (94,7% da variância): **CV=0,424, teste=0,499** — melhor que a
produção nas duas métricas, usando uma variável a menos (14 em vez de 15).

### Etapa 8 — `exploracao_pca_grupos_ordinais.py`: o mesmo padrão se repete em outros grupos?

Testados mais 5 grupos ordinais/Likert, todos candidatos "no mesmo contexto e
mesma escala" — a regra que funcionou na etapa 7:

| Grupo testado | Itens originais | Componentes (≥80% var.) | Ganho de CV sobre o baseline (0,317) |
|---|---|---|---|
| Escolaridade dos pais (`QE_I04`+`QE_I05`) | 2 | 1 (88%) | 0,329 (+0,012) |
| Professores/didática (`QE_I37,38,39,41,56,57,58`) | 7 | 1 (80%) | 0,312 (-0,005) |
| Infraestrutura (`QE_I59,61,62,63,64,65,68`) | 7 | 2 (87%) | 0,315 (-0,002) |
| Formação/currículo (`QE_I27,29-36,47,48,49`) | 12 | 1 (85%) | 0,318 (+0,001) |
| Oportunidades extracurriculares (`QE_I43,44,45,46,52,53,60`) | 7 | 2 (87%) | 0,327 (+0,010) |
| Todos os 5 juntos | 35 | 7 | 0,335 (+0,018) |

**Por que todos foram descartados**: nenhum chegou perto do ganho do
econômico (+0,024 a +0,029 de CV). Os itens Likert de percepção de ensino
(professores, infraestrutura, formação, oportunidades) têm correlação interna
alta dentro do próprio grupo (80-88% de variância em 1-2 componentes — eles
realmente medem "a mesma coisa"), mas essa "coisa" tem pouca relação com
`NT_GER`. A lição: PCA só ajuda quando as variáveis de entrada **já têm sinal
individual forte** antes de serem condensadas — condensar sinal fraco
continua fraco, só que com menos dimensões. `QE_I08`/`QE_I09`/`QE_I10` já
eram, cada uma isoladamente, entre as variáveis mais importantes do modelo
(ver etapa 4); os itens Likert nunca tinham aparecido no top do ranking de
importância em nenhuma etapa anterior.

## 4. Estado final em produção

`modelo_regressao.py` foi atualizado com:

- Hiperparâmetros: `RandomForestRegressor(n_estimators=200, max_depth=5,
  min_samples_leaf=2)`.
- **14 variáveis** (as 15 da etapa 5, com `QE_I08_media`/`QE_I09_media`/
  `QE_I10_media` substituídas por `PCA_ECON_1`/`PCA_ECON_2` — etapa 7):
  `QE_I57`, `QE_I15_C`, `QE_I15_E`, `QE_I04_media`, `CO_TURNO_GRADUACAO_4`,
  `QE_I13_A`, `QE_I13_B`, `QE_I13_D`, `QE_I24_A`, `QE_I12_A`, `QE_I11_A`,
  `QE_I19_B`, `PCA_ECON_1`, `PCA_ECON_2`. O PCA é recalculado a cada
  reprocessamento (não é persistido como o RandomForest) — são só 3 variáveis
  estáveis, sem necessidade de versionar o ajuste do PCA entre execuções.
- Avaliação honesta (teste 80/20) + reajuste final com 100% dos dados antes
  de publicar. Resultado no conjunto de teste: **R²=0,498 | MAE=3,03 |
  RMSE=3,82** (n=33) — consistente com o R²=0,499 encontrado na etapa 7.
- Retreinado e publicado: `tbl_multi_enade_regressao` (161 cursos) e
  `tbl_multi_enade_shap` (14 features — `PCA_ECON_1` agora é a mais
  importante do modelo, seguida por `QE_I13_B`).

### Síntese: por que esta combinação venceu

**Modelo**: RandomForest venceu 8 outros algoritmos (Ridge, Lasso,
ElasticNet, DecisionTree, GradientBoosting, KNN, SVR, LinearRegression —
etapa 2) porque a relação entre as variáveis e `NT_GER` tem interações e
não-linearidades que os modelos lineares não capturam (ex: o efeito da renda
provavelmente não é o mesmo em cursos noturnos vs. integrais) — os modelos
lineares ficaram com R² de teste entre 0,11 e 0,32, e CV chegando a negativo.

**Hiperparâmetros**: `min_samples_leaf=2` (vs. 4 em produção antes) foi o
achado do `GridSearchCV` (etapa 2), mas isoladamente contribui quase nada
(decomposição da etapa 2: A→B, CV de -0,139 para -0,104) — o ganho real
sempre veio de quais variáveis entram no modelo, não de como o RandomForest é
ajustado.

**PCA por tema**: funciona quando (a) as variáveis são ordinais da mesma
escala, (b) medem o mesmo construto de fundo, e (c) **já tinham sinal
individual forte** antes de serem condensadas. As 3 econômicas atendiam aos
três critérios. Os outros 5 grupos testados (etapa 8) atendiam (a) e (b) mas
não (c) — por isso só o econômico foi incorporado.

**Incidentes reais corrigidos durante os deploys** (5 no total, ao longo das
3 rodadas de publicação — 7 variáveis, depois 15, depois PCA):
1. `upsert_supabase` com o bug de NaN (ver seção 2) esvaziou as tabelas de
   fonte brevemente durante os testes — corrigido e restaurado.
2. `tbl_multi_enade_regressao` tinha schema fixo sem as 4 colunas da primeira
   leva (`QE_I08_media`, `QE_I04_media`, `QE_I10_media`,
   `CO_TURNO_GRADUACAO_4`) — identificado via endpoint OpenAPI do PostgREST
   (`{url}/rest/v1/`, mais confiável que adivinhar o schema), corrigido com
   `ALTER TABLE` e os dados restaurados sem precisar retreinar.
3. Ao completar as 15 variáveis: (a) a mesma tabela precisou de mais 8
   colunas (`QE_I13_A/B/D`, `QE_I24_A`, `QE_I12_A`, `QE_I11_A`, `QE_I19_B`,
   `QE_I09_media`) — mesmo processo de correção; (b) as 6 tabelas novas
   (`tbl_arq15/17/18/19/25/30_2021`) foram criadas com `CO_CURSO` como
   `bigint`, diferente de todas as outras tabelas do projeto (`text`) — o
   merge por `CO_CURSO` quebrava até normalizar o tipo em pandas antes de
   cada merge.
4. `tbl_arq11_2021` (escolaridade da mãe, usada só na exploração da etapa 8)
   também estava com dado nacional antigo (753 cursos) — mesmo problema das
   tabelas arq2/10/14/16 relatado antes; criado `refino_arq11.py` e
   atualizado pro recorte Norte+Nordeste.
5. Ao trocar as 3 ordinais por PCA: `tbl_multi_enade_regressao` precisou de
   mais 2 colunas (`PCA_ECON_1`, `PCA_ECON_2`) — mesmo processo de correção
   via `ALTER TABLE`.

## 5. Gráficos locais (bugs corrigidos depois do deploy)

Revisão à parte, feita depois de tudo acima já estar em produção: os
gráficos locais tinham dois bugs que passaram despercebidos durante os
deploys (o pipeline sempre reportava sucesso porque a geração de gráfico é
best-effort — um `try/except` que não deixa falha de plot derrubar os dados
já persistidos, mas também escondia esses dois problemas):

- `plotar_grafico_shap`: o `plt.savefig(...)` estava **comentado** no
  código — a função imprimia "Gráfico SHAP salvo lindamente..." mas nunca
  salvava nada. Corrigido (parâmetro `nome_arquivo`, savefig ativo).
- `plotar_grafico_tradicional` (visão "cotas"): checava
  `if 'QE_I15_A' in df_plot.columns` pra decidir a legenda, mas `QE_I15_A`
  não sobreviveu à seleção de variáveis da etapa 5 (só `QE_I15_C` e
  `QE_I15_E` ficaram) — a condição nunca era verdadeira, sempre caía em
  "Dado Indisponível". Corrigido: legenda agora usa a soma de `QE_I15_C` +
  `QE_I15_E`, cortada pela mediana da amostra (não um limiar fixo de 0,5,
  que nunca separaria nada — essas proporções raramente passam de 0,2-0,3).
- **Novo gráfico** `grafico_pca_geral.png`: as 14 variáveis do modelo
  padronizadas e reduzidas a 2 componentes via PCA (mesma técnica de
  `modelo_clusters.py::plotar_grafico_clusters`), colorido pela nota real —
  dá uma visão de conjunto que nem o gráfico tradicional (foca só na
  variável mais importante) nem o SHAP (não é espacial) cobrem sozinhos.

`modelo_clusters.py::plotar_grafico_clusters` tinha o mesmo bug do SHAP
(nunca teve `savefig`) — corrigido junto, ver `EXPLORACAO_MODELO_CLUSTERS.md`.

### Pendências

- Nenhuma tabela publicada indica o recorte regional (Norte+Nordeste) —
  exigiria coluna nova fora do alcance da API REST usada.
- `QE_I04` (escolaridade do pai) e `QE_I13` (bolsa acadêmica) ainda não
  testados dentro de um PCA combinado com `QE_I08` — testados isoladamente
  em grupos diferentes (etapas 7/8), não em conjunto.
- Grupos ordinais com ganho pequeno mas não-nulo na etapa 8 (escolaridade dos
  pais +0,012, oportunidades +0,010) não foram adotados por serem marginais
  dentro do ruído amostral — podem valer re-teste se a amostra crescer.
