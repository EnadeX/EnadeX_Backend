# Resultados — Projeto ENADE-Time (Ciência da Computação, Norte/Nordeste)

_Gerado em 2026-05-22._

## Recorte v2

- **Curso:** Ciência da Computação (CO_GRUPO **40** em 2005/2008 e **4004** em 2011–2021).
- **Regiões:** Norte (1) e Nordeste (2).
- **Anos:** 2005, 2008, 2011, 2014, 2017, 2021 — edições do ciclo trienal em que Computação foi avaliada.
- **Sistemas de Informação (4006) e demais cursos de TI foram excluídos.**

## Estrutura desta pasta (`dados_processados/resultados/`)

### CSV
- **`tabela_resumo_final.csv`** — Tabela compacta com 1 linha por ano e as estatísticas principais. **Use este arquivo no Google Sheets** como ponto de partida.

### Gráficos (PNG, prontos para apresentação)
- **`grafico_media_nt_fg_por_ano.png`** — Evolução da média geral em 6 pontos.
- **`grafico_media_nt_fg_por_regiao.png`** — Compara Norte vs Nordeste.

### Documentação
- **`relatorio_analise_enade.md`** — Relatório completo: objetivo, metodologia, tabelas, interpretação e limitações.
- **`README_RESULTADOS.md`** — Este arquivo.

## Fluxo de execução do projeto

1. `scripts/01_inspecionar_estrutura.py` — diagnóstico read-only dos TXT.
2. `scripts/02_processar_microdados_enade.py` — pipeline principal.
3. `scripts/03_validar_csvs.py` — validação das saídas oficiais.
4. `scripts/03_gerar_bases_analise.py` — bases derivadas para análise.
5. `scripts/04_gerar_graficos_e_relatorio.py` — gráficos e relatório (este).

## Garantias
- Nenhum arquivo `.txt` original foi alterado.
- Nenhum CSV oficial em `dados_processados/` foi sobrescrito por este script.
- Todos os CSVs usam `sep=";"` e `encoding="utf-8-sig"` (Google Sheets PT-BR).
