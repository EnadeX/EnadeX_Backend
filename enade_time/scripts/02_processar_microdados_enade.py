"""
Pipeline de processamento dos microdados do ENADE — recorte v2.

Anos processados: 2005, 2008, 2011, 2014, 2017, 2021.
Filtro de curso: APENAS Ciência da Computação.
  - 2005, 2008: CO_GRUPO = 40
  - 2011, 2014, 2017, 2021: CO_GRUPO = 4004
Filtro de região: Norte (1) e Nordeste (2).

Lógica por ano:
  1. Lê arq1 (10 colunas-padrão; CO_MODALIDADE pode estar ausente em 2005/2008).
  2. Filtra CO_REGIAO_CURSO em {1,2} e CO_GRUPO em {40, 4004}.
  3. Lê arq3 (apenas CO_CURSO e NT_FG).
  4. Converte NT_FG tratando vírgula/ponto e sentinelas de NA.
  5. Agrupa NT_FG por CO_CURSO -> MEDIA_NT_FG.
  6. Valida escala [0, 100]. Se falhar, NÃO salva CSV do ano.
  7. Imprime amostra de médias antes de salvar.
  8. Left join no arq1 filtrado e salva CSV.

CSVs sempre: sep=';', encoding='utf-8-sig', index=False.
Arquivos .txt originais nunca são alterados.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd


RAIZ = Path(__file__).resolve().parent.parent
DIR_SAIDA = RAIZ / "dados_processados"


def _dir_microdados() -> Path:
    """Onde estão as pastas microdados_enade_*: ENADE_TIME_MICRODADOS_DIR ou candidatos padrão.

    Os TXT brutos do INEP (3+ GB) NÃO entram no repositório do grupo. Candidatos:
    1. env ENADE_TIME_MICRODADOS_DIR;
    2. <pai do EnadeX>/microdados (convenção do ecossistema — mesma do educluster);
    3. <pai do EnadeX>/ENADE (repositório original do subprojeto);
    4. o próprio enade_time/ (layout antigo).
    """
    import os as _os
    env = _os.environ.get("ENADE_TIME_MICRODADOS_DIR")
    candidatos = ([Path(env)] if env else []) + [
        RAIZ.parent.parent / "microdados",
        RAIZ.parent.parent / "ENADE",
        RAIZ,
    ]
    for c in candidatos:
        try:
            if c.is_dir() and any(c.glob("microdados_enade_*")):
                return c
        except OSError:
            continue
    return candidatos[0]


DIR_MICRODADOS = _dir_microdados()


def _dir_microdados() -> Path:
    """Onde estão as pastas microdados_enade_*: ENADE_TIME_MICRODADOS_DIR ou candidatos padrão.

    Os TXT brutos do INEP (3+ GB) NÃO entram no repositório do grupo. Candidatos:
    1. env ENADE_TIME_MICRODADOS_DIR;
    2. <pai do EnadeX>/microdados (convenção do ecossistema — mesma do educluster);
    3. <pai do EnadeX>/ENADE (repositório original do subprojeto);
    4. o próprio enade_time/ (layout antigo).
    """
    import os as _os
    env = _os.environ.get("ENADE_TIME_MICRODADOS_DIR")
    candidatos = ([Path(env)] if env else []) + [
        RAIZ.parent.parent / "microdados",
        RAIZ.parent.parent / "ENADE",
        RAIZ,
    ]
    for c in candidatos:
        try:
            if c.is_dir() and any(c.glob("microdados_enade_*")):
                return c
        except OSError:
            continue
    return candidatos[0]


DIR_MICRODADOS = _dir_microdados()

ANOS = [2005, 2008, 2011, 2014, 2017, 2021]

COLUNAS_FINAIS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MODALIDADE", "CO_MUNIC_CURSO", "CO_UF_CURSO",
    "CO_REGIAO_CURSO", "MEDIA_NT_FG",
]
COLUNAS_ARQ1_OBRIGATORIAS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MUNIC_CURSO", "CO_UF_CURSO", "CO_REGIAO_CURSO",
]
COLUNAS_ARQ1_OPCIONAIS = ["CO_MODALIDADE"]
COLUNAS_ARQ3 = ["CO_CURSO", "NT_FG"]

REGIOES_PERMITIDAS = {1, 2}
CODIGOS_COMPUTACAO = {40, 4004}

ENCODINGS = ["utf-8", "latin1", "cp1252"]
SEPARADORES = [";", ",", "\t"]

SENTINELAS_NA = {"", ".", "NA", "N/A", "nan", "NaN", "NAN", "null", "Null",
                 "NULL", "None", "none"}

NOME_CONSOLIDADO = "microdados_enade_2005_2021_filtrado_consolidado.csv"


# ---------------------------------------------------------------------------
# Localização de arquivos
# ---------------------------------------------------------------------------

def encontrar_pasta_ano(ano: int) -> Path | None:
    for c in sorted(DIR_MICRODADOS.glob(f"microdados_enade_{ano}*")):
        if c.is_dir():
            return c
    return None


def encontrar_arquivo_arq(pasta_ano: Path, ano: int, n_arq: int) -> Path | None:
    padroes = [
        f"**/microdados{ano}_arq{n_arq}.*",
        f"**/microdados_{ano}_arq{n_arq}.*",
        f"**/microdados{ano}_arq{n_arq}*",
    ]
    for padrao in padroes:
        for m in sorted(pasta_ano.glob(padrao)):
            if m.is_file():
                return m
    return None


# ---------------------------------------------------------------------------
# Leitura robusta
# ---------------------------------------------------------------------------

def detectar_encoding_separador(path: Path) -> tuple[str | None, str | None, list[str]]:
    melhor = (None, None, [], 0)
    for enc in ENCODINGS:
        for sep in SEPARADORES:
            try:
                df = pd.read_csv(
                    path, sep=sep, encoding=enc, nrows=5,
                    dtype=str, engine="python", on_bad_lines="skip",
                )
            except Exception:
                continue
            n = len(df.columns)
            if n > melhor[3] and n >= 2:
                melhor = (enc, sep, list(df.columns), n)
    return melhor[0], melhor[1], melhor[2]


def ler_arquivo(path: Path, colunas: list[str] | None = None) -> tuple[pd.DataFrame | None, str, str]:
    enc, sep, header = detectar_encoding_separador(path)
    if enc is None:
        return None, "", ""
    use = None
    if colunas is not None:
        use = [c for c in colunas if c in header]
        if not use:
            return None, enc, sep
    df = pd.read_csv(
        path, sep=sep, encoding=enc, dtype=str,
        usecols=use, engine="python", on_bad_lines="skip",
    )
    return df, enc, sep


# ---------------------------------------------------------------------------
# Conversões
# ---------------------------------------------------------------------------

def converter_inteiro(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip().str.strip('"').str.strip("'")
    s = s.replace(list(SENTINELAS_NA), np.nan)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def converter_nt_fg(serie: pd.Series) -> pd.Series:
    """Converte NT_FG para float preservando escala 0-100."""
    s = serie.astype(str).str.strip().str.strip('"').str.strip("'")
    s = s.replace(list(SENTINELAS_NA), np.nan)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


# ---------------------------------------------------------------------------
# Processamento por ano
# ---------------------------------------------------------------------------

def processar_ano(ano: int) -> tuple[dict, pd.DataFrame | None]:
    rel: dict = {
        "ano": ano,
        "pasta_encontrada": "",
        "arquivo_arq1_encontrado": "",
        "arquivo_arq3_encontrado": "",
        "status": "",
        "linhas_arq1_original": 0,
        "linhas_arq1_filtrado": 0,
        "qtd_cursos_unicos_filtrados": 0,
        "qtd_cursos_com_media_nt_fg": 0,
        "qtd_cursos_sem_media_nt_fg": 0,
        "menor_media_nt_fg": "",
        "maior_media_nt_fg": "",
        "validacao_media_nt_fg": "",
        "observacoes": "",
    }

    pasta = encontrar_pasta_ano(ano)
    if pasta is None:
        rel["status"] = "arquivo_nao_encontrado"
        rel["observacoes"] = f"Pasta 'microdados_enade_{ano}*' não existe"
        return rel, None
    rel["pasta_encontrada"] = pasta.relative_to(RAIZ).as_posix()

    arq1 = encontrar_arquivo_arq(pasta, ano, 1)
    arq3 = encontrar_arquivo_arq(pasta, ano, 3)
    rel["arquivo_arq1_encontrado"] = arq1.relative_to(RAIZ).as_posix() if arq1 else ""
    rel["arquivo_arq3_encontrado"] = arq3.relative_to(RAIZ).as_posix() if arq3 else ""

    if arq1 is None or arq3 is None:
        rel["status"] = "arquivo_nao_encontrado"
        falt = [n for n, p in (("arq1", arq1), ("arq3", arq3)) if p is None]
        rel["observacoes"] = "Não encontrado(s): " + ", ".join(falt)
        return rel, None

    # ---------- arq1 ----------
    colunas_pedidas = COLUNAS_ARQ1_OBRIGATORIAS + COLUNAS_ARQ1_OPCIONAIS
    df1, enc1, sep1 = ler_arquivo(arq1, colunas=colunas_pedidas)
    if df1 is None:
        rel["status"] = "erro_leitura"
        rel["observacoes"] = "Falha ao ler arq1"
        return rel, None

    rel["linhas_arq1_original"] = len(df1)

    ausentes_obrig = [c for c in COLUNAS_ARQ1_OBRIGATORIAS if c not in df1.columns]
    if ausentes_obrig:
        rel["status"] = "coluna_obrigatoria_ausente"
        rel["observacoes"] = f"arq1 sem colunas obrigatórias: {ausentes_obrig}"
        return rel, None

    obs_extra = []
    if "CO_MODALIDADE" not in df1.columns:
        df1["CO_MODALIDADE"] = pd.NA
        obs_extra.append("CO_MODALIDADE ausente no arq1 — preenchida com NA")

    for col in COLUNAS_ARQ1_OBRIGATORIAS + COLUNAS_ARQ1_OPCIONAIS:
        df1[col] = converter_inteiro(df1[col])

    df1f = df1[
        df1["CO_REGIAO_CURSO"].isin(REGIOES_PERMITIDAS)
        & df1["CO_GRUPO"].isin(CODIGOS_COMPUTACAO)
    ].copy()
    rel["linhas_arq1_filtrado"] = len(df1f)
    rel["qtd_cursos_unicos_filtrados"] = int(df1f["CO_CURSO"].nunique())

    if df1f.empty:
        rel["status"] = "vazio_apos_filtro"
        rel["validacao_media_nt_fg"] = "sem_media_calculada"
        rel["observacoes"] = ("; ".join(
            [*obs_extra, "Nenhum aluno de CO_GRUPO 40/4004 nas regiões 1/2"]))
        print(f"\n[{ano}] vazio após filtro")
        return rel, None

    # ---------- arq3 ----------
    df3, enc3, sep3 = ler_arquivo(arq3, colunas=COLUNAS_ARQ3)
    if df3 is None or "NT_FG" not in df3.columns or "CO_CURSO" not in df3.columns:
        rel["status"] = "coluna_obrigatoria_ausente"
        rel["observacoes"] = "; ".join([*obs_extra, "arq3 sem NT_FG ou CO_CURSO"])
        return rel, None

    df3["CO_CURSO"] = converter_inteiro(df3["CO_CURSO"])
    df3["NT_FG"] = converter_nt_fg(df3["NT_FG"])
    df3 = df3.dropna(subset=["CO_CURSO", "NT_FG"])

    medias = (df3.groupby("CO_CURSO", as_index=False)["NT_FG"]
              .mean()
              .rename(columns={"NT_FG": "MEDIA_NT_FG"}))

    # ---------- validação ----------
    if medias.empty:
        rel["status"] = "vazio_apos_filtro"
        rel["validacao_media_nt_fg"] = "sem_media_calculada"
        rel["observacoes"] = "; ".join(
            [*obs_extra, "Nenhum NT_FG válido no arq3 para calcular média"])
        print(f"\n[{ano}] sem médias calculáveis no arq3")
        return rel, None

    minimo = float(medias["MEDIA_NT_FG"].min())
    maximo = float(medias["MEDIA_NT_FG"].max())
    rel["menor_media_nt_fg"] = round(minimo, 4)
    rel["maior_media_nt_fg"] = round(maximo, 4)

    # ---------- amostra antes de salvar ----------
    print(f"\n[{ano}] Amostra MEDIA_NT_FG por CO_CURSO (10 primeiras):")
    amostra = medias.sort_values("CO_CURSO").head(10)
    for _, row in amostra.iterrows():
        print(f"   CO_CURSO={int(row['CO_CURSO']):>7}   "
              f"MEDIA_NT_FG={row['MEDIA_NT_FG']:.4f}")
    print(f"   min={minimo:.4f}  max={maximo:.4f}  "
          f"mean={medias['MEDIA_NT_FG'].mean():.4f}  count={len(medias)}")

    if maximo > 100:
        rel["status"] = "erro_conversao_nt_fg"
        rel["validacao_media_nt_fg"] = "erro_media_acima_100"
        rel["observacoes"] = "; ".join(
            [*obs_extra,
             f"MEDIA_NT_FG máxima = {maximo:.4f} > 100. CSV NÃO foi salvo."])
        print(f"   ERRO: max={maximo:.4f} > 100 -> CSV NÃO será salvo")
        return rel, None
    if minimo < 0:
        rel["status"] = "erro_conversao_nt_fg"
        rel["validacao_media_nt_fg"] = "erro_media_abaixo_0"
        rel["observacoes"] = "; ".join(
            [*obs_extra,
             f"MEDIA_NT_FG mínima = {minimo:.4f} < 0. CSV NÃO foi salvo."])
        print(f"   ERRO: min={minimo:.4f} < 0 -> CSV NÃO será salvo")
        return rel, None

    rel["validacao_media_nt_fg"] = "ok"

    # ---------- merge ----------
    final = df1f.merge(medias, on="CO_CURSO", how="left")
    final = final[COLUNAS_FINAIS]

    rel["qtd_cursos_com_media_nt_fg"] = int(final.loc[
        final["MEDIA_NT_FG"].notna(), "CO_CURSO"].nunique())
    rel["qtd_cursos_sem_media_nt_fg"] = int(final.loc[
        final["MEDIA_NT_FG"].isna(), "CO_CURSO"].nunique())

    # ---------- salvar ----------
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    saida = DIR_SAIDA / f"microdados_enade_{ano}_filtrado.csv"
    final.to_csv(saida, sep=";", encoding="utf-8-sig", index=False,
                 quoting=csv.QUOTE_MINIMAL)
    rel["status"] = "ok"
    rel["observacoes"] = "; ".join(obs_extra) if obs_extra else ""
    print(f"   salvo: {saida.relative_to(RAIZ).as_posix()}  (linhas={len(final)})")
    return rel, final


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)

    relatorios: list[dict] = []
    consolidado: list[pd.DataFrame] = []

    print("=" * 100)
    print("PROCESSAMENTO ENADE — CIÊNCIA DA COMPUTAÇÃO (40/4004) — Norte/Nordeste")
    print("=" * 100)

    for ano in ANOS:
        rel, df = processar_ano(ano)
        relatorios.append(rel)
        if df is not None and rel["status"] == "ok":
            consolidado.append(df)

    # relatório
    rel_df = pd.DataFrame(relatorios)
    rel_path = DIR_SAIDA / "relatorio_processamento.csv"
    rel_df.to_csv(rel_path, sep=";", encoding="utf-8-sig", index=False,
                  quoting=csv.QUOTE_MINIMAL)

    # consolidado
    cons_path: Path | None = None
    if consolidado:
        cons = pd.concat(consolidado, ignore_index=True)
        cons_path = DIR_SAIDA / NOME_CONSOLIDADO
        cons.to_csv(cons_path, sep=";", encoding="utf-8-sig", index=False,
                    quoting=csv.QUOTE_MINIMAL)

    # resumo final
    print("\n" + "=" * 100)
    print("RESUMO FINAL")
    print("=" * 100)
    for r in relatorios:
        print(f"  [{r['ano']}] status={r['status']:<25} "
              f"linhas_filt={r['linhas_arq1_filtrado']:>6}  "
              f"valid={r['validacao_media_nt_fg'] or '-'}")
    print(f"\nRelatório:    {rel_path.relative_to(RAIZ).as_posix()}")
    if cons_path is not None:
        print(f"Consolidado:  {cons_path.relative_to(RAIZ).as_posix()}  "
              f"(linhas={sum(len(d) for d in consolidado)})")
    else:
        print("Consolidado:  (nenhum ano produziu CSV válido)")


if __name__ == "__main__":
    main()
