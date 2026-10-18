"""
Gera bases derivadas para análise no Google Sheets — v2 (apenas Ciência da Computação).

Entrada (não modificada):
  dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv

Saídas em dados_processados/analises/:
  1. cursos_unicos_com_media_nt_fg.csv    (1 linha por NU_ANO+CO_CURSO, sem nulos)
  2. resumo_temporal_por_ano.csv
  3. resumo_temporal_por_ano_regiao.csv   (agrupado por NU_ANO + CO_REGIAO_CURSO)
  4. controle_nulos_media_nt_fg.csv       (registros com MEDIA_NT_FG nula)
  5. resumo_nulos_por_ano.csv

  (resumo_temporal_por_ano_e_curso.csv foi removido na v2: sem 4006, a comparação
   por CO_GRUPO só refletia a recodificação 40 -> 4004, não cursos distintos.)

Regras:
  - Os agregados usam APENAS linhas com MEDIA_NT_FG não nula.
  - A base por curso (item 1) é deduplicada por (NU_ANO, CO_CURSO).
  - Os nulos vão SOMENTE para os relatórios 4 e 5 — nunca entram nos cálculos.
  - CSVs sempre: sep=';', encoding='utf-8-sig', index=False.
  - Não altera nenhum arquivo de entrada nem os CSVs oficiais.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


RAIZ = Path(__file__).resolve().parent.parent
DIR_IN = RAIZ / "dados_processados"
DIR_OUT = DIR_IN / "analises"

ARQ_CONS = DIR_IN / "microdados_enade_2005_2021_filtrado_consolidado.csv"


def salvar(df: pd.DataFrame, nome: str) -> Path:
    DIR_OUT.mkdir(parents=True, exist_ok=True)
    path = DIR_OUT / nome
    df.to_csv(path, sep=";", encoding="utf-8-sig", index=False,
              quoting=csv.QUOTE_MINIMAL)
    return path


def resumo_estatistico(df: pd.DataFrame, grupos: list[str]) -> pd.DataFrame:
    """Agrega MEDIA_NT_FG com as métricas pedidas (sobre 1 linha por curso)."""
    out = (df.groupby(grupos, as_index=False)
             .agg(quantidade_cursos=("CO_CURSO", "nunique"),
                  media_nt_fg=("MEDIA_NT_FG", "mean"),
                  mediana_nt_fg=("MEDIA_NT_FG", "median"),
                  menor_nt_fg=("MEDIA_NT_FG", "min"),
                  maior_nt_fg=("MEDIA_NT_FG", "max"),
                  desvio_padrao_nt_fg=("MEDIA_NT_FG", "std")))
    for c in ["media_nt_fg", "mediana_nt_fg", "menor_nt_fg",
              "maior_nt_fg", "desvio_padrao_nt_fg"]:
        out[c] = out[c].round(4)
    return out


def main() -> None:
    print("=" * 100)
    print("GERAÇÃO DE BASES DERIVADAS PARA ANÁLISE")
    print("=" * 100)
    print(f"Lendo: {ARQ_CONS.relative_to(RAIZ).as_posix()}")
    cons = pd.read_csv(ARQ_CONS, sep=";", encoding="utf-8-sig")
    print(f"  total linhas no consolidado: {len(cons)}")

    # --- 5) controle de nulos (linha a linha, sem dedup) ---
    nulos = cons[cons["MEDIA_NT_FG"].isna()].copy()
    df_ctrl = nulos[["NU_ANO", "CO_CURSO", "CO_GRUPO", "CO_REGIAO_CURSO",
                     "CO_UF_CURSO", "CO_IES", "CO_MUNIC_CURSO"]]
    p5 = salvar(df_ctrl, "controle_nulos_media_nt_fg.csv")

    # --- 6) resumo dos nulos por ano ---
    df_resnul = (nulos.groupby("NU_ANO", as_index=False)
                       .agg(linhas_nulas=("CO_CURSO", "size"),
                            cursos_unicos_com_media_nula=("CO_CURSO", "nunique")))
    p6 = salvar(df_resnul, "resumo_nulos_por_ano.csv")

    # --- base limpa para cálculos ---
    base = cons[cons["MEDIA_NT_FG"].notna()].copy()

    # --- 1) cursos únicos com média válida ---
    cursos = (base.drop_duplicates(subset=["NU_ANO", "CO_CURSO"])
                  [["NU_ANO", "CO_CURSO", "CO_GRUPO", "CO_REGIAO_CURSO",
                    "CO_UF_CURSO", "CO_MODALIDADE", "MEDIA_NT_FG"]]
                  .sort_values(["NU_ANO", "CO_CURSO"])
                  .reset_index(drop=True))
    p1 = salvar(cursos, "cursos_unicos_com_media_nt_fg.csv")

    # --- 2/3) resumos (sem mais "por_ano_e_curso" na v2) ---
    p2 = salvar(resumo_estatistico(cursos, ["NU_ANO"]),
                "resumo_temporal_por_ano.csv")
    p3 = salvar(resumo_estatistico(cursos, ["NU_ANO", "CO_REGIAO_CURSO"]),
                "resumo_temporal_por_ano_regiao.csv")

    # remove arquivo legado da v1, se existir
    legado = DIR_OUT / "resumo_temporal_por_ano_e_curso.csv"
    if legado.exists():
        legado.unlink()
        print(f"  removido (legado v1): {legado.relative_to(RAIZ).as_posix()}")

    # --- resumo no terminal ---
    print()
    print("-" * 100)
    print("RESUMO")
    print("-" * 100)
    print(f"Total de cursos únicos (NU_ANO+CO_CURSO) com média válida: {len(cursos)}")
    print()
    print("Por ano:")
    por_ano = (cursos.groupby("NU_ANO")
                     .agg(qtd_cursos=("CO_CURSO", "nunique"),
                          media=("MEDIA_NT_FG", "mean"),
                          minimo=("MEDIA_NT_FG", "min"),
                          maximo=("MEDIA_NT_FG", "max")))
    for ano, row in por_ano.iterrows():
        print(f"  {int(ano)}: cursos={int(row['qtd_cursos']):>4}  "
              f"media={row['media']:.4f}  "
              f"min={row['minimo']:.4f}  max={row['maximo']:.4f}")

    mn = float(cursos["MEDIA_NT_FG"].min())
    mx = float(cursos["MEDIA_NT_FG"].max())
    print()
    print(f"Escala global: min={mn:.4f}  max={mx:.4f}", end="")
    if 0 <= mn and mx <= 100:
        print("  -> OK (dentro de [0, 100])")
    else:
        print("  -> FORA DA ESCALA ESPERADA")

    print()
    print("Arquivos gerados:")
    for p in (p1, p2, p3, p5, p6):
        print(f"  {p.relative_to(RAIZ).as_posix()}")
    print("=" * 100)


if __name__ == "__main__":
    main()
