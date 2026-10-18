# Dicionário Unificado de Variáveis — ENADE-Time Distribuído

**Projeto 4 — ENADE-Time · Critério B · Módulo 1 (ETL Longitudinal e Harmonização)**
Aluno responsável: **Lucas Eduardo Tavares Costa**

Este documento descreve, para cada variável relevante do recorte, o **nome/código
original por ano**, a **forma harmonizada** adotada no pipeline e as
**observações** sobre mudanças entre ciclos do ENADE.

> Fonte de verdade: a harmonização é executada em
> [`scripts/02_processar_microdados_enade.py`](../scripts/02_processar_microdados_enade.py).
> As evidências por ano vêm de
> [`dados_processados/inspecao_estrutura.csv`](../dados_processados/inspecao_estrutura.csv)
> e [`dados_processados/relatorio_processamento.csv`](../dados_processados/relatorio_processamento.csv).
> Base consolidada resultante:
> [`dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv`](../dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv)
> (24.967 linhas, 6 edições).

## Recorte do estudo

- **Edições:** 2005, 2008, 2011, 2014, 2017, 2021 (ciclos trienais da área).
- **Cursos:** Computação — `CO_GRUPO` ∈ {40, 4004}.
- **Regiões:** Norte e Nordeste — `CO_REGIAO_CURSO` ∈ {1, 2}.
- **Grão da base consolidada:** linha do `arq1` filtrado (uma por inscrição); as
  notas são médias por `CO_CURSO` calculadas a partir do `arq3`.
- **Unidade analítica: curso-ano.** As 13 colunas são função de (`NU_ANO`,
  `CO_CURSO`): são **582 pares distintos** (216 `CO_CURSO`), e 24.385 das 24.967
  linhas são réplicas integrais. Médias calculadas diretamente sobre a base são,
  portanto, **ponderadas por matrícula**; o N para inferência é 582, não 24.967.
  A view `v_enade_time_curso_ano` (Supabase) materializa esse grão com os nomes
  de coluna do E-XplainENADE. (Ver `DESIGN_LOG.md`, D16.)

---

## Tabela de harmonização (nome original por ano → harmonizado → observações)

| # | Variável (harmonizada) | Origem (arquivo) | Presença / forma por ano | Forma harmonizada | Observações (mudança entre ciclos) |
|---|---|---|---|---|---|
| 1 | **nu_ano** | arq1 `NU_ANO` | Presente em todos | `nu_ano` SMALLINT | Identifica a edição; sem alteração de nome entre ciclos. |
| 2 | **co_grupo** | arq1 `CO_GRUPO` | **40** em 2005 e 2008; **4004** em 2011, 2014, 2017, 2021 | `co_grupo` SMALLINT (mantém o código original do ano) | **Mudança de código entre ciclos**: Computação migrou de 40 → 4004. O pipeline trata os dois como equivalentes via conjunto `CODIGOS_COMPUTACAO = {40, 4004}` (não recodifica para um valor único — preserva o código original e marca a equivalência semântica). Evidência: `inspecao_estrutura.csv` colunas `tem_40`/`tem_4004`. |
| 3 | **co_modalidade** | arq1 `CO_MODALIDADE` | **Ausente** no arq1 de 2005 e 2008; **presente** em 2011+ | `co_modalidade` SMALLINT NULL | **Mudança de esquema entre ciclos**: quando a coluna não existe no arquivo bruto, é criada e preenchida com NULL (`df1["CO_MODALIDADE"] = pd.NA`). Evidência: `inspecao_estrutura.csv` coluna `tem_co_modalidade = nao` (2005/2008) / `sim` (2011+) e observação em `relatorio_processamento.csv`. |
| 4 | **media_nt_fg** | arq3 `NT_FG` | Presente em todos (arq3) | `media_nt_fg` NUMERIC(7,4) NULL — média de `NT_FG` por `CO_CURSO` | Decimal com **vírgula→ponto**; sentinelas de ausência → NULL; validação de escala [0, 100]. |
| 5 | **media_nt_ger** | arq3 `NT_GER` | Presente em todos (arq3) | `media_nt_ger` NUMERIC(7,4) NULL — média de `NT_GER` por `CO_CURSO` | Mesmo tratamento de `NT_FG`. Adicionada em etapa posterior controlada (ver `LOG_EXECUCAO_ETL.md`). |
| 6 | **media_nt_ce** | arq3 `NT_CE` | Presente em todos (arq3) | `media_nt_ce` NUMERIC(7,4) NULL — média de `NT_CE` por `CO_CURSO` | Mesmo tratamento de `NT_FG`. |
| 7 | **co_regiao_curso** | arq1 `CO_REGIAO_CURSO` | Presente em todos | `co_regiao_curso` SMALLINT | Usado como filtro do recorte (Norte=1, Nordeste=2). |
| 8 | **co_uf_curso** | arq1 `CO_UF_CURSO` | Presente em todos | `co_uf_curso` SMALLINT | Identifica a UF do curso. |

> **Cobertura do requisito:** ≥5 variáveis com mudança entre ciclos harmonizadas —
> com destaque para `co_grupo` (código), `co_modalidade` (esquema/ausência) e as
> três notas `NT_FG`/`NT_GER`/`NT_CE` (formato decimal + sentinelas).

---

## Harmonizações técnicas transversais (aplicadas a todos os anos)

Implementadas em `scripts/02_processar_microdados_enade.py`:

1. **Detecção automática de encoding** — testa `utf-8`, `latin1`, `cp1252`.
   *Evidência:* todos os 6 anos foram lidos como `utf-8` (`inspecao_estrutura.csv`,
   colunas `arq1_encoding`/`arq3_encoding`), mas o pipeline tolera os demais.
2. **Detecção automática de separador** — testa `;`, `,`, `\t` e escolhe o que
   maximiza o número de colunas. *Evidência:* todos os anos usaram `;`.
3. **Normalização decimal** — `","` → `"."` antes de converter notas para float
   (`s.str.replace(",", ".", ...)`).
4. **Sentinelas de ausência → NULL** — conjunto
   `{"", ".", "NA", "N/A", "nan", "NaN", "NAN", "null", "Null", "NULL", "None", "none"}`
   convertido para nulo (preserva nulos como nulos, sem inventar valores).
5. **Validação de escala** — médias de nota rejeitadas se fora de [0, 100]
   (o ano não é salvo se a validação falhar).

---

## Disponibilidade por ano (evidência real)

| Ano | arq1 enc/sep | arq3 enc/sep | `CO_MODALIDADE` | `CO_GRUPO` | linhas filtradas |
|----:|:---:|:---:|:---:|:---:|---:|
| 2005 | utf-8 / `;` | utf-8 / `;` | ausente → NULL | 40 | 5.748 |
| 2008 | utf-8 / `;` | utf-8 / `;` | ausente → NULL | 40 | 8.740 |
| 2011 | utf-8 / `;` | utf-8 / `;` | presente | 4004 | 2.463 |
| 2014 | utf-8 / `;` | utf-8 / `;` | presente | 4004 | 2.388 |
| 2017 | utf-8 / `;` | utf-8 / `;` | presente | 4004 | 2.537 |
| 2021 | utf-8 / `;` | utf-8 / `;` | presente | 4004 | 3.091 |
| **Total** | | | | | **24.967** |

*(Fonte: `inspecao_estrutura.csv` + `relatorio_processamento.csv`.)*

---

## Esquema final da base consolidada

`NU_ANO; CO_CURSO; CO_IES; CO_CATEGAD; CO_ORGACAD; CO_GRUPO; CO_MODALIDADE;
CO_MUNIC_CURSO; CO_UF_CURSO; CO_REGIAO_CURSO; MEDIA_NT_FG; MEDIA_NT_GER; MEDIA_NT_CE`

- Separador `;`, encoding `utf-8-sig`, decimal com ponto.
- `MEDIA_NT_FG`, `MEDIA_NT_GER`, `MEDIA_NT_CE`: 24.775 preenchidos / 192 nulos
  cada (os 192 nulos são coerentes entre as três notas).
