# Respostas às lacunas do artigo — multi_enade

Respostas às perguntas de `lacunas.txt`, baseadas **somente** no que está no módulo `multi_enade/` (código, CSVs de resultado, `DIARIO.md` e os três `EXPLORACAO_MODELO_*.md`). Onde a informação **não está registrada** em lugar nenhum, está escrito explicitamente — nada foi inventado.

---

## 1. Dados gerais da base utilizada

**Recorte (confirmado no código).** `refinamento_dados/util_etl.py::obter_cursos_recorte` filtra o arq1 por `CO_GRUPO ∈ {4004, 4006}` e `CO_REGIAO_CURSO ∈ {1, 2}` (1 = Norte, 2 = Nordeste). Todos os arquivos são do **Enade 2021** (`microdados2021_arqN.txt`, tabelas `tbl_arqN_2021`).

- **Ano:** 2021 — confirmado.
- **Regiões:** Norte + Nordeste — confirmado (decisão registrada em `EXPLORACAO_MODELO_REGRESSAO.md`, §2).
- **Cursos:** os códigos de grupo 4004 e 4006 são os de Ciência da Computação e Sistemas de Informação, mas o código **só traz os números**, não os nomes. Vale conferir 4004/4006 no dicionário oficial (`dados_brutos/documentacao/Dicionário_arquivos_variáveis_microdados_Enade_2021.xlsx`) antes de escrever no artigo.

**Quantidades exatas:**

| Etapa | Quantidade | Fonte |
|---|---|---|
| Cursos após o recorte (tabelas de origem) | **190** | `EXPLORACAO_MODELO_REGRESSAO.md` §2 e `DIARIO.md` |
| Cursos com ≥ 5 respondentes (`N_MINIMO_ALUNOS = 5`), usados em regressão e clusters | **161** | CSVs de resultado (161 linhas) |
| Alunos nos 161 cursos (soma de `QT_ALUNOS`, onde `QT_ALUNOS` = nº de alunos com `NT_GER` válida) | **4.467** | soma de `QT_ALUNOS` em `dados_clusters_treinado.csv` |
| Alunos na associação | **≈ 4.657** (ver ressalva) | ver abaixo |

> **Ressalva sobre os alunos da associação.** O número **exato não está registrado**. O único dado disponível vem da validação em metades: duas metades de ~2.328 e ~2.329 alunos (`EXPLORACAO_MODELO_ASSOCIACAO.md`), ou seja ≈ 4.657. Esse valor é o de alunos do arq4 com os 6 itens Likert válidos (sem 7/8) **e** com banda de desempenho do curso — a diferença para 4.467 é esperada, porque a associação usa o arq4 por aluno (sem o piso de 5 respondentes por curso e sem a exigência de `NT_GER` por aluno). Para obter o número exato, basta imprimir `len(base)` em `preparar_dados_associacao` (`modelo_associacao.py`) depois do `dropna`.

**Arquivos (tabelas Supabase) que entraram em cada modelo** (conferido nos `consultar_dados(...)` do código):

| Modelo | Tabelas de origem |
|---|---|
| Regressão | `arq2, arq3, arq4, arq10, arq14, arq15, arq16, arq17, arq18, arq19, arq21, arq25, arq30` (13 tabelas) |
| Clustering | `arq3` (desempenho), `arq4` (infraestrutura, `QE_I63`), `arq21` (cotas, `QE_I15`), `arq17` (bolsa/financiamento, `QE_I11`) |
| Associação | `arq4` (6 itens Likert) e `arq3` (só para a banda de desempenho do curso) |

> O endpoint `/reprocessar/fontes` foi corrigido para bater com estas 13 tabelas (ver `DIARIO.md`, 04/10 — continuação 4). O arq1 só entra no recorte (e como variável institucional na exploração da regressão); o arq29 (`QE_I23`) **não é mais usado** por nenhum modelo.

---

## 2. Resultado final da associação — as 4 regras de desempenho

Configuração final (`modelo_associacao.py`): 6 itens Likert + banda de desempenho do curso, `suporte_minimo = 0,03`, `confianca_minima = 0,5`, máximo de 3 itens por regra, limite de 50 publicadas. Funil: **2.417 regras → 377 simples → 50 publicadas → 4 envolvendo desempenho**.

As 4 regras abaixo foram extraídas de `modelos/mdl_associacao/dados_associacao_resultado.csv` (arquivo da configuração final: itens `QE_I57, QE_I61, QE_I34, QE_I44, QE_I30, QE_I56`). Suporte e confiança em %.

| # | Antecedente | Consequente | Suporte | Confiança | Lift |
|---|---|---|---|---|---|
| 1 | `desempenho_baixo` + `metodologia_inovadora_5` | `formacao_critica_5` | 3,95 | 54,44 | 2,127 |
| 2 | `desempenho_baixo` + `oportunidades_ic_5` | `profs_disponibilidade_5` | 3,63 | 52,32 | 1,997 |
| 3 | `desempenho_baixo` + `profs_disponibilidade_5` | `professores_dominio_5` | 4,44 | 57,98 | 1,957 |
| 4 | `desempenho_baixo` + `professores_dominio_5` | `profs_disponibilidade_5` | 4,44 | 50,74 | 1,937 |

Itens: `metodologia_inovadora` = `QE_I30`, `formacao_critica` = `QE_I34`, `oportunidades_ic` = `QE_I44`, `profs_disponibilidade` = `QE_I56`, `professores_dominio` = `QE_I57`. O nível 5 é "concordo" na escala 1–6.

**Pontos que precisam estar claros no artigo (para não superinterpretar):**

1. **As quatro regras têm `desempenho_baixo` como parte do *antecedente*, não como consequente.** Elas **não** dizem "percepção X → desempenho baixo". Dizem: dentro de cursos de desempenho baixo, quem concorda com X tende a concordar também com Y. Ou seja, são regras de efeito-halo (percepção ↔ percepção) *condicionadas* à banda de desempenho — não regras que preveem desempenho.
2. **Nenhuma das 4 é de percepção → desempenho.** O resultado "percepção → desempenho" que a exploração identificou como mais robusto (ancorado em `oportunidades_ic_6`, nível 6, desempenho alto) vem do conjunto de 10 regras do "sweet spot" validado em duas metades — **não** das 4 publicadas.
3. **A validação por amostras independentes (6 de 13/9 regras replicaram) foi feita para o conjunto de 10 regras do sweet spot, e não para estas 50/4 regras publicadas** (limitação já registrada em `EXPLORACAO_MODELO_ASSOCIACAO.md`). Portanto as 4 regras acima **não foram individualmente validadas por repetição**.
4. O lift 1,94–2,13 aqui é inflado pelo efeito-halo entre percepções; o lift de regressões do tipo percepção → desempenho foi bem menor (≈ 1,08–1,19 por item isolado, até ~1,40 em combinações).
5. O `dados_associacao_binario.csv` e o `dados_associacao_resultado.csv` atuais já são os da configuração final; as regras antigas (`QE_I30`, `QE_I56`, `QE_I57` apenas, 7 regras, lift 1,5–1,8) **não estão mais nesses arquivos**. Se o CSV que foi enviado antes mostra `QE_I30/I56/I57` como as únicas variáveis, é o do modelo antigo e não deve ser misturado.

---

## 3. SHAP / importância da regressão — resultado final

`modelos/mdl_regressao/dados_shap_importancia.csv` é o **resultado final** (14 variáveis do modelo de produção, pós-PCA econômico; publicado em `tbl_multi_enade_shap`). Coluna `importancia_media` do arquivo.

| # | Variável | Importância | Descrição |
|---|---|---|---|
| 1 | `PCA_ECON_1` | 1,735 | 1º componente do PCA econômico (renda `QE_I08`, situação financeira `QE_I09`, trabalho `QE_I10`) — eixo de "status socioeconômico" |
| 2 | `QE_I13_B` | 1,514 | Bolsa de iniciação científica |
| 3 | `QE_I13_A` | 1,072 | Sem bolsa acadêmica |
| 4 | `QE_I24_A` | 0,503 | Idioma estrangeiro (`QE_I24`, categoria A) |
| 5 | `QE_I04_media` | 0,449 | Escolaridade do pai (média do curso) |
| 6 | `QE_I15_E` | 0,358 | Cota/ingresso (`QE_I15`, categoria E) |
| 7 | `CO_TURNO_GRADUACAO_4` | 0,354 | Turno do curso (noturno) |
| 8 | `QE_I57` | 0,352 | Professores demonstraram domínio do conteúdo |
| 9 | `QE_I19_B` | 0,280 | Incentivo (`QE_I19`, categoria B) |
| 10 | `PCA_ECON_2` | 0,265 | 2º componente do PCA econômico |
| 11 | `QE_I13_D` | 0,237 | Bolsa acadêmica (`QE_I13`, categoria D) |
| 12 | `QE_I11_A` | 0,173 | Nenhuma bolsa de financiamento, curso gratuito |
| 13 | `QE_I12_A` | 0,113 | Auxílio permanência (`QE_I12`, categoria A) |
| 14 | `QE_I15_C` | 0,078 | Cota/ingresso (`QE_I15`, categoria C) |

Rótulos das categorias (`_A`, `_B`, ...) estão no dicionário oficial; confira antes de nomeá-las no artigo, pois aqui só foi registrado o que consta na documentação do projeto.

**Desempenho do modelo final** (teste 80/20, n = 33 cursos; `metricas_regressao.csv`): **R² = 0,498 | MAE = 3,03 | RMSE = 3,82**. Treino: 128 cursos. Validação cruzada 5-fold na exploração: R² ≈ 0,42–0,43.

Ressalvas já registradas: (i) `QE_I13_B` (bolsa de IC) é mais marcador de bom aluno do que fator causal; (ii) o conjunto de teste é pequeno (33 cursos), então o R² tem incerteza grande; (iii) a unidade é o curso.

---

## 4. Clusters: como o k = 3 foi escolhido

**Resposta honesta: não há registro de uma comparação entre valores de k.**

- No código, `num_clusters` é parâmetro com **valor padrão 3** (`treinar_e_salvar_clusters(..., num_clusters=3)`; o endpoint de reprocessamento também usa `num_clusters: int = 3`). Todos os cenários testados em `EXPLORACAO_MODELO_CLUSTERS.md` mantêm k = 3 fixo e variam **o conjunto de variáveis** (com/sem `NT_GER`, + renda, + bolsa), não o k.
- Os nomes "Desempenho Alto/Médio/Baixo" (`nomear_clusters`) existem **porque** k = 3 (rótulos fixos para 3 grupos); para outros k o código usa "Grupo i (desempenho)". Ou seja, k = 3 foi definido **previamente**, e a nomenclatura foi construída em torno dele.
- O silhouette de 0,211 é o do k = 3 com 23 variáveis; **nenhum silhouette para outros k foi calculado/documentado**. Não há curva de cotovelo nem comparação de silhouette entre k.
- O cenário "+ renda + bolsa" gerou um cluster com apenas 8 cursos (instável) e foi descartado por isso — é o único registro de decisão ligada a tamanho de cluster, mas é sobre conjunto de variáveis, não sobre k.

**Como redigir em Métodos sem faltar com a verdade:** "O número de clusters foi fixado em k = 3 a priori, para permitir uma leitura em três níveis de desempenho (alto, médio, baixo); a qualidade da partição foi avaliada pelo coeficiente de silhouette (0,211)." Se quiser sustentar a escolha com dados, é preciso **rodar uma varredura de k (por exemplo 2 a 8, silhouette + inércia)** — isso ainda não foi feito e é rápido de fazer sobre `dados_clusters.csv`.

Além disso, o silhouette de 0,211 é baixo (estrutura de cluster fraca a moderada); o artigo deve apresentá-lo como tal. O cluster "Médio" é pequeno (16 cursos, 248 alunos).

---

## 5. Perfil final dos clusters

Calculado a partir de `modelos/mdl_clusters/dados_clusters_treinado.csv` (161 cursos, 23 variáveis de entrada: `QE_I63` ×6, `QE_I15` ×6, `QE_I11` ×11). Valores = média, entre os cursos do cluster, da proporção de alunos que marcaram cada categoria. `NT_GER` **não** entra na formação dos clusters; só nomeia/perfila.

| | Alto | Médio | Baixo |
|---|---|---|---|
| Cursos | 73 | 16 | 72 |
| Alunos (soma de `QT_ALUNOS`) | 2.461 | 248 | 1.758 |
| `NT_GER` médio dos cursos | 39,80 | 37,57 | 34,75 |
| Silhouette (geral) | 0,211 | | |

**Variáveis que mais diferenciam os grupos** (ranking pela amplitude entre o maior e o menor cluster):

| Rank | Variável | Alto | Médio | Baixo | Amplitude | Leitura |
|---|---|---|---|---|---|---|
| 1 | `QE_I11_A` | 97,1% | 0,2% | 0,5% | 0,969 | Nenhuma bolsa, curso gratuito (indicador de curso público) |
| 2 | `QE_I11_B` | 0,2% | 11,7% | 31,3% | 0,311 | Nenhuma bolsa, curso pago |
| 3 | `QE_I15_A` | 63,5% | 52,0% | 82,4% | 0,305 | Ampla concorrência (sem cota) |
| 4 | `QE_I11_D` | 0,0% | 23,4% | 2,1% | 0,233 | Categoria D de bolsa/financiamento |
| 5 | `QE_I11_C` | 0,2% | 23,1% | 13,6% | 0,229 | Categoria C de bolsa/financiamento |
| 6 | `QE_I63_6` | 38,9% | 61,8% | 58,9% | 0,229 | Infraestrutura "concordo totalmente" |
| 7 | `QE_I15_D` | 13,3% | 26,7% | 5,8% | 0,208 | Categoria D de cota |
| 8 | `QE_I11_H` | 1,9% | 5,6% | 20,6% | 0,188 | Categoria H de bolsa/financiamento |
| 9 | `QE_I11_E` | 0,0% | 14,9% | 18,1% | 0,181 | Categoria E de bolsa/financiamento |
| 10 | `QE_I11_F` | 0,0% | 18,0% | 0,8% | 0,180 | Categoria F de bolsa/financiamento |

**Leitura para a discussão** (apenas o que os números sustentam):

- O Cluster **Alto** é quase inteiramente de cursos gratuitos (97% `QE_I11_A`), com a **menor** nota de infraestrutura "concordo totalmente" (38,9% vs. ~59–62%) e mais diversidade de cotas que o Baixo (63,5% vs. 82,4% de ampla concorrência).
- O Cluster **Baixo** concentra cursos pagos sem bolsa (31%) e mais ampla concorrência (82%).
- O Cluster **Médio** (16 cursos) tem perfil misto de financiamento (categorias C, D, F) e a maior proporção da categoria D de cota.
- **A separação é essencialmente institucional (público-gratuito vs. privado-pago) e não pedagógica** — mesmo fator que aparece como `CO_CATEGAD_1` na regressão. Infraestrutura mais bem avaliada **não** corresponde a maior desempenho (padrão não monotônico, já registrado em `EXPLORACAO_MODELO_CLUSTERS.md`).
- Os rótulos das categorias `QE_I11_C/D/E/F/H` e `QE_I15_D` precisam ser consultados no dicionário oficial; o projeto só documentou `QE_I11_A` e `QE_I11_B` explicitamente.

---

## 6. Caracterização do corpus e das variáveis

| Modelo | Unidade de análise | Alvo | Principais variáveis |
|---|---|---|---|
| Regressão (RandomForest, `n_estimators=200, max_depth=5, min_samples_leaf=2`, ponderada por `QT_ALUNOS`) | **Curso** (161 cursos) | `NT_GER` (média do curso) | **14 variáveis**: `PCA_ECON_1`, `PCA_ECON_2`, `QE_I13_A/B/D`, `QE_I24_A`, `QE_I04_media`, `QE_I15_C/E`, `CO_TURNO_GRADUACAO_4`, `QE_I57`, `QE_I19_B`, `QE_I11_A`, `QE_I12_A` |
| Clustering (K-Means, k = 3, padronizado com `StandardScaler`, 2D via PCA só para gráfico) | **Curso** (161 cursos) | — (não supervisionado; `NT_GER` só nomeia os grupos) | **23 variáveis**: proporções de `QE_I63` (infraestrutura, 6 níveis), `QE_I15` (cotas, 6), `QE_I11` (bolsa/financiamento, 11) |
| Associação (Apriori, suporte 0,03, confiança 0,5, ≤ 3 itens/regra) | **Aluno**, com a **banda de desempenho do curso** anexada via `CO_CURSO` (tercis de `NT_GER` médio do curso) | Regras (sem alvo supervisionado) | **6 itens Likert** (`QE_I57, QE_I61, QE_I34, QE_I44, QE_I30, QE_I56`) **+ banda de desempenho** (baixo/médio/alto) |

**Observação metodológica importante:** regressão e clustering operam sobre **médias/proporções por curso**; a associação opera sobre **respostas de alunos**, e o desempenho que entra nela é uma característica do **curso** repetida para todos os seus alunos — não a nota individual. Os arquivos do INEP são embaralhados de forma independente (LGPD), então não existe chave comum aluno-a-aluno entre arquivos; `CO_CURSO` é a única chave compartilhada. Esse é o motivo estrutural para modelar por curso e para a associação só combinar itens do mesmo arquivo.

---

## 7. Avaliação do artefato em sentido DSR

**Não há, em nenhum material do módulo, avaliação com especialistas/usuários** (entrevista, questionário, teste de usabilidade, avaliação de interpretabilidade ou utilidade percebida). O que existe no repositório é inteiramente **avaliação computacional/empírica**:

- Regressão: divisão treino/teste 80/20, validação cruzada 5-fold, `GridSearchCV`, comparação de 9 algoritmos, decomposição variável vs. hiperparâmetro, comparação nacional vs. regional, seleção de variáveis sem vazamento, R²/MAE/RMSE.
- Clusters: silhouette; comparação com/sem `NT_GER` e com/sem renda/bolsa.
- Associação: varredura suporte × confiança, validação em duas amostras independentes, análise de impossibilidade estrutural de suporte 0,6.
- Artefato de software: 4 endpoints de relatório e 3 de reprocessamento testados ponta a ponta (`DIARIO.md`, revisão final de 04/10).

**Recomendação para o artigo:** descrever como *avaliação computacional e empírica do artefato*; **não** afirmar validação por especialistas nem avaliação de usabilidade/utilidade. Se quiserem incluir a dimensão de utilidade, precisarão realizar uma rodada de avaliação (por exemplo, apresentar os relatórios a 3–5 pesquisadores/coordenadores com um questionário curto) — e isso ainda não aconteceu.

---

## 8. Procedimento da revisão bibliográfica

**Não há registro no módulo `multi_enade/`.** `README.md` e `DIARIO.md` descrevem problema, dados e decisões de modelagem; nenhum deles lista bases consultadas, termos de busca, período ou critérios de inclusão/exclusão (as referências e os achados de literatura estão fora desta pasta). Nada foi inventado aqui.

Se a revisão for **narrativa** (como a lacuna sugere), basta apresentar: objetivo da revisão, fontes principais consultadas e critério geral de seleção, sem o formalismo de revisão sistemática. Se quiserem apresentá-la como etapa estruturada, os autores precisam informar: bases (por exemplo Scopus, Google Scholar, SciELO), strings de busca, período, critérios de inclusão/exclusão e número de trabalhos em cada etapa.

---

## Resumo das pendências reais

| # | Item | Situação |
|---|---|---|
| 1 | Nº exato de alunos na associação | **Faltando** (≈ 4.657 pela validação em metades; basta imprimir `len(base)`) |
| 1 | Nomes dos grupos 4004/4006 | Conferir no dicionário oficial |
| 2 | 4 regras finais | **Respondido** (§2), mas com ressalva de que não são regras percepção → desempenho |
| 3 | SHAP das 14 variáveis | **Respondido** (§3) |
| 4 | Critério para k = 3 | **Não registrado**: k fixado a priori; sem varredura de k |
| 5 | Perfil dos clusters | **Respondido** (§5), com rótulos de categoria a conferir no dicionário |
| 6 | Tabela conceitual | **Respondido** (§6) |
| 7 | Avaliação DSR com especialistas | **Não existe** |
| 8 | Procedimento da revisão bibliográfica | **Não registrado** no módulo |
