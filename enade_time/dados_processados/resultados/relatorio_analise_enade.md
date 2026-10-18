# Análise da Média de NT_FG — Ciência da Computação no Norte e Nordeste — ENADE

_Relatório gerado automaticamente em 2026-05-22._

## 1. Objetivo da análise

Descrever a evolução temporal da **média da Nota de Formação Geral (NT_FG)** nos cursos de **Ciência da Computação** ofertados nas regiões **Norte** e **Nordeste** do Brasil, usando os microdados públicos do ENADE entre 2005 e 2021.

## 2. Base utilizada

- **Origem:** microdados oficiais do ENADE/INEP (arquivos `arq1` e `arq3` por ano), edições de 2005, 2008, 2011, 2014, 2017 e 2021 — os anos em que Ciência da Computação foi avaliada dentro do **ciclo trienal** do exame.
- **Pipeline:** os TXT originais foram lidos por `scripts/02_processar_microdados_enade.py`, filtrados, e o resultado consolidado salvo em `dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv`.
- **Bases derivadas (entradas deste relatório):** geradas por `scripts/03_gerar_bases_analise.py` em `dados_processados/analises/`.

## 3. Critérios de filtragem

- `CO_GRUPO` ∈ {**40** (Ciência da Computação até 2008), **4004** (Ciência da Computação a partir de 2011)}.
- `CO_REGIAO_CURSO` ∈ {**1** (Norte), **2** (Nordeste)}.
- **Sistemas de Informação (CO_GRUPO=4006) foi excluído** deste recorte.
- Outros cursos relacionados a Computação (Engenharia de Computação, Licenciatura em Computação, ADS, Redes, Gestão de TI) também não estão incluídos.

> **Nota sobre a recodificação 40 → 4004:** o INEP alterou o código identificador de Ciência da Computação entre as edições antigas (até 2008) e as recentes (a partir de 2011). No CSV consolidado, o `CO_GRUPO` é mantido com o **valor original de cada edição** — fidelidade ao dado bruto. Para análises temporais, ambos representam o mesmo curso.

## 4. Tratamento metodológico

- A conversão de `NT_FG` aceita decimais com vírgula ou ponto e descarta sentinelas (`""`, `"."`, `"NA"`, `"nan"`, `"null"`, `"None"`) como valor nulo.
- Foi aplicada validação dura de escala: se qualquer média ultrapassar `[0, 100]`, o CSV do ano **não** é salvo. Todos os anos passaram na validação.
- A média por curso (`MEDIA_NT_FG`) foi calculada agrupando o `arq3` por `CO_CURSO` antes do `left join` com o `arq1` filtrado.
- Para análise temporal, a base foi **deduplicada por (NU_ANO, CO_CURSO)**, evitando inflar as estatísticas com a repetição de alunos do mesmo curso.
- **Registros com `MEDIA_NT_FG` nula foram separados em arquivo de controle** (`controle_nulos_media_nt_fg.csv`) e **não entraram** nos cálculos de média, mediana, desvio etc.
- **`CO_MODALIDADE` não existe** nos microdados de 2005/2008; nessas linhas a coluna fica em branco no CSV final. Para 2011–2021 o valor original do INEP é preservado.

## 5. Resultados por ano

| Ano | Cursos | Média | Mediana | Mínimo | Máximo | Desvio padrão |
|-----|-------:|------:|--------:|-------:|-------:|--------------:|
| 2005 | 110 | 54.85 | 55.73 | 4.06 | 70.61 | 8.73 |
| 2008 | 165 | 47.53 | 47.68 | 11.19 | 64.43 | 6.93 |
| 2011 | 79 | 51.70 | 51.85 | 35.58 | 64.20 | 6.26 |
| 2014 | 66 | 60.07 | 59.39 | 40.61 | 79.20 | 6.90 |
| 2017 | 72 | 53.48 | 53.31 | 35.94 | 67.33 | 6.83 |
| 2021 | 76 | 38.21 | 37.86 | 24.38 | 54.30 | 6.41 |

**Por região:**

| Ano | Região | Cursos | Média | Mediana | Min | Max | Desvio |
|-----|-------:|-------:|------:|--------:|----:|----:|-------:|
| 2005 | 1 | 32 | 53.98 | 53.84 | 44.24 | 66.89 | 5.98 |
| 2005 | 2 | 78 | 55.20 | 56.35 | 4.06 | 70.61 | 9.64 |
| 2008 | 1 | 46 | 45.22 | 44.83 | 30.00 | 56.95 | 6.49 |
| 2008 | 2 | 119 | 48.42 | 48.58 | 11.19 | 64.43 | 6.91 |
| 2011 | 1 | 21 | 51.49 | 50.80 | 35.58 | 64.20 | 6.80 |
| 2011 | 2 | 58 | 51.78 | 52.08 | 36.65 | 62.65 | 6.11 |
| 2014 | 1 | 15 | 58.21 | 57.17 | 40.61 | 79.20 | 9.23 |
| 2014 | 2 | 51 | 60.62 | 59.40 | 48.90 | 75.84 | 6.06 |
| 2017 | 1 | 18 | 50.05 | 51.58 | 38.79 | 59.50 | 6.82 |
| 2017 | 2 | 54 | 54.63 | 53.50 | 35.94 | 67.33 | 6.50 |
| 2021 | 1 | 14 | 36.20 | 36.91 | 26.82 | 46.15 | 6.92 |
| 2021 | 2 | 62 | 38.67 | 38.22 | 24.38 | 54.30 | 6.26 |

## 6. Interpretação dos resultados

A série temporal tem **seis pontos** — 2005, 2008, 2011, 2014, 2017 e 2021 — correspondentes às edições em que Ciência da Computação foi avaliada dentro do ciclo trienal do ENADE. Outros anos do calendário (2010, 2012, 2013, etc.) **não** trazem dados desse curso e por isso ficam fora do escopo.

- **2005:** média aproximada de **54.85** sobre 110 cursos avaliados.
- **2008:** média aproximada de **47.53** sobre 165 cursos avaliados.
- **2011:** média aproximada de **51.70** sobre 79 cursos avaliados.
- **2014:** média aproximada de **60.07** sobre 66 cursos avaliados.
- **2017:** média aproximada de **53.48** sobre 72 cursos avaliados.
- **2021:** média aproximada de **38.21** sobre 76 cursos avaliados.

> **Importante:** o relatório descreve apenas a variação observada nos dados. **Não se afirma causalidade.** Diferenças entre edições podem refletir características específicas da prova de cada ano, mudanças no calendário, na população avaliada, na codificação adotada pelo INEP ou em variáveis externas (p.ex., contexto pós-pandemia em 2021). Qualquer atribuição de causa específica exigiria investigação adicional.

## 7. Observações sobre dados nulos

- Total de **192** registros com `MEDIA_NT_FG` nula no consolidado (cursos que existem no `arq1` mas cujos alunos não geraram nenhum `NT_FG` numérico válido no `arq3`).
- Distribuição por ano:

| Ano | Linhas nulas | Cursos únicos com média nula |
|-----|-------------:|-----------------------------:|
| 2005 | 24 | 2 |
| 2011 | 8 | 2 |
| 2014 | 4 | 2 |
| 2017 | 28 | 2 |
| 2021 | 128 | 6 |

- **Interpretação correta:** valor nulo significa **ausência de média válida**, não nota zero.
- Esses registros foram listados em `controle_nulos_media_nt_fg.csv` para auditoria, mas excluídos de todos os cálculos estatísticos.

## 8. Limitações da análise

- A série temporal é **descontínua** (apenas 6 pontos em 17 anos cobertos), o que limita análises de tendência refinadas.
- O recorte foi mantido **estrito** a Ciência da Computação (códigos 40/4004) — eventuais cursos sob outros `CO_GRUPO` (Engenharia de Computação, Licenciatura, ADS, Sistemas de Informação etc.) **não estão** nesta base.
- A média de cada curso é a média simples dos `NT_FG` dos alunos, sem ponderação por número de respondentes nem ajuste pela presença/ausência.
- `CO_MODALIDADE` não está disponível em 2005/2008 — análises por modalidade só podem ser feitas a partir de 2011.
- 2020 não tem edição (cancelada pela pandemia); 2021 funciona como reposição.

## 9. Arquivos gerados

Em `dados_processados/resultados/`:

- `grafico_media_nt_fg_por_ano.png` — média geral por ano (linha única).
- `grafico_media_nt_fg_por_regiao.png` — comparação Norte (1) vs Nordeste (2).
- `tabela_resumo_final.csv` — tabela compacta para usar no Sheets.
- `relatorio_analise_enade.md` — este documento.
- `README_RESULTADOS.md` — guia rápido dos artefatos.
