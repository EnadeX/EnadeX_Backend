# Log de Execução do ETL — ENADE-Time Distribuído

**Projeto 4 — ENADE-Time · Critério B · Módulo 1**
Aluno responsável: **Lucas Eduardo Tavares Costa**

Registro de execução do pipeline de ingestão e harmonização dos microdados do
ENADE, com versão do dataset, data, seed e transformações aplicadas.

---

## Versão do dataset

| Campo | Valor |
|---|---|
| **Versão** | `v1.1` — base consolidada com as três notas (`MEDIA_NT_FG`, `MEDIA_NT_GER`, `MEDIA_NT_CE`) |
| **Versão anterior** | `v1.0` — apenas `MEDIA_NT_FG` (preservada no backup `*.backup_20260616_223051.csv`) |
| **Data de referência deste log** | 2026-06-17 |
| **Arquivo** | `dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv` |
| **Linhas** | 24.967 |
| **Colunas** | 13 |
| **Edições** | 2005, 2008, 2011, 2014, 2017, 2021 |

## Seed

**N/A — pipeline determinístico.** O ETL não usa amostragem aleatória,
embaralhamento nem qualquer fonte de aleatoriedade; dada a mesma entrada bruta,
a saída é idêntica byte-a-byte. Portanto não há seed a registrar. (Caso o Módulo
2 venha a usar reamostragem/bootstrap para IC 95%, a seed deverá ser registrada
aqui.)

---

## Transformações aplicadas (na ordem)

Executadas por `scripts/02_processar_microdados_enade.py` (geração da base v1.0)
e por `tools/adicionar_notas_ger_ce_consolidado.py` (incremento controlado v1.1):

1. **Localização dos arquivos** por ano (`arq1` cadastro, `arq3` notas).
2. **Detecção de encoding** (utf-8 / latin1 / cp1252) e **separador** (`;` / `,` / `\t`).
3. **Seleção de colunas** obrigatórias do `arq1` e de notas do `arq3`.
4. **Conversão de inteiros** (códigos) com sentinelas → `<NA>`.
5. **Harmonização `CO_MODALIDADE`**: criada com NULL quando ausente (2005/2008).
6. **Filtro do recorte**: `CO_REGIAO_CURSO ∈ {1,2}` e `CO_GRUPO ∈ {40, 4004}`.
7. **Conversão das notas** `NT_FG`/`NT_GER`/`NT_CE`: vírgula→ponto, sentinelas→NULL.
8. **Agregação por curso**: média de cada nota por `CO_CURSO`.
9. **Validação de escala** [0, 100] (ano rejeitado se violar).
10. **Merge** das médias no `arq1` filtrado (grão = curso).
11. **Consolidação** por concatenação na ordem dos anos.
12. **Incremento v1.1** (`tools/adicionar_notas_ger_ce_consolidado.py`): reconstrução
    dos mesmos registros, **validação linha-a-linha** contra a base v1.0 (todas as
    colunas inteiras + `MEDIA_NT_FG` batendo 100%) e anexação de `MEDIA_NT_GER` e
    `MEDIA_NT_CE` **sem alterar** nenhuma coluna antiga (backup automático criado).

---

## Contagens por ano (evidência real)

Fonte: `dados_processados/relatorio_processamento.csv` (coluna `linhas_arq1_filtrado`).

| Ano | Linhas brutas `arq1` | Linhas filtradas | Cursos únicos | min `MEDIA_NT_FG` | max `MEDIA_NT_FG` |
|----:|---:|---:|---:|---:|---:|
| 2005 | 323.338 | 5.748 | 112 | 0,0000 | 80,1750 |
| 2008 | 461.726 | 8.740 | 165 | 0,0000 | 75,8571 |
| 2011 | 376.180 | 2.463 | 81 | 0,0000 | 81,5000 |
| 2014 | 481.718 | 2.388 | 68 | 1,9780 | 93,6000 |
| 2017 | 537.358 | 2.537 | 74 | 15,0000 | 92,1000 |
| 2021 | 489.866 | 3.091 | 82 | 3,7500 | 66,7000 |
| **Total** | — | **24.967** | — | — | — |

## Qualidade das notas (após v1.1)

| Coluna | Não nulos | Nulos | Coerência |
|---|---:|---:|---|
| `MEDIA_NT_FG` | 24.775 | 192 | — |
| `MEDIA_NT_GER` | 24.775 | 192 | nulos idênticos aos de FG |
| `MEDIA_NT_CE` | 24.775 | 192 | nulos idênticos aos de FG |

*(Validado por `scripts/07_validar_banco.py`: seção "3b/3c" confirma 24.775 não
nulos, 192 nulos e divergência fg/ger = fg/ce = 0.)*

---

## Manifesto de arquivos

| Arquivo | Linhas |
|---|---:|
| `microdados_enade_2005_filtrado.csv` | 5.748 (+header) |
| `microdados_enade_2008_filtrado.csv` | 8.740 (+header) |
| `microdados_enade_2011_filtrado.csv` | 2.463 (+header) |
| `microdados_enade_2014_filtrado.csv` | 2.388 (+header) |
| `microdados_enade_2017_filtrado.csv` | 2.537 (+header) |
| `microdados_enade_2021_filtrado.csv` | 3.091 (+header) |
| `microdados_enade_2005_2021_filtrado_consolidado.csv` | 24.967 (+header) |
| `microdados_enade_2005_2021_filtrado_consolidado.backup_20260616_223051.csv` | 24.967 (v1.0, 11 colunas) |

---

## Reprodutibilidade

```powershell
cd C:\Projetos\ENADE
.\.venv\Scripts\Activate.ps1
# (v1.0) geração base — NÃO reexecutar sem necessidade; já validada
# python scripts\02_processar_microdados_enade.py
# (v1.1) incremento das notas GER/CE — já aplicado e validado
# python tools\adicionar_notas_ger_ce_consolidado.py --dry-run
```

> Os microdados brutos (`microdados_enade_*`) e os scripts 01–10 **não** são
> alterados por este pipeline; toda escrita ocorre apenas em `dados_processados/`.
