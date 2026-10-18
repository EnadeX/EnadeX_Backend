"""
Gera gráficos e relatório final do projeto ENADE-Time — v2.

Recorte: Ciência da Computação (CO_GRUPO 40 em 2005/2008, 4004 em 2011-2021),
regiões Norte/Nordeste.

Entradas (não modificadas): dados_processados/analises/*.csv
Saídas em dados_processados/resultados/:
  - grafico_media_nt_fg_por_ano.png
  - grafico_media_nt_fg_por_regiao.png
  - tabela_resumo_final.csv
  - relatorio_analise_enade.md
  - README_RESULTADOS.md

Não toca nos CSVs oficiais nem nos TXT originais.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


RAIZ = Path(__file__).resolve().parent.parent
DIR_ANALISES = RAIZ / "dados_processados" / "analises"
DIR_OUT = RAIZ / "dados_processados" / "resultados"

ARQ_RES_ANO = DIR_ANALISES / "resumo_temporal_por_ano.csv"
ARQ_RES_ANO_REGIAO = DIR_ANALISES / "resumo_temporal_por_ano_regiao.csv"
ARQ_CURSOS = DIR_ANALISES / "cursos_unicos_com_media_nt_fg.csv"
ARQ_CTRL_NULOS = DIR_ANALISES / "controle_nulos_media_nt_fg.csv"
ARQ_RES_NULOS = DIR_ANALISES / "resumo_nulos_por_ano.csv"

CSVS_OFICIAIS = [
    RAIZ / "dados_processados" / "microdados_enade_2005_2021_filtrado_consolidado.csv",
    RAIZ / "dados_processados" / "microdados_enade_2005_filtrado.csv",
    RAIZ / "dados_processados" / "microdados_enade_2008_filtrado.csv",
    RAIZ / "dados_processados" / "microdados_enade_2011_filtrado.csv",
    RAIZ / "dados_processados" / "microdados_enade_2014_filtrado.csv",
    RAIZ / "dados_processados" / "microdados_enade_2017_filtrado.csv",
    RAIZ / "dados_processados" / "microdados_enade_2021_filtrado.csv",
    RAIZ / "dados_processados" / "relatorio_processamento.csv",
    RAIZ / "dados_processados" / "inspecao_estrutura.csv",
]

NOME_REGIAO = {1: "Norte (1)", 2: "Nordeste (2)"}


def ler(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, sep=";", encoding="utf-8-sig")


def sha256_size(p: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest(), p.stat().st_size


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def grafico_por_ano(df: pd.DataFrame, out: Path) -> None:
    df = df.sort_values("NU_ANO")
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    ax.plot(df["NU_ANO"], df["media_nt_fg"], marker="o", linewidth=2,
            color="#1f4e79", markersize=9, markerfacecolor="#c00000",
            markeredgecolor="#c00000")
    for _, r in df.iterrows():
        ax.annotate(f"{r['media_nt_fg']:.2f}",
                    (r["NU_ANO"], r["media_nt_fg"]),
                    textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=9, color="#333333")
    ax.set_title("Média da Nota de Formação Geral — Ciência da Computação — "
                 "Norte/Nordeste",
                 fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Ano da edição (NU_ANO)")
    ax.set_ylabel("Média da NT_FG (escala 0–100)")
    ax.set_xticks(df["NU_ANO"].tolist())
    ax.set_ylim(0, 100)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


def grafico_por_regiao(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    cores = {1: "#2ca02c", 2: "#ff7f0e"}
    for reg in [1, 2]:
        sub = df[df["CO_REGIAO_CURSO"] == reg].sort_values("NU_ANO")
        if sub.empty:
            continue
        ax.plot(sub["NU_ANO"], sub["media_nt_fg"], marker="o", linewidth=2,
                color=cores[reg], label=NOME_REGIAO[reg], markersize=8)
        for _, r in sub.iterrows():
            ax.annotate(f"{r['media_nt_fg']:.2f}",
                        (r["NU_ANO"], r["media_nt_fg"]),
                        textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8, color=cores[reg])
    ax.set_title("Média da NT_FG por Região (Norte vs Nordeste) — "
                 "Ciência da Computação",
                 fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Ano da edição (NU_ANO)")
    ax.set_ylabel("Média da NT_FG (escala 0–100)")
    anos = sorted(df["NU_ANO"].unique().tolist())
    ax.set_xticks(anos)
    ax.set_ylim(0, 100)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="lower left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

def gerar_tabela_final(res_ano: pd.DataFrame, out: Path) -> pd.DataFrame:
    cols = ["NU_ANO", "quantidade_cursos", "media_nt_fg", "mediana_nt_fg",
            "menor_nt_fg", "maior_nt_fg", "desvio_padrao_nt_fg"]
    tab = res_ano[cols].sort_values("NU_ANO").reset_index(drop=True)
    tab.to_csv(out, sep=";", encoding="utf-8-sig", index=False,
               quoting=csv.QUOTE_MINIMAL)
    return tab


def gerar_relatorio_md(tab: pd.DataFrame, res_regiao: pd.DataFrame,
                       res_nulos: pd.DataFrame, out: Path) -> None:
    linhas = []
    a = linhas.append

    a("# Análise da Média de NT_FG — Ciência da Computação no Norte e Nordeste — ENADE")
    a("")
    a(f"_Relatório gerado automaticamente em {date.today().isoformat()}._")
    a("")

    a("## 1. Objetivo da análise")
    a("")
    a("Descrever a evolução temporal da **média da Nota de Formação Geral (NT_FG)** "
      "nos cursos de **Ciência da Computação** ofertados nas regiões **Norte** e "
      "**Nordeste** do Brasil, usando os microdados públicos do ENADE entre 2005 e 2021.")
    a("")

    a("## 2. Base utilizada")
    a("")
    a("- **Origem:** microdados oficiais do ENADE/INEP (arquivos `arq1` e `arq3` por ano), "
      "edições de 2005, 2008, 2011, 2014, 2017 e 2021 — os anos em que Ciência da "
      "Computação foi avaliada dentro do **ciclo trienal** do exame.")
    a("- **Pipeline:** os TXT originais foram lidos por `scripts/02_processar_microdados_enade.py`, "
      "filtrados, e o resultado consolidado salvo em "
      "`dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv`.")
    a("- **Bases derivadas (entradas deste relatório):** geradas por "
      "`scripts/03_gerar_bases_analise.py` em `dados_processados/analises/`.")
    a("")

    a("## 3. Critérios de filtragem")
    a("")
    a("- `CO_GRUPO` ∈ {**40** (Ciência da Computação até 2008), "
      "**4004** (Ciência da Computação a partir de 2011)}.")
    a("- `CO_REGIAO_CURSO` ∈ {**1** (Norte), **2** (Nordeste)}.")
    a("- **Sistemas de Informação (CO_GRUPO=4006) foi excluído** deste recorte.")
    a("- Outros cursos relacionados a Computação (Engenharia de Computação, "
      "Licenciatura em Computação, ADS, Redes, Gestão de TI) também não estão incluídos.")
    a("")
    a("> **Nota sobre a recodificação 40 → 4004:** o INEP alterou o código identificador "
      "de Ciência da Computação entre as edições antigas (até 2008) e as recentes "
      "(a partir de 2011). No CSV consolidado, o `CO_GRUPO` é mantido com o **valor "
      "original de cada edição** — fidelidade ao dado bruto. Para análises temporais, "
      "ambos representam o mesmo curso.")
    a("")

    a("## 4. Tratamento metodológico")
    a("")
    a("- A conversão de `NT_FG` aceita decimais com vírgula ou ponto e descarta sentinelas "
      "(`\"\"`, `\".\"`, `\"NA\"`, `\"nan\"`, `\"null\"`, `\"None\"`) como valor nulo.")
    a("- Foi aplicada validação dura de escala: se qualquer média ultrapassar `[0, 100]`, "
      "o CSV do ano **não** é salvo. Todos os anos passaram na validação.")
    a("- A média por curso (`MEDIA_NT_FG`) foi calculada agrupando o `arq3` por "
      "`CO_CURSO` antes do `left join` com o `arq1` filtrado.")
    a("- Para análise temporal, a base foi **deduplicada por (NU_ANO, CO_CURSO)**, "
      "evitando inflar as estatísticas com a repetição de alunos do mesmo curso.")
    a("- **Registros com `MEDIA_NT_FG` nula foram separados em arquivo de controle** "
      "(`controle_nulos_media_nt_fg.csv`) e **não entraram** nos cálculos de média, "
      "mediana, desvio etc.")
    a("- **`CO_MODALIDADE` não existe** nos microdados de 2005/2008; nessas linhas "
      "a coluna fica em branco no CSV final. Para 2011–2021 o valor original do INEP "
      "é preservado.")
    a("")

    a("## 5. Resultados por ano")
    a("")
    a("| Ano | Cursos | Média | Mediana | Mínimo | Máximo | Desvio padrão |")
    a("|-----|-------:|------:|--------:|-------:|-------:|--------------:|")
    for _, r in tab.iterrows():
        a(f"| {int(r['NU_ANO'])} | {int(r['quantidade_cursos'])} | "
          f"{r['media_nt_fg']:.2f} | {r['mediana_nt_fg']:.2f} | "
          f"{r['menor_nt_fg']:.2f} | {r['maior_nt_fg']:.2f} | "
          f"{r['desvio_padrao_nt_fg']:.2f} |")
    a("")
    a("**Por região:**")
    a("")
    a("| Ano | Região | Cursos | Média | Mediana | Min | Max | Desvio |")
    a("|-----|-------:|-------:|------:|--------:|----:|----:|-------:|")
    for _, r in res_regiao.sort_values(["NU_ANO", "CO_REGIAO_CURSO"]).iterrows():
        a(f"| {int(r['NU_ANO'])} | {int(r['CO_REGIAO_CURSO'])} | "
          f"{int(r['quantidade_cursos'])} | "
          f"{r['media_nt_fg']:.2f} | {r['mediana_nt_fg']:.2f} | "
          f"{r['menor_nt_fg']:.2f} | {r['maior_nt_fg']:.2f} | "
          f"{r['desvio_padrao_nt_fg']:.2f} |")
    a("")

    a("## 6. Interpretação dos resultados")
    a("")
    a("A série temporal tem **seis pontos** — 2005, 2008, 2011, 2014, 2017 e 2021 — "
      "correspondentes às edições em que Ciência da Computação foi avaliada dentro do "
      "ciclo trienal do ENADE. Outros anos do calendário (2010, 2012, 2013, etc.) "
      "**não** trazem dados desse curso e por isso ficam fora do escopo.")
    a("")
    for _, r in tab.iterrows():
        a(f"- **{int(r['NU_ANO'])}:** média aproximada de **{r['media_nt_fg']:.2f}** "
          f"sobre {int(r['quantidade_cursos'])} cursos avaliados.")
    a("")
    a("> **Importante:** o relatório descreve apenas a variação observada nos dados. "
      "**Não se afirma causalidade.** Diferenças entre edições podem refletir "
      "características específicas da prova de cada ano, mudanças no calendário, na "
      "população avaliada, na codificação adotada pelo INEP ou em variáveis externas "
      "(p.ex., contexto pós-pandemia em 2021). Qualquer atribuição de causa específica "
      "exigiria investigação adicional.")
    a("")

    a("## 7. Observações sobre dados nulos")
    a("")
    if not res_nulos.empty:
        total_nulos = int(res_nulos["linhas_nulas"].sum())
        a(f"- Total de **{total_nulos}** registros com `MEDIA_NT_FG` nula no consolidado "
          "(cursos que existem no `arq1` mas cujos alunos não geraram nenhum `NT_FG` "
          "numérico válido no `arq3`).")
        a("- Distribuição por ano:")
        a("")
        a("| Ano | Linhas nulas | Cursos únicos com média nula |")
        a("|-----|-------------:|-----------------------------:|")
        for _, r in res_nulos.sort_values("NU_ANO").iterrows():
            a(f"| {int(r['NU_ANO'])} | {int(r['linhas_nulas'])} | "
              f"{int(r['cursos_unicos_com_media_nula'])} |")
        a("")
    a("- **Interpretação correta:** valor nulo significa **ausência de média válida**, "
      "não nota zero.")
    a("- Esses registros foram listados em `controle_nulos_media_nt_fg.csv` para auditoria, "
      "mas excluídos de todos os cálculos estatísticos.")
    a("")

    a("## 8. Limitações da análise")
    a("")
    a("- A série temporal é **descontínua** (apenas 6 pontos em 17 anos cobertos), o que "
      "limita análises de tendência refinadas.")
    a("- O recorte foi mantido **estrito** a Ciência da Computação (códigos 40/4004) — "
      "eventuais cursos sob outros `CO_GRUPO` (Engenharia de Computação, Licenciatura, "
      "ADS, Sistemas de Informação etc.) **não estão** nesta base.")
    a("- A média de cada curso é a média simples dos `NT_FG` dos alunos, sem ponderação "
      "por número de respondentes nem ajuste pela presença/ausência.")
    a("- `CO_MODALIDADE` não está disponível em 2005/2008 — análises por modalidade só "
      "podem ser feitas a partir de 2011.")
    a("- 2020 não tem edição (cancelada pela pandemia); 2021 funciona como reposição.")
    a("")

    a("## 9. Arquivos gerados")
    a("")
    a("Em `dados_processados/resultados/`:")
    a("")
    a("- `grafico_media_nt_fg_por_ano.png` — média geral por ano (linha única).")
    a("- `grafico_media_nt_fg_por_regiao.png` — comparação Norte (1) vs Nordeste (2).")
    a("- `tabela_resumo_final.csv` — tabela compacta para usar no Sheets.")
    a("- `relatorio_analise_enade.md` — este documento.")
    a("- `README_RESULTADOS.md` — guia rápido dos artefatos.")
    a("")

    out.write_text("\n".join(linhas), encoding="utf-8")


def gerar_readme(out: Path) -> None:
    md = [
        "# Resultados — Projeto ENADE-Time (Ciência da Computação, Norte/Nordeste)",
        "",
        f"_Gerado em {date.today().isoformat()}._",
        "",
        "## Recorte v2",
        "",
        "- **Curso:** Ciência da Computação (CO_GRUPO **40** em 2005/2008 e **4004** "
        "em 2011–2021).",
        "- **Regiões:** Norte (1) e Nordeste (2).",
        "- **Anos:** 2005, 2008, 2011, 2014, 2017, 2021 — edições do ciclo trienal "
        "em que Computação foi avaliada.",
        "- **Sistemas de Informação (4006) e demais cursos de TI foram excluídos.**",
        "",
        "## Estrutura desta pasta (`dados_processados/resultados/`)",
        "",
        "### CSV",
        "- **`tabela_resumo_final.csv`** — Tabela compacta com 1 linha por ano e "
        "as estatísticas principais. **Use este arquivo no Google Sheets** como "
        "ponto de partida.",
        "",
        "### Gráficos (PNG, prontos para apresentação)",
        "- **`grafico_media_nt_fg_por_ano.png`** — Evolução da média geral em 6 pontos.",
        "- **`grafico_media_nt_fg_por_regiao.png`** — Compara Norte vs Nordeste.",
        "",
        "### Documentação",
        "- **`relatorio_analise_enade.md`** — Relatório completo: objetivo, metodologia, "
        "tabelas, interpretação e limitações.",
        "- **`README_RESULTADOS.md`** — Este arquivo.",
        "",
        "## Fluxo de execução do projeto",
        "",
        "1. `scripts/01_inspecionar_estrutura.py` — diagnóstico read-only dos TXT.",
        "2. `scripts/02_processar_microdados_enade.py` — pipeline principal.",
        "3. `scripts/03_validar_csvs.py` — validação das saídas oficiais.",
        "4. `scripts/03_gerar_bases_analise.py` — bases derivadas para análise.",
        "5. `scripts/04_gerar_graficos_e_relatorio.py` — gráficos e relatório (este).",
        "",
        "## Garantias",
        "- Nenhum arquivo `.txt` original foi alterado.",
        "- Nenhum CSV oficial em `dados_processados/` foi sobrescrito por este script.",
        "- Todos os CSVs usam `sep=\";\"` e `encoding=\"utf-8-sig\"` (Google Sheets PT-BR).",
        "",
    ]
    out.write_text("\n".join(md), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 100)
    print("GERAÇÃO DE GRÁFICOS E RELATÓRIO — ENADE-Time v2")
    print("=" * 100)

    # snapshot pre-execução dos CSVs oficiais (para garantir intocados)
    snap_pre = {p: sha256_size(p) for p in CSVS_OFICIAIS if p.exists()}

    DIR_OUT.mkdir(parents=True, exist_ok=True)

    res_ano = ler(ARQ_RES_ANO)
    res_regiao = ler(ARQ_RES_ANO_REGIAO)
    res_nulos = ler(ARQ_RES_NULOS) if ARQ_RES_NULOS.exists() else pd.DataFrame()

    # gráficos
    p_g1 = DIR_OUT / "grafico_media_nt_fg_por_ano.png"
    p_g2 = DIR_OUT / "grafico_media_nt_fg_por_regiao.png"
    grafico_por_ano(res_ano, p_g1)
    grafico_por_regiao(res_regiao, p_g2)

    # remover gráfico legado da v1, se existir
    legado = DIR_OUT / "grafico_media_nt_fg_por_curso.png"
    if legado.exists():
        legado.unlink()
        print(f"  removido (legado v1): {legado.relative_to(RAIZ).as_posix()}")

    # tabela final
    p_tab = DIR_OUT / "tabela_resumo_final.csv"
    tab = gerar_tabela_final(res_ano, p_tab)

    # relatórios
    p_rel = DIR_OUT / "relatorio_analise_enade.md"
    gerar_relatorio_md(tab, res_regiao, res_nulos, p_rel)
    p_readme = DIR_OUT / "README_RESULTADOS.md"
    gerar_readme(p_readme)

    # verificação pós-execução
    snap_pos = {p: sha256_size(p) for p in CSVS_OFICIAIS if p.exists()}
    intactos = all(snap_pre.get(p) == snap_pos.get(p) for p in snap_pre)

    # ----------------------- saída no terminal -----------------------
    print("\nGráficos:")
    for p in (p_g1, p_g2):
        print(f"  {p.relative_to(RAIZ).as_posix()}")
    print("\nRelatórios:")
    for p in (p_tab, p_rel, p_readme):
        print(f"  {p.relative_to(RAIZ).as_posix()}")

    print("\nTabela final de resumo por ano:")
    print(f"{'Ano':>6} {'Cursos':>7} {'Média':>8} {'Mediana':>8} "
          f"{'Min':>7} {'Max':>7} {'Desvio':>8}")
    for _, r in tab.iterrows():
        print(f"{int(r['NU_ANO']):>6} {int(r['quantidade_cursos']):>7} "
              f"{r['media_nt_fg']:>8.4f} {r['mediana_nt_fg']:>8.4f} "
              f"{r['menor_nt_fg']:>7.4f} {r['maior_nt_fg']:>7.4f} "
              f"{r['desvio_padrao_nt_fg']:>8.4f}")

    print("\nIntegridade dos CSVs oficiais:")
    if intactos:
        print(f"  OK — nenhum dos {len(snap_pre)} CSVs oficiais foi alterado.")
        for p in snap_pre:
            print(f"     intacto: {p.relative_to(RAIZ).as_posix()}")
    else:
        print("  ATENÇÃO — alguma diferença detectada nos CSVs oficiais:")
        for p in snap_pre:
            tag = "ok" if snap_pre[p] == snap_pos.get(p) else "ALTERADO"
            print(f"     [{tag}] {p.relative_to(RAIZ).as_posix()}")

    print("=" * 100)


if __name__ == "__main__":
    main()
