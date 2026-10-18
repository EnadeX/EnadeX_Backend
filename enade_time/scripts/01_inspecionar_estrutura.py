"""
Script de inspeção dos microdados do ENADE (2010-2023).

Apenas leitura: NÃO altera, move, renomeia ou apaga arquivo nenhum.

Para cada ano:
  - Localiza dinamicamente a pasta de microdados.
  - Tenta achar arq1 e arq3 (qualquer extensão).
  - Detecta separador e encoding lendo só algumas linhas.
  - Reporta colunas presentes/ausentes, e amostra de valores de CO_GRUPO.

Saídas:
  - Resumo legível no terminal.
  - dados_processados/inspecao_estrutura.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

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

COLUNAS_ARQ1_OBRIGATORIAS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MUNIC_CURSO", "CO_UF_CURSO", "CO_REGIAO_CURSO",
]
COLUNAS_ARQ1_OPCIONAIS = ["CO_MODALIDADE"]
COLUNAS_ARQ3_OBRIGATORIAS = ["CO_CURSO", "NT_FG"]

CODIGOS_COMPUTACAO_ALVO = {40, 4004}

ENCODINGS = ["utf-8", "latin1", "cp1252"]
SEPARADORES = [";", ",", "\t"]


# ---------------------------------------------------------------------------
# Localização de arquivos
# ---------------------------------------------------------------------------

def encontrar_pasta_ano(ano: int) -> Path | None:
    candidatos = sorted(DIR_MICRODADOS.glob(f"microdados_enade_{ano}*"))
    for c in candidatos:
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
        matches = sorted(pasta_ano.glob(padrao))
        for m in matches:
            if m.is_file():
                return m
    return None


# ---------------------------------------------------------------------------
# Detecção de separador e encoding
# ---------------------------------------------------------------------------

def detectar_encoding_separador(path: Path) -> tuple[str | None, str | None, list[str]]:
    """
    Retorna (encoding, separador, colunas_header) ou (None, None, []) se falhar.
    Faz a escolha pela combinação que produzir o MAIOR número de colunas no header
    (separador errado tende a devolver 1 só "coluna" gigante).
    """
    melhor = (None, None, [], 0)  # encoding, sep, cols, n_cols
    for enc in ENCODINGS:
        for sep in SEPARADORES:
            try:
                df = pd.read_csv(
                    path,
                    sep=sep,
                    encoding=enc,
                    nrows=5,
                    dtype=str,
                    engine="python",
                    on_bad_lines="skip",
                )
            except (UnicodeDecodeError, pd.errors.ParserError, OSError):
                continue
            except Exception:
                continue
            cols = list(df.columns)
            n = len(cols)
            if n > melhor[3] and n >= 2:
                melhor = (enc, sep, cols, n)
    enc, sep, cols, _ = melhor
    return enc, sep, cols


def ler_amostra(path: Path, enc: str, sep: str, colunas: list[str] | None = None,
                nrows: int = 2000) -> pd.DataFrame | None:
    try:
        return pd.read_csv(
            path,
            sep=sep,
            encoding=enc,
            nrows=nrows,
            dtype=str,
            usecols=colunas,
            engine="python",
            on_bad_lines="skip",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Inspeção por ano
# ---------------------------------------------------------------------------

def inspecionar_ano(ano: int) -> dict:
    info = {
        "ano": ano,
        "pasta_encontrada": "",
        "arquivo_arq1": "",
        "arquivo_arq3": "",
        "arq1_encoding": "",
        "arq1_separador": "",
        "arq3_encoding": "",
        "arq3_separador": "",
        "arq1_colunas_obrigatorias_presentes": "",
        "arq1_colunas_obrigatorias_ausentes": "",
        "tem_co_modalidade": "",
        "arq3_colunas_obrigatorias_presentes": "",
        "arq3_colunas_obrigatorias_ausentes": "",
        "co_grupo_amostra": "",
        "tem_40": "",
        "tem_4004": "",
        "co_regiao_curso_amostra": "",
        "nt_fg_amostra": "",
        "status": "",
        "observacoes": "",
    }

    pasta = encontrar_pasta_ano(ano)
    if pasta is None:
        info["status"] = "pasta_nao_encontrada"
        info["observacoes"] = f"Nenhuma pasta com padrão 'microdados_enade_{ano}*'"
        return info
    info["pasta_encontrada"] = pasta.relative_to(RAIZ).as_posix()

    arq1 = encontrar_arquivo_arq(pasta, ano, 1)
    arq3 = encontrar_arquivo_arq(pasta, ano, 3)
    info["arquivo_arq1"] = arq1.relative_to(RAIZ).as_posix() if arq1 else ""
    info["arquivo_arq3"] = arq3.relative_to(RAIZ).as_posix() if arq3 else ""

    if arq1 is None or arq3 is None:
        info["status"] = "arquivo_nao_encontrado"
        faltando = []
        if arq1 is None:
            faltando.append("arq1")
        if arq3 is None:
            faltando.append("arq3")
        info["observacoes"] = "Não encontrado(s): " + ", ".join(faltando)
        return info

    # arq1
    enc1, sep1, cols1 = detectar_encoding_separador(arq1)
    info["arq1_encoding"] = enc1 or ""
    info["arq1_separador"] = repr(sep1) if sep1 else ""
    if not enc1:
        info["status"] = "erro_leitura"
        info["observacoes"] = "Não consegui detectar encoding/sep do arq1"
        return info

    presentes1 = [c for c in COLUNAS_ARQ1_OBRIGATORIAS if c in cols1]
    ausentes1 = [c for c in COLUNAS_ARQ1_OBRIGATORIAS if c not in cols1]
    info["arq1_colunas_obrigatorias_presentes"] = ",".join(presentes1)
    info["arq1_colunas_obrigatorias_ausentes"] = ",".join(ausentes1)
    info["tem_co_modalidade"] = "sim" if "CO_MODALIDADE" in cols1 else "nao"

    cols_amostra = [c for c in ("CO_GRUPO", "CO_REGIAO_CURSO") if c in cols1]
    amostra1 = ler_amostra(arq1, enc1, sep1, colunas=cols_amostra, nrows=500_000) \
        if cols_amostra else None
    if amostra1 is not None and "CO_GRUPO" in amostra1.columns:
        grupos = amostra1["CO_GRUPO"].dropna().astype(str).str.strip().unique()
        info["co_grupo_amostra"] = ",".join(sorted(grupos)[:30])
        try:
            grupos_int = {int(g) for g in grupos if g.lstrip("-").isdigit()}
            info["tem_40"] = "sim" if 40 in grupos_int else "nao"
            info["tem_4004"] = "sim" if 4004 in grupos_int else "nao"
        except ValueError:
            info["tem_40"] = "?"
            info["tem_4004"] = "?"
    if amostra1 is not None and "CO_REGIAO_CURSO" in amostra1.columns:
        regs = amostra1["CO_REGIAO_CURSO"].dropna().astype(str).str.strip().unique()
        info["co_regiao_curso_amostra"] = ",".join(sorted(regs))

    # arq3
    enc3, sep3, cols3 = detectar_encoding_separador(arq3)
    info["arq3_encoding"] = enc3 or ""
    info["arq3_separador"] = repr(sep3) if sep3 else ""
    if not enc3:
        info["status"] = "erro_leitura"
        info["observacoes"] = "Não consegui detectar encoding/sep do arq3"
        return info

    presentes3 = [c for c in COLUNAS_ARQ3_OBRIGATORIAS if c in cols3]
    ausentes3 = [c for c in COLUNAS_ARQ3_OBRIGATORIAS if c not in cols3]
    info["arq3_colunas_obrigatorias_presentes"] = ",".join(presentes3)
    info["arq3_colunas_obrigatorias_ausentes"] = ",".join(ausentes3)

    if "NT_FG" in cols3:
        amostra3 = ler_amostra(arq3, enc3, sep3, colunas=["NT_FG"], nrows=200)
        if amostra3 is not None and not amostra3.empty:
            valores = amostra3["NT_FG"].dropna().astype(str).str.strip().head(8).tolist()
            info["nt_fg_amostra"] = " | ".join(valores)

    if ausentes1 or ausentes3:
        info["status"] = "coluna_obrigatoria_ausente"
        partes = []
        if ausentes1:
            partes.append(f"arq1 sem {ausentes1}")
        if ausentes3:
            partes.append(f"arq3 sem {ausentes3}")
        info["observacoes"] = "; ".join(partes)
    else:
        info["status"] = "ok"

    return info


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    resultados = [inspecionar_ano(ano) for ano in ANOS]

    df = pd.DataFrame(resultados)
    saida = DIR_SAIDA / "inspecao_estrutura.csv"
    df.to_csv(saida, sep=";", encoding="utf-8-sig", index=False,
              quoting=csv.QUOTE_MINIMAL)

    # --- resumo no terminal ---
    print("=" * 100)
    print("INSPEÇÃO ENADE 2010-2023")
    print("=" * 100)
    for r in resultados:
        ano = r["ano"]
        status = r["status"] or "?"
        print(f"\n[{ano}] status={status}")
        print(f"  pasta:        {r['pasta_encontrada'] or '-'}")
        print(f"  arq1:         {r['arquivo_arq1'] or '-'}")
        print(f"  arq3:         {r['arquivo_arq3'] or '-'}")
        if r["arq1_encoding"]:
            print(f"  arq1 enc/sep: {r['arq1_encoding']} / {r['arq1_separador']}")
        if r["arq3_encoding"]:
            print(f"  arq3 enc/sep: {r['arq3_encoding']} / {r['arq3_separador']}")
        if r["arq1_colunas_obrigatorias_ausentes"]:
            print(f"  ! arq1 faltam: {r['arq1_colunas_obrigatorias_ausentes']}")
        if r["arq3_colunas_obrigatorias_ausentes"]:
            print(f"  ! arq3 faltam: {r['arq3_colunas_obrigatorias_ausentes']}")
        print(f"  CO_MODALIDADE: {r['tem_co_modalidade']}")
        if r["tem_40"] or r["tem_4004"]:
            print(f"  CO_GRUPO 40 (Ciência Comp. antiga): {r['tem_40']}  |  "
                  f"CO_GRUPO 4004 (Ciência Comp. atual): {r['tem_4004']}")
        if r["co_regiao_curso_amostra"]:
            print(f"  regiões obs.: {r['co_regiao_curso_amostra']}")
        if r["nt_fg_amostra"]:
            print(f"  NT_FG amostra: {r['nt_fg_amostra']}")
        if r["observacoes"]:
            print(f"  obs: {r['observacoes']}")

    print("\n" + "=" * 100)
    print(f"Resumo gravado em: {saida.relative_to(RAIZ).as_posix()}")
    print("=" * 100)

    contagem = df["status"].value_counts().to_dict()
    print("Contagem por status:")
    for k, v in contagem.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
