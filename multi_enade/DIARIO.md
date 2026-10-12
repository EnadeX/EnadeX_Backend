# DIÁRIO DE DECISÕES

## 13/09 - 10:20

Baixamos os dados públicos de alunos estudantes cotistas e bolsistas (Prouni/PIBIC/apoio moradia). O arquivo `microdados2021_arq29.csv` continha 489868 linhas e 3 colunas, sendo elas "NU_ANO", "CO_CURSO", "QE_I23".

## 13/09 - 10:50

Iniciamos a análise das variáveis do arquivo para entender quais informações estão disponíveis e como elas podem ser utilizadasno projeto.

## 13/09 - 11:00

Realizamos a análise exploratória dos dados.

## 13/09 -

## 04/10

Revisão completa da lógica de negócio do `modelo_regressao.py` (e correções
menores em clusters/associação), reconstrução do ETL de ingestão
(`refinamento_dados/`) e exploração extensa de variáveis/modelos pra tentar
melhorar o poder explicativo de NT_GER (saiu de R²≈-0,14 pra R²≈0,40 em
validação cruzada). Processo completo, com todos os números de cada etapa,
documentado em `EXPLORACAO_MODELO_REGRESSAO.md`.

## 04/10 (continuação)

Revisão do `modelo_associacao.py`: os 3 itens originais eram do mesmo
microtema e só geravam regras de efeito-halo raso (7 regras, lift 1,5-1,8).
Testado ligar percepção a desempenho do curso (banda de NT_GER via
CO_CURSO), com busca de limiar e validação por amostras independentes —
metade das regras "achadas" numa amostra não se repetia na outra, só as
ancoradas em `oportunidades_ic` (iniciação científica) sobreviveram.
Suporte 0,6 pedido pelo usuário se mostrou estruturalmente impossível (nem
a categoria mais comum chega a 60% dos alunos). Config final adotada:
6 itens diversos + banda de desempenho, suporte 0,03/confiança 0,5, com
limite de 50 regras publicadas (de 2417 encontradas) pra não inundar a
tabela. Processo completo documentado em `EXPLORACAO_MODELO_ASSOCIACAO.md`.

## 04/10 (continuação 2)

Revisão do `modelo_clusters.py`: `NT_GER` entrava como variável de
clusterização e depois os clusters eram nomeados "Desempenho Alto/Médio/
Baixo" pela mesma nota — circular. Sem ela, o KMeans forma clusters até
mais coesos (silhouette 0,142 vs 0,133) e revela um padrão menos óbvio: o
cluster com infraestrutura melhor avaliada não é o de melhor desempenho —
é um cluster intermediário, com mais diversidade de cotas. Corrigido:
NT_GER removida das variáveis de entrada, mantida só para nomear/perfilar
os clusters depois de formados. Documentado em
`EXPLORACAO_MODELO_CLUSTERS.md`.

## 04/10 (continuação 3)

Testado enriquecer os clusters com renda (`QE_I08`) e bolsa/financiamento
(`QE_I11`). Renda isolada não ajudou (silhouette piora). Bolsa ajudou muito
(silhouette 0,142 -> 0,211, separação de desempenho dobrou) — captura de
forma indireta o divisor público-gratuito vs. privado-pago, mesmo fator que
já tinha aparecido na regressão via `CO_CATEGAD`. Aplicado em produção:
`QE_I11` incorporado, renda descartada. Clusters agora: Alto (n=73,
NT_GER=39,80), Médio (n=16, NT_GER=37,57), Baixo (n=72, NT_GER=34,75).

## 04/10 (continuação 4) — gráficos locais + revisão completa final

Corrigidos 2 bugs de gráfico que nunca tinham sido pegos (geração "best
effort" escondia a falha): `plotar_grafico_shap` tinha o `savefig`
comentado (nunca salvava nada, só imprimia que tinha salvo);
`plotar_grafico_clusters` nunca teve `savefig`. Adicionado também um
gráfico novo (`grafico_pca_geral.png`) que resume as 14 variáveis da
regressão em 2D via PCA. Também corrigida a legenda "cotas" do gráfico de
regressão, que sempre caía em "Dado Indisponível" (checava a existência de
`QE_I15_A`, que não sobreviveu à seleção de variáveis) — agora usa
`QE_I15_C`+`QE_I15_E`, cortado pela mediana.

Revisão completa final do módulo: todas as 16 tabelas de origem e as 4 de
resultado conferidas ao vivo (190 cursos nas fontes, 161 nos resultados,
tudo consistente); os 4 endpoints de relatório e os 3 de reprocessamento
testados de ponta a ponta. Achado real: `POST /reprocessar/fontes` só
reprocessava as 4 fontes originais (`arq3,4,21,29`) — as 11 fontes
adicionadas depois (usadas por regressão e clusters) nunca tinham sido
conectadas ao endpoint. Corrigido: lista agora bate com as 13 tabelas que
os modelos realmente consultam. Documentação das 3 revisões (regressão,
clusters, associação) revisada e atualizada onde estava desatualizada.
