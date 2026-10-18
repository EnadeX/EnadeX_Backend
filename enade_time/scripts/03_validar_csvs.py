"""
Validação dos CSVs já gerados em dados_processados/.
Somente leitura. NÃO reprocessa TXT, NÃO altera CSVs nem scripts.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


RAIZ = Path(__file__).resolve().parent.parent
DIR = RAIZ / "dados_processados"

COLUNAS_ESPERADAS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MODALIDADE", "CO_MUNIC_CURSO", "CO_UF_CURSO",
    "CO_REGIAO_CURSO", "MEDIA_NT_FG",
]
COLUNAS_AMOSTRA = ["NU_ANO", "CO_CURSO", "CO_GRUPO",
                   "CO_REGIAO_CURSO", "MEDIA_NT_FG"]

CODIGOS_COMPUTACAO = {40, 4004}
ANOS_OK_ESPERADOS = {2005, 2008, 2011, 2014, 2017, 2021}
ANOS_VAZIOS_ESPERADOS: set[int] = set()
ANOS_SEM_MODALIDADE = {2005, 2008}
SOMA_ESPERADA: int | None = None  # preenchido em runtime (sem hard-coded total)

ARQUIVOS_ANUAIS = {
    2005: "microdados_enade_2005_filtrado.csv",
    2008: "microdados_enade_2008_filtrado.csv",
    2011: "microdados_enade_2011_filtrado.csv",
    2014: "microdados_enade_2014_filtrado.csv",
    2017: "microdados_enade_2017_filtrado.csv",
    2021: "microdados_enade_2021_filtrado.csv",
}
CONS_FILE = "microdados_enade_2005_2021_filtrado_consolidado.csv"
REL_FILE = "relatorio_processamento.csv"

problemas: list[str] = []


def ler(nome: str) -> pd.DataFrame:
    return pd.read_csv(DIR / nome, sep=";", encoding="utf-8-sig")


def sep() -> None:
    print("-" * 100)


# ---------------------------------------------------------------------------
# 1) CSVs anuais
# ---------------------------------------------------------------------------
print("=" * 100)
print("VALIDAÇÃO DOS CSVS — DADOS_PROCESSADOS/")
print("=" * 100)

linhas_por_ano: dict[int, int] = {}

for ano, nome in ARQUIVOS_ANUAIS.items():
    sep()
    print(f"[{ano}] {nome}")
    df = ler(nome)
    linhas_por_ano[ano] = len(df)

    print(f"  linhas       : {len(df)}")
    print(f"  colunas      : {len(df.columns)}")
    print(f"  nomes cols   : {list(df.columns)}")
    print(f"  NU_ANO únicos: {sorted(df['NU_ANO'].dropna().unique().tolist())}")
    print(f"  CO_GRUPO     : {sorted(df['CO_GRUPO'].dropna().unique().tolist())}")
    print(f"  CO_REGIAO    : {sorted(df['CO_REGIAO_CURSO'].dropna().unique().tolist())}")
    print(f"  CO_CURSO uniq: {df['CO_CURSO'].nunique()}")
    nulas = int(df["MEDIA_NT_FG"].isna().sum())
    print(f"  MEDIA nulas  : {nulas}")
    if df["MEDIA_NT_FG"].notna().any():
        mn = float(df["MEDIA_NT_FG"].min())
        mx = float(df["MEDIA_NT_FG"].max())
        mean = float(df["MEDIA_NT_FG"].mean())
        print(f"  MEDIA min    : {mn:.4f}")
        print(f"  MEDIA max    : {mx:.4f}")
        print(f"  MEDIA mean   : {mean:.4f}")
    print("  10 primeiras (NU_ANO, CO_CURSO, CO_GRUPO, CO_REGIAO_CURSO, MEDIA_NT_FG):")
    amostra = df[COLUNAS_AMOSTRA].head(10)
    for _, row in amostra.iterrows():
        print(f"    {int(row['NU_ANO'])}  curso={int(row['CO_CURSO']):>6}  "
              f"grupo={int(row['CO_GRUPO'])}  regiao={int(row['CO_REGIAO_CURSO'])}  "
              f"media={row['MEDIA_NT_FG']:.4f}")

    # --- 2) ordem e nomes das colunas ---
    if list(df.columns) != COLUNAS_ESPERADAS:
        problemas.append(f"[{ano}] colunas fora do padrão: {list(df.columns)}")

    # --- 3) regras de domínio ---
    grupos_invalidos = set(df["CO_GRUPO"].dropna().unique()) - CODIGOS_COMPUTACAO
    if grupos_invalidos:
        problemas.append(f"[{ano}] CO_GRUPO inválido encontrado: {grupos_invalidos}")
    regs_invalidas = set(df["CO_REGIAO_CURSO"].dropna().unique()) - {1, 2}
    if regs_invalidas:
        problemas.append(f"[{ano}] CO_REGIAO_CURSO inválida: {regs_invalidas}")
    if df["MEDIA_NT_FG"].notna().any():
        if df["MEDIA_NT_FG"].min() < 0:
            problemas.append(f"[{ano}] MEDIA_NT_FG < 0 encontrada "
                             f"(min={df['MEDIA_NT_FG'].min()})")
        if df["MEDIA_NT_FG"].max() > 100:
            problemas.append(f"[{ano}] MEDIA_NT_FG > 100 encontrada "
                             f"(max={df['MEDIA_NT_FG'].max()})")
    # CO_MODALIDADE: ausência total esperada em 2005/2008; presença esperada nos demais
    mod_nulas = int(df["CO_MODALIDADE"].isna().sum())
    print(f"  CO_MODALIDADE nulas: {mod_nulas} / {len(df)}")
    if ano in ANOS_SEM_MODALIDADE:
        if mod_nulas != len(df):
            problemas.append(f"[{ano}] CO_MODALIDADE deveria estar 100% nula "
                             f"(observado: {mod_nulas}/{len(df)})")
    else:
        if mod_nulas == len(df):
            problemas.append(f"[{ano}] CO_MODALIDADE inesperadamente 100% nula")

# ---------------------------------------------------------------------------
# 4) Consolidado
# ---------------------------------------------------------------------------
sep()
print(f"\n[CONSOLIDADO] {CONS_FILE}")
cons = ler(CONS_FILE)
print(f"  total de linhas      : {len(cons)}")

print("  linhas por NU_ANO    :")
for ano, n in cons["NU_ANO"].value_counts().sort_index().items():
    print(f"    {int(ano)}: {int(n)}")

print("  linhas por CO_GRUPO  :")
for g, n in cons["CO_GRUPO"].value_counts().sort_index().items():
    print(f"    {int(g)}: {int(n)}")

print("  linhas por CO_REGIAO :")
for r, n in cons["CO_REGIAO_CURSO"].value_counts().sort_index().items():
    print(f"    {int(r)}: {int(n)}")

print("  MEDIA_NT_FG (min / max / mean) por ano:")
agg = cons.groupby("NU_ANO")["MEDIA_NT_FG"].agg(["min", "max", "mean", "count"])
for ano, row in agg.iterrows():
    print(f"    {int(ano)}: min={row['min']:.4f}  max={row['max']:.4f}  "
          f"mean={row['mean']:.4f}  n={int(row['count'])}")

# colunas, ordem e regras do consolidado
if list(cons.columns) != COLUNAS_ESPERADAS:
    problemas.append(f"[consolidado] colunas fora do padrão: {list(cons.columns)}")
grupos_cons = set(cons["CO_GRUPO"].dropna().unique()) - CODIGOS_COMPUTACAO
if grupos_cons:
    problemas.append(f"[consolidado] CO_GRUPO inválido: {grupos_cons}")
regs_cons = set(cons["CO_REGIAO_CURSO"].dropna().unique()) - {1, 2}
if regs_cons:
    problemas.append(f"[consolidado] CO_REGIAO_CURSO inválida: {regs_cons}")
if cons["MEDIA_NT_FG"].notna().any():
    if cons["MEDIA_NT_FG"].min() < 0:
        problemas.append(f"[consolidado] MEDIA_NT_FG < 0 (min={cons['MEDIA_NT_FG'].min()})")
    if cons["MEDIA_NT_FG"].max() > 100:
        problemas.append(f"[consolidado] MEDIA_NT_FG > 100 (max={cons['MEDIA_NT_FG'].max()})")
nulas_cons = int(cons["MEDIA_NT_FG"].isna().sum())
print(f"\n[INFO] MEDIA_NT_FG nula no consolidado: {nulas_cons} "
      f"({nulas_cons/len(cons)*100:.2f}%) — esperado pelo left join")

# ---------------------------------------------------------------------------
# 5) Soma dos anuais == consolidado
# ---------------------------------------------------------------------------
sep()
soma = sum(linhas_por_ano.values())
parcelas = " + ".join(f"{linhas_por_ano[a]}" for a in sorted(linhas_por_ano))
anos_str = " + ".join(str(a) for a in sorted(linhas_por_ano))
print(f"\n[SOMA CHECK]  {anos_str} = {parcelas} = {soma}")
print(f"              consolidado            = {len(cons)}")
if soma != len(cons):
    problemas.append(f"Soma dos anuais ({soma}) != consolidado ({len(cons)})")

# ---------------------------------------------------------------------------
# 6) Relatório
# ---------------------------------------------------------------------------
sep()
print(f"\n[RELATÓRIO] {REL_FILE}")
rel = ler(REL_FILE)
print(f"  linhas: {len(rel)}  colunas: {list(rel.columns)}")

anos_ok = set(rel.loc[rel["status"] == "ok", "ano"].astype(int).tolist())
anos_vazio = set(rel.loc[rel["status"] == "vazio_apos_filtro", "ano"].astype(int).tolist())
anos_nf = set(rel.loc[rel["status"] == "arquivo_nao_encontrado", "ano"].astype(int).tolist())
anos_erro = set(rel.loc[rel["status"].isin(
    ["erro_conversao_nt_fg", "erro_leitura", "coluna_obrigatoria_ausente"]
), "ano"].astype(int).tolist())

print(f"  status=ok                    : {sorted(anos_ok)}")
print(f"  status=vazio_apos_filtro     : {sorted(anos_vazio)}")
print(f"  status=arquivo_nao_encontrado: {sorted(anos_nf)}")
print(f"  status=erro_*                : {sorted(anos_erro)}")

vals_valid = rel["validacao_media_nt_fg"].fillna("").unique().tolist()
print(f"  validacao_media_nt_fg vals   : {sorted(vals_valid)}")

if anos_ok != ANOS_OK_ESPERADOS:
    problemas.append(f"anos ok diferem do esperado: {anos_ok} vs {ANOS_OK_ESPERADOS}")
if anos_vazio != ANOS_VAZIOS_ESPERADOS:
    problemas.append(f"anos vazios diferem do esperado: "
                     f"{anos_vazio} vs {ANOS_VAZIOS_ESPERADOS}")
if anos_nf:
    problemas.append(f"anos com arquivo_nao_encontrado (não esperado em v2): {anos_nf}")
if anos_erro:
    problemas.append(f"Há anos com status de erro: {anos_erro}")

erros_valid = set(vals_valid) & {"erro_media_acima_100", "erro_media_abaixo_0"}
if erros_valid:
    problemas.append(f"validacao_media_nt_fg com erros: {erros_valid}")

# ---------------------------------------------------------------------------
# Veredicto
# ---------------------------------------------------------------------------
print("\n" + "=" * 100)
if not problemas:
    print("BASE VALIDADA COM SUCESSO")
else:
    print(f"BASE TEM PROBLEMAS ({len(problemas)}):")
    for p in problemas:
        print(f"  - {p}")
print("=" * 100)
