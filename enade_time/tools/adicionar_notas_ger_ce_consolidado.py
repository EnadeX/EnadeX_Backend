"""
Utilitário SEGURO — acrescenta MEDIA_NT_GER e MEDIA_NT_CE ao CSV consolidado.

Objetivo
--------
O consolidado atual traz apenas MEDIA_NT_FG (média da nota de Formação Geral
por CO_CURSO). Este utilitário adiciona duas colunas análogas, extraídas dos
mesmos arquivos brutos (arq3) com a MESMA lógica/filtros que geraram o
consolidado:

    MEDIA_NT_GER  -> média de NT_GER (nota geral) por CO_CURSO
    MEDIA_NT_CE   -> média de NT_CE  (componente específico) por CO_CURSO

Garantias de segurança
----------------------
1. NÃO altera TXT/CSV brutos em microdados_enade_*.
2. NÃO altera os scripts numerados nem o schema/API/frontend.
3. Reconstrói os mesmos registros dos brutos e VERIFICA, linha a linha e na
   mesma ordem, que MEDIA_NT_FG e todas as colunas inteiras batem 100% com o
   consolidado. Só então salva.
4. As colunas antigas são lidas como STRING e regravadas VERBATIM (nenhum
   valor antigo é reparseado/reformatado). Apenas duas colunas novas são
   anexadas ao final.
5. Faz backup com timestamp imediatamente antes de gravar.
6. Preserva nulos como nulos (NaN -> campo vazio); não inventa valores.

Se a reconstrução não bater 100%, NADA é gravado e o motivo é reportado.

Uso
---
    C:\\Projetos\\ENADE> .venv\\Scripts\\python.exe tools\\adicionar_notas_ger_ce_consolidado.py

Opcional:
    --dry-run   executa toda a validação mas NÃO grava (apenas relatório).
"""

from __future__ import annotations

import csv
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes — cópia fiel das usadas em scripts/02 e etl/processar_ano.py
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
NOME_CONSOLIDADO = "microdados_enade_2005_2021_filtrado_consolidado.csv"
CAMINHO_CONSOLIDADO = DIR_SAIDA / NOME_CONSOLIDADO

ANOS = [2005, 2008, 2011, 2014, 2017, 2021]

COLUNAS_ARQ1_OBRIGATORIAS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MUNIC_CURSO", "CO_UF_CURSO", "CO_REGIAO_CURSO",
]
COLUNAS_ARQ1_OPCIONAIS = ["CO_MODALIDADE"]

# colunas finais antigas do consolidado, na ordem exata do arquivo
COLUNAS_FINAIS_ANTIGAS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MODALIDADE", "CO_MUNIC_CURSO", "CO_UF_CURSO",
    "CO_REGIAO_CURSO", "MEDIA_NT_FG",
]
COLUNAS_INTEIRAS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MODALIDADE", "CO_MUNIC_CURSO", "CO_UF_CURSO",
    "CO_REGIAO_CURSO",
]

# arq3: além de NT_FG, agora também NT_GER e NT_CE
COLUNAS_ARQ3 = ["CO_CURSO", "NT_FG", "NT_GER", "NT_CE"]
NOTAS_NOVAS = {"NT_GER": "MEDIA_NT_GER", "NT_CE": "MEDIA_NT_CE"}

REGIOES_PERMITIDAS = {1, 2}
CODIGOS_COMPUTACAO = {40, 4004}

ENCODINGS = ["utf-8", "latin1", "cp1252"]
SEPARADORES = [";", ",", "\t"]
SENTINELAS_NA = {"", ".", "NA", "N/A", "nan", "NaN", "NAN", "null", "Null",
                 "NULL", "None", "none"}

TOL = dict(rtol=1e-9, atol=1e-9)


# ---------------------------------------------------------------------------
# Localização e leitura (cópia fiel do script 02 — read-only nos brutos)
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


def detectar_encoding_separador(path: Path):
    melhor = (None, None, [], 0)
    for enc in ENCODINGS:
        for sep in SEPARADORES:
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc, nrows=5,
                                 dtype=str, engine="python", on_bad_lines="skip")
            except Exception:
                continue
            n = len(df.columns)
            if n > melhor[3] and n >= 2:
                melhor = (enc, sep, list(df.columns), n)
    return melhor[0], melhor[1], melhor[2]


def ler_arquivo(path: Path, colunas: list[str] | None = None):
    enc, sep, header = detectar_encoding_separador(path)
    if enc is None:
        return None, "", "", []
    use = None
    if colunas is not None:
        use = [c for c in colunas if c in header]
        if not use:
            return None, enc, sep, header
    df = pd.read_csv(path, sep=sep, encoding=enc, dtype=str,
                     usecols=use, engine="python", on_bad_lines="skip")
    return df, enc, sep, header


def converter_inteiro(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip().str.strip('"').str.strip("'")
    s = s.replace(list(SENTINELAS_NA), np.nan)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def converter_nota(serie: pd.Series) -> pd.Series:
    """Idêntica a converter_nt_fg do script 02 (vírgula->ponto, sentinelas->NaN)."""
    s = serie.astype(str).str.strip().str.strip('"').str.strip("'")
    s = s.replace(list(SENTINELAS_NA), np.nan)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


# ---------------------------------------------------------------------------
# Reconstrução de um ano (mesma lógica/ordem do script 02) + novas notas
# ---------------------------------------------------------------------------
def reconstruir_ano(ano: int, alertas: list[str]) -> pd.DataFrame:
    pasta = encontrar_pasta_ano(ano)
    if pasta is None:
        raise RuntimeError(f"[{ano}] pasta microdados_enade_{ano}* não encontrada")

    arq1 = encontrar_arquivo_arq(pasta, ano, 1)
    arq3 = encontrar_arquivo_arq(pasta, ano, 3)
    if arq1 is None or arq3 is None:
        raise RuntimeError(f"[{ano}] arq1/arq3 não encontrados (arq1={arq1}, arq3={arq3})")

    # ----- arq1: cadastro -----
    df1, _, _, _ = ler_arquivo(arq1, colunas=COLUNAS_ARQ1_OBRIGATORIAS + COLUNAS_ARQ1_OPCIONAIS)
    if df1 is None:
        raise RuntimeError(f"[{ano}] falha ao ler arq1")
    ausentes = [c for c in COLUNAS_ARQ1_OBRIGATORIAS if c not in df1.columns]
    if ausentes:
        raise RuntimeError(f"[{ano}] arq1 sem colunas obrigatórias: {ausentes}")
    if "CO_MODALIDADE" not in df1.columns:
        df1["CO_MODALIDADE"] = pd.NA
        alertas.append(f"[{ano}] CO_MODALIDADE ausente no arq1 — preenchida com NA (igual ao script 02)")

    for col in COLUNAS_ARQ1_OBRIGATORIAS + COLUNAS_ARQ1_OPCIONAIS:
        df1[col] = converter_inteiro(df1[col])

    df1f = df1[
        df1["CO_REGIAO_CURSO"].isin(REGIOES_PERMITIDAS)
        & df1["CO_GRUPO"].isin(CODIGOS_COMPUTACAO)
    ].copy()

    # ----- arq3: notas -----
    df3, _, _, header3 = ler_arquivo(arq3, colunas=COLUNAS_ARQ3)
    if df3 is None:
        raise RuntimeError(f"[{ano}] falha ao ler arq3")
    faltam = [c for c in ("CO_CURSO", "NT_FG", "NT_GER", "NT_CE") if c not in df3.columns]
    if faltam:
        raise RuntimeError(f"[{ano}] arq3 sem colunas {faltam} (header={header3})")

    df3["CO_CURSO"] = converter_inteiro(df3["CO_CURSO"])
    for nt in ("NT_FG", "NT_GER", "NT_CE"):
        df3[nt] = converter_nota(df3[nt])

    # MEDIA_NT_FG: EXATAMENTE como o script 02 (dropna CO_CURSO+NT_FG, mean por curso)
    base_fg = df3.dropna(subset=["CO_CURSO", "NT_FG"])
    medias_fg = (base_fg.groupby("CO_CURSO", as_index=False)["NT_FG"]
                 .mean().rename(columns={"NT_FG": "MEDIA_NT_FG"}))

    # MEDIA_NT_GER / MEDIA_NT_CE: análogo, cada nota com seu próprio dropna
    medias = medias_fg
    for nt, destino in NOTAS_NOVAS.items():
        base = df3.dropna(subset=["CO_CURSO", nt])
        m = (base.groupby("CO_CURSO", as_index=False)[nt]
             .mean().rename(columns={nt: destino}))
        medias = medias.merge(m, on="CO_CURSO", how="outer")

    # merge final por CO_CURSO (how=left, chave única em medias -> preserva ordem de df1f)
    final = df1f.merge(medias, on="CO_CURSO", how="left")
    final = final[COLUNAS_FINAIS_ANTIGAS + list(NOTAS_NOVAS.values())]
    return final


# ---------------------------------------------------------------------------
# Validação rigorosa recon vs consolidado original
# ---------------------------------------------------------------------------
def validar(cons_str: pd.DataFrame, recon: pd.DataFrame, alertas: list[str]) -> list[str]:
    erros: list[str] = []

    if len(cons_str) != len(recon):
        erros.append(f"Total de linhas difere: consolidado={len(cons_str)} recon={len(recon)}")
        return erros  # sem alinhamento, não adianta seguir

    # contagem por ano (comparada como dict de int -> int, robusto a dtypes de índice)
    a = {int(k): int(v) for k, v in cons_str["NU_ANO"].astype(int).value_counts().items()}
    b = {int(k): int(v) for k, v in recon["NU_ANO"].astype("Int64").value_counts().items()}
    if a != b:
        erros.append(f"Contagem por ano difere:\n  consolidado={dict(sorted(a.items()))}\n  recon={dict(sorted(b.items()))}")

    # colunas antigas presentes em recon
    faltam = [c for c in COLUNAS_FINAIS_ANTIGAS if c not in recon.columns]
    if faltam:
        erros.append(f"recon não possui colunas antigas: {faltam}")
        return erros

    # colunas inteiras: comparação exata (convertendo o consolidado-string igual ao 02)
    for col in COLUNAS_INTEIRAS:
        a_int = converter_inteiro(cons_str[col])
        b_int = recon[col].astype("Int64")
        # comparação elemento a elemento tratando <NA>
        mask_na = a_int.isna().to_numpy() & b_int.isna().to_numpy()
        iguais = (a_int.fillna(-(10**12)).to_numpy() == b_int.fillna(-(10**12)).to_numpy()) | mask_na
        ndif = int((~iguais).sum())
        if ndif:
            erros.append(f"Coluna inteira '{col}' difere em {ndif} linha(s)")

    # MEDIA_NT_FG: tolerância numérica + posições de NaN idênticas
    a_fg = pd.to_numeric(cons_str["MEDIA_NT_FG"].replace("", np.nan), errors="coerce").to_numpy(dtype=float)
    b_fg = recon["MEDIA_NT_FG"].to_numpy(dtype=float)
    na_a, na_b = np.isnan(a_fg), np.isnan(b_fg)
    if int((na_a != na_b).sum()):
        erros.append(f"MEDIA_NT_FG: posições nulas divergem em {int((na_a != na_b).sum())} linha(s)")
    prox = np.isclose(a_fg, b_fg, equal_nan=True, **TOL)
    ndif = int((~prox).sum())
    if ndif:
        erros.append(f"MEDIA_NT_FG: {ndif} valor(es) fora da tolerância {TOL}")

    return erros


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    dry = "--dry-run" in sys.argv

    print("=" * 88)
    print("ADICIONAR MEDIA_NT_GER e MEDIA_NT_CE ao consolidado")
    print("=" * 88)

    if not CAMINHO_CONSOLIDADO.exists():
        print(f"ERRO: consolidado não encontrado: {CAMINHO_CONSOLIDADO}")
        return 2

    alertas: list[str] = []

    # 1) ler consolidado como STRING (preserva tudo verbatim)
    cons_str = pd.read_csv(CAMINHO_CONSOLIDADO, sep=";", dtype=str,
                           keep_default_na=False, encoding="utf-8-sig")
    n_orig = len(cons_str)
    cont_orig = cons_str["NU_ANO"].astype(int).value_counts().sort_index()
    cols_orig = list(cons_str.columns)
    print(f"\nConsolidado: {n_orig} linhas, colunas={cols_orig}")

    # checagem: novas colunas ainda não existem
    ja_tem = [c for c in NOTAS_NOVAS.values() if c in cols_orig]
    if ja_tem:
        print(f"ERRO: o consolidado já contém {ja_tem}. Abortando para não sobrescrever.")
        return 2

    anos_consolidado = sorted(int(x) for x in cons_str["NU_ANO"].unique())
    print(f"Anos no consolidado: {anos_consolidado}")

    # 2) reconstruir por ano (na ordem ANOS, igual ao script 02)
    anos_proc = [a for a in ANOS if a in anos_consolidado]
    if set(anos_proc) != set(anos_consolidado):
        extras = set(anos_consolidado) - set(ANOS)
        if extras:
            print(f"ERRO: consolidado tem anos fora de ANOS={ANOS}: {sorted(extras)}")
            return 2

    print("\nReconstruindo dos brutos (mesma lógica/filtros do script 02)...")
    partes = []
    for ano in anos_proc:
        df = reconstruir_ano(ano, alertas)
        print(f"  [{ano}] reconstruído: {len(df)} linhas")
        partes.append(df)
    recon = pd.concat(partes, ignore_index=True)
    print(f"Recon total: {len(recon)} linhas")

    # 3) validar
    print("\nValidando reconstrução vs consolidado (linha a linha)...")
    erros = validar(cons_str, recon, alertas)
    if erros:
        print("\n*** VALIDAÇÃO FALHOU — NADA será gravado ***")
        for e in erros:
            print("  - " + e)
        if alertas:
            print("\nAlertas:")
            for a in alertas:
                print("  ! " + a)
        return 1
    print("  OK: total, por ano, colunas inteiras e MEDIA_NT_FG batem 100%.")

    # 4) montar saída: colunas antigas VERBATIM (string) + 2 novas (float, mesma ordem)
    saida = cons_str.copy()
    for destino in NOTAS_NOVAS.values():
        saida[destino] = recon[destino].to_numpy(dtype=float)

    # estatísticas das novas colunas
    stats = {}
    for destino in NOTAS_NOVAS.values():
        v = recon[destino].to_numpy(dtype=float)
        nn = int((~np.isnan(v)).sum())
        stats[destino] = (nn, n_orig, 100.0 * nn / n_orig)

    if dry:
        print("\n[--dry-run] Validação passou; gravação NÃO realizada.")
        _relatorio(None, None, n_orig, cont_orig, saida, stats, alertas, dry=True)
        return 0

    # 5) backup imediatamente antes de gravar
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DIR_SAIDA / f"microdados_enade_2005_2021_filtrado_consolidado.backup_{ts}.csv"
    shutil.copy2(CAMINHO_CONSOLIDADO, backup)

    # 6) gravar (mesmo formato do script 02)
    saida.to_csv(CAMINHO_CONSOLIDADO, sep=";", encoding="utf-8-sig",
                 index=False, quoting=csv.QUOTE_MINIMAL)

    # 7) verificação pós-escrita: reabre e confere colunas antigas idênticas + contagens
    pos = pd.read_csv(CAMINHO_CONSOLIDADO, sep=";", dtype=str,
                      keep_default_na=False, encoding="utf-8-sig")
    antigas_ok = cons_str.equals(pos[cols_orig])
    n_pos = len(pos)
    cont_pos = pos["NU_ANO"].astype(int).value_counts().sort_index()

    _relatorio(CAMINHO_CONSOLIDADO, backup, n_orig, cont_orig, pos, stats, alertas,
               dry=False, antigas_ok=antigas_ok, n_pos=n_pos, cont_pos=cont_pos)
    return 0 if antigas_ok and n_pos == n_orig else 1


def _relatorio(arquivo, backup, n_orig, cont_orig, saida, stats, alertas,
               dry=False, antigas_ok=None, n_pos=None, cont_pos=None) -> None:
    print("\n" + "=" * 88)
    print("RELATÓRIO FINAL")
    print("=" * 88)
    print(f"1. Arquivo alterado : {arquivo if arquivo else '(dry-run — não gravado)'}")
    print(f"2. Backup criado    : {backup if backup else '(dry-run — não criado)'}")
    print(f"3. Linhas antes     : {n_orig}")
    print(f"   Linhas depois    : {n_pos if n_pos is not None else '(dry-run)'}")
    print("4. Linhas por ano (antes / depois):")
    for ano, q in cont_orig.items():
        dep = cont_pos[ano] if cont_pos is not None else "-"
        print(f"     {ano}: {q} / {dep}")
    print(f"5. Colunas adicionadas: {', '.join(NOTAS_NOVAS.values())}")
    print("6. % não nulos nas novas colunas:")
    for destino, (nn, tot, pct) in stats.items():
        print(f"     {destino}: {nn}/{tot} preenchidos ({pct:.2f}% não nulos)")
    if antigas_ok is not None:
        print(f"7. Colunas antigas inalteradas (byte-a-byte): {'SIM' if antigas_ok else 'NÃO'}")
        print(f"8. Ordem das linhas preservada: {'SIM' if antigas_ok else 'NÃO'} "
              f"(verificado pela igualdade posicional das colunas antigas)")
    else:
        print("7. Colunas antigas inalteradas: (dry-run — não gravado)")
        print("8. Ordem das linhas preservada: (dry-run)")
    print("9. Comando: .venv\\Scripts\\python.exe tools\\adicionar_notas_ger_ce_consolidado.py")
    print("10. Alertas:", "nenhum" if not alertas else "")
    for a in alertas:
        print("     ! " + a)


if __name__ == "__main__":
    raise SystemExit(main())
