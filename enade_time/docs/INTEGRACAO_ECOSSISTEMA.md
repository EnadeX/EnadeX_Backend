# Integração no Ecossistema EnadeX

**Projeto 4 — ENADE-Time · Critério B · Módulo 1**
Aluno responsável: **Lucas Eduardo Tavares Costa**

Este documento define como a **base multianual consolidada** produzida pelo
ENADE-Time pode ser **consumida pelos demais projetos** do ecossistema EnadeX.

> ⚠️ **Aviso de integridade:** este documento descreve o *contrato técnico de
> consumo* da base — o que o ENADE-Time **oferece**. Ele **não** registra nenhuma
> decisão conjunta com outro aluno/projeto que não tenha de fato ocorrido. A
> seção "Acordos de Integração" abaixo está como **pendência / modelo para
> preenchimento posterior** e deve ser completada somente quando houver decisão
> real e combinada entre as partes.

---

## 1. O que esta base oferece

| Item | Valor |
|---|---|
| Artefato | `dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv` |
| Formato | CSV estruturado (`;`, `utf-8-sig`, decimal com ponto) |
| Linhas | 24.967 |
| Edições | 2005, 2008, 2011, 2014, 2017, 2021 |
| Recorte | Computação (`CO_GRUPO` 40/4004), Norte e Nordeste |
| Grão | curso (`CO_CURSO`) por ano; notas = médias por curso |
| Versão | v1.1 (com `MEDIA_NT_FG`, `MEDIA_NT_GER`, `MEDIA_NT_CE`) |

Schema (colunas e tipos lógicos):

| Coluna | Tipo | Nulo? |
|---|---|---|
| `NU_ANO` | inteiro (ano) | não |
| `CO_CURSO` | inteiro | não |
| `CO_IES` | inteiro (e-MEC) | não |
| `CO_CATEGAD` | inteiro | não |
| `CO_ORGACAD` | inteiro | não |
| `CO_GRUPO` | inteiro (40/4004) | não |
| `CO_MODALIDADE` | inteiro | sim (ausente em 2005/2008) |
| `CO_MUNIC_CURSO` | inteiro | sim |
| `CO_UF_CURSO` | inteiro | não |
| `CO_REGIAO_CURSO` | inteiro (1/2) | não |
| `MEDIA_NT_FG` | decimal [0–100] | sim (192) |
| `MEDIA_NT_GER` | decimal [0–100] | sim (192) |
| `MEDIA_NT_CE` | decimal [0–100] | sim (192) |

Documentação de apoio: [`DICIONARIO_VARIAVEIS.md`](DICIONARIO_VARIAVEIS.md),
[`LOG_EXECUCAO_ETL.md`](LOG_EXECUCAO_ETL.md).

> **Unidade analítica.** As 13 colunas são função de (`NU_ANO`, `CO_CURSO`):
> a base tem **582 cursos-ano** distintos (216 cursos); 24.385 das 24.967
> linhas são réplicas integrais (uma por inscrição). Quem consumir a base
> para inferência deve agregar por curso-ano — ou usar a view
> `v_enade_time_curso_ano` (abaixo) — e tratar as réplicas como peso por
> matrícula, não como observações independentes (DESIGN_LOG D16).

---

## 2. Formas de consumo

### 2.1 Direto pelo CSV (qualquer linguagem)
```python
import pandas as pd
df = pd.read_csv(
    "dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv",
    sep=";", encoding="utf-8-sig",
)
```
- Estável e sem dependência de serviço no ar.
- Indicado para projetos que rodam ETL/estatística offline.

### 2.2 Via API REST (read-only) — recomendada para dashboards
Base URL local: `http://localhost:8002/api/enade-time` (API standalone; com o
router no `api_main.py` central, `http://localhost:8000/api/enade-time`).
Endpoints úteis para outros projetos (caminhos relativos à base):

| Endpoint | Uso |
|---|---|
| `GET /health` | Verificar disponibilidade (503 quando o banco está fora) |
| `GET /dim/*` | Dimensões (regiões, UFs, anos, grupos, categorias…) |
| `GET /analises/resumo-anual` | Série por ano (média FG/GER/CE + n), aceita filtros |
| `GET /analises/resumo-regiao` / `resumo-uf` / `resumo-ies` | Agregações |
| `GET /analises/registros` | Registros paginados (3 notas) |

Filtros combináveis (AND): `nu_ano, co_regiao, co_uf, co_ies, co_grupo,
co_modalidade, co_categad, co_orgacad`. A API é **somente leitura** (sem
POST/PUT/DELETE). Contrato detalhado: Swagger em `http://localhost:8002/docs`. O consumidor de
referência é o módulo `/enade-time` do `EnadeX_Frontend`.

### 2.4 Supabase — contrato do ecossistema EnadeX (em implantação, DESIGN_LOG D11/D15)

Ponto de integração canônico do ecossistema. A base já está publicada como
`enade_time_distribuido` + `dim_*` (24.967 linhas, 06/08/2026) e será
renomeada para a convenção do grupo, com leitura por
`util.util_db.consultar_dados(...)`:

| Relação | Grão | Linhas | Observação |
|---|---|---:|---|
| `tbl_enade_time_fato` | inscrição (linha do arq1) × ano | 24.967 | mesmo schema do CSV v1.1 |
| `tbl_enade_time_dim_*` (7) | lookup | 40 | FKs para joins no PostgREST |
| `v_enade_time_curso_ano` | **curso × ano** | **582** | colunas com os nomes do `load_raw()` do E-XplainENADE: `"NU_ANO", "CO_CURSO", "NT_GER", "NT_FG", "NT_CE", "QT_ALUNOS", "CO_GRUPO", "CO_REGIAO", "TP_CATEGAD_BIN"`; `QT_ALUNOS` = inscritos (não `TP_PRES == 555`) — documentado em `COMMENT ON COLUMN` |
| `tbl_enade_time_benchmark_*`, `v_enade_time_benchmark_*` | execução / etapa / agregados | — | resultados do experimento de SPD |

O swap point registrado em `e_xplainenade/modules/etl.py` ("quando o
ENADE-Time (Lucas) entregar uma base normalizada equivalente…") é atendido
como **extensão longitudinal** (2005–2017 para os 82 cursos do recorte), não
como substituição: o recorte do E-XplainENADE (753 cursos, CC+SI, Brasil,
2021) continua vindo de `tbl_arq*_2021`. A formalização com o responsável
(JP) segue pendente — ver seção 4.

### 2.3 Parquet (opcional, sob demanda)
A base está disponível em CSV (atende ao requisito "Parquet **ou** CSV
estruturado"). Se um projeto consumidor exigir Parquet por desempenho, é possível
gerar uma cópia `.parquet` a partir do CSV (utilitário read-only, ainda não
criado — registrado em [`PROXIMOS_PASSOS.md`](PROXIMOS_PASSOS.md)).

---

## 3. Garantias e versionamento

- **Imutabilidade do recorte:** colunas e grão não mudam dentro de uma versão.
- **Nulos preservados:** notas ausentes ficam vazias (NULL), nunca imputadas.
- **Mudança de schema → nova versão** (ex.: v1.0 → v1.1 ao adicionar GER/CE),
  com backup da versão anterior preservado em `dados_processados/`.
- **Coerência das três notas:** os 192 nulos coincidem entre FG/GER/CE.

---

## 4. Acordos de Integração — PENDÊNCIA (preencher quando houver decisão real)

> Modelo a ser completado **somente** com decisões efetivamente combinadas com
> outro(s) projeto(s)/aluno(s). **Não preencher com suposições.**

| Campo | Preencher |
|---|---|
| Projeto consumidor | _[pendente]_ |
| Aluno(s) responsável(is) do outro lado | _[pendente]_ |
| Formato acordado (CSV / API / Parquet) | _[pendente]_ |
| Colunas/contrato acordados | _[pendente]_ |
| Frequência de atualização | _[pendente]_ |
| Data do acordo | _[pendente]_ |
| Evidência (ata, mensagem, issue) | _[pendente]_ |

**Status atual:** nenhuma integração conjunta formalizada foi registrada até a
data deste documento. O ENADE-Time disponibiliza a base e a API; a efetivação de
um acordo de consumo com outro projeto depende de combinação futura.
