# Eficácia real de bolsas de assistência e auxílio

## 1. Qual o problema, e por que ele importa

O projeto busca avaliar se estudantes cotistas ou beneficiários de programas de assistência e auxílio, como Prouni, PIBIC e apoio moradia, alcançam proficiência equivalente ou superior à dos alunos pagantes.

A partir de dados públicos, pretendemos investigar a relação entre o acesso a esses benefícios e o desempenho acadêmico dos estudantes. Essa análise pode contribuir para compreender a eficácia dos programas de apoio estudantil e fornecer informações que auxiliem no direcionamento de verbas públicas e institucionais.

O problema é relevante porque permite avaliar se os recursos destinados à assistência estudantil estão associados a resultados acadêmicos positivos, contribuindo para a permanência e o desenvolvimento dos estudantes.

## 2. De onde vieram os dados, e quantos são

Os dados utilizados no projeto foram obtidos a partir dos microdados do Exame Nacional de Desempenho dos Estudantes (Enade) 2021, disponibilizados pelo Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira (INEP).

Fonte: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enade

O arquivo `microdados2021_arq29.csv` contém 489868 registros e 3 colunas:

- `NU_ANO`: ano de referência dos dados.
- `CO_CURSO`: código do curso.
- `QE_I23`: variável relacionada ao Questionário do Estudante.

A base foi escolhida por conter informações relacionadas aos estudantes cotistas e bolsistas, que serão utilizadas na investigação da eficácia dos programas de assistência e auxílio estudantil.

A análise inicial identificou que o arquivo contém informações sobre o ano, o código do curso e uma variável de questionário. Ainda será necessário consultar a documentação oficial dos microdados para compreender o significado de cada variável e verificar quais informações permitem realizar a comparação entre estudantes beneficiários e alunos pagantes.