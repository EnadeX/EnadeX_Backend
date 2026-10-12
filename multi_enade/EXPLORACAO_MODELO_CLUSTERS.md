# Revisão do modelo de clusters — multi_enade

Registro da revisão sobre `modelo_clusters.py`.

## Diagnóstico: NT_GER como variável de clusterização era circular

`treinar_e_salvar_clusters`/`aplicar_clusters` só excluíam `CO_CURSO` e
`QT_ALUNOS` antes de padronizar e treinar o KMeans — **`NT_GER` entrava como
uma das variáveis de agrupamento**. Os clusters resultantes eram então
nomeados "Desempenho Alto/Médio/Baixo" (`nomear_clusters`, por ranking de
`NT_GER` médio) — ou seja, a nota ajudava a *formar* os grupos e depois os
grupos eram rotulados *pela mesma nota*. O "achado" de que o cluster de
desempenho alto tem desempenho alto é, nessas condições, quase garantido
pela própria definição dos grupos, não uma relação genuína entre perfil
pedagógico (infraestrutura/cotas) e desempenho.

### Teste: com vs. sem NT_GER como entrada

| | Com NT_GER (antes) | Sem NT_GER |
|---|---|---|
| Silhouette score | 0,133 | **0,142** (clusters mais coesos) |
| NT_GER por cluster | 35,22 / 35,84 / **39,14** (separação de ~4 pontos) | 36,19 / **38,36** / 36,79 (separação de ~2,2 pontos) |

Sem a nota como entrada, o KMeans forma clusters **até ligeiramente melhor
definidos** (silhouette mais alto) — a nota não estava ajudando a achar
grupos mais naturais, só inflando a separação de desempenho entre eles.

### O perfil sem NT_GER é mais informativo, não só "mais honesto"

| | Cluster 0 (n=42) | Cluster 1 (n=71, desempenho alto) | Cluster 2 (n=48) |
|---|---|---|---|
| NT_GER médio | 36,19 | **38,36** | 36,79 |
| QE_I63_6 (infra "concordo totalmente") | 25% | 48% | **75%** |
| QE_I15_A (ampla concorrência, sem cota) | 74% | 60% | 84% |

**Achado não-trivial**: o cluster com a infraestrutura mais bem avaliada
(cluster 2, 75% "concordo totalmente") **não** é o de melhor desempenho — é
o cluster 1, com infraestrutura intermediária (48%) e mais diversidade de
cotas (só 60% ampla concorrência). Sem a circularidade, a relação entre
infraestrutura/diversidade e desempenho deixa de ser monotônica e óbvia —
que é exatamente o tipo de padrão que uma análise de clusters deveria
revelar, em vez de esconder atrás de uma separação artificialmente limpa.

## Correção aplicada

`NT_GER` removida das variáveis de entrada em `treinar_e_salvar_clusters`,
`aplicar_clusters` e `plotar_grafico_clusters` (as 3 usavam a mesma lista de
exclusão de colunas "não-matemáticas", agora incluindo `NT_GER`). Ela
continua disponível no DataFrame para:
- `nomear_clusters`: ranking dos clusters por `NT_GER` médio pós-formação
  (não muda — já era calculado depois do KMeans, só a entrada mudou).
- O perfil numérico impresso e a tabela publicada (`tbl_multi_enade_clusters`
  já tinha a coluna `NT_GER`, nenhuma mudança de schema necessária).

Retreinado e republicado: `tbl_multi_enade_clusters` (161 cursos), mesmos 3
clusters nomeados, perfil exatamente como a tabela acima.

## Enriquecimento: renda e bolsa/financiamento

Testado adicionar `QE_I08` (renda, ordinal) e `QE_I11` (bolsa/financiamento
do curso — "bolsa" no sentido mais literal, diferente de `QE_I13` que é
bolsa acadêmica/iniciação científica) ao conjunto de entrada (infra+cotas).

| Cenário | Nº variáveis | Silhouette | Separação de NT_GER |
|---|---|---|---|
| Atual (infra+cotas) | 12 | 0,142 | 36,19 – 38,36 (gap 2,2) |
| + renda | 13 | 0,136 (piora) | gap quase igual |
| **+ bolsa** | 23 | **0,211** | **34,75 – 39,80 (gap 5,0)** |
| + renda + bolsa | 24 | 0,201 | gap 4,4, mas 1 cluster com só 8 cursos (instável) |

**Renda isolada não ajudou** — silhouette piora levemente, separação de
desempenho não muda. **Bolsa ajudou muito** — clusters mais coesos e
separação de desempenho mais que o dobro.

### Por que bolsa funciona

Perfil do cenário "+ bolsa" (clusters balanceados: 73/16/72 cursos):

| | Cluster 0 (NT_GER=39,80) | Cluster 1 (NT_GER=37,57) | Cluster 2 (NT_GER=34,75) |
|---|---|---|---|
| QE_I11_A (nenhuma bolsa, curso gratuito) | **97%** | 0% | 1% |
| QE_I11_B (nenhuma bolsa, curso pago) | 0% | 12% | 31% |

`QE_I11` captura de forma indireta o divisor público-gratuito vs.
privado-pago — o cluster quase inteiramente de cursos gratuitos (97%) tem
a nota mais alta. Consistente com o achado de `CO_CATEGAD` (pública
federal) na regressão (`EXPLORACAO_MODELO_REGRESSAO.md`) — é o mesmo fator
institucional aparecendo por um ângulo diferente.

**Decisão**: `QE_I11` incorporado às variáveis de clusterização; renda
isolada descartada (não validou). Retreinado e republicado:
`tbl_multi_enade_clusters` (161 cursos, 30 colunas — 11 novas de `QE_I11`),
clusters agora: Alto (n=73, NT_GER=39,80), Médio (n=16, NT_GER=37,57),
Baixo (n=72, NT_GER=34,75).

## Gráfico local: bug de `savefig` corrigido

`plotar_grafico_clusters` nunca teve `plt.savefig(...)` — só `plt.show()`
(que não faz nada no backend `Agg`, sem display). Rodava sem erro, mas não
produzia nenhum arquivo. Corrigido: parâmetro `nome_arquivo`, salva
`grafico_clusters.png`. Mesmo tipo de bug encontrado e corrigido em
`plotar_grafico_shap` da regressão (`EXPLORACAO_MODELO_REGRESSAO.md`).

### Pendência

`QE_I08` (renda) e `QE_I13` (bolsa acadêmica/IC) ainda não testados juntos
com `QE_I11` — podem interagir de forma diferente da testada isoladamente.
