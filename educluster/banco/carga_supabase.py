import argparse
import json
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from educluster.educluster_config import (
    ATRIBUTOS_CURSO,
    CAMINHO_ZIP_MICRODADOS,
    COLS_ARQ3_CURSO,
    COLS_ARQ4_CURSO,
    ITENS_ARQ4,
    NOTAS_ARQ3,
    PASTA_DADOS_NO_ZIP,
    TABELA_CURSOS_SUPABASE,
    TABELAS_SUPABASE,
)

_local = threading.local()


def cliente():
    if not hasattr(_local, "cliente"):
        from supabase import create_client
        from util.util_db import credenciais_banco

        credenciais = credenciais_banco()
        _local.cliente = create_client(credenciais["url_banco"], credenciais["key_banco"])
    return _local.cliente


def ler_do_zip(caminho_zip, numero_arq, colunas):
    membro = f"{PASTA_DADOS_NO_ZIP}/microdados2021_arq{numero_arq}.txt"
    print(f"[carga] lendo {membro.split('/')[-1]} do zip")
    with zipfile.ZipFile(caminho_zip) as arquivo_zip:
        with arquivo_zip.open(membro) as conteudo:
            return pd.read_csv(conteudo, sep=";", encoding="latin-1", dtype=str, usecols=colunas)


def preparar_arq3(caminho_zip):
    df = ler_do_zip(caminho_zip, 3, COLS_ARQ3_CURSO)
    df["CO_CURSO"] = pd.to_numeric(df["CO_CURSO"]).astype("int64")
    for coluna in NOTAS_ARQ3:
        df[coluna] = pd.to_numeric(df[coluna].str.replace(",", ".", regex=False), errors="coerce")
    df.insert(0, "id", range(1, len(df) + 1))
    return df


def preparar_arq4(caminho_zip):
    df = ler_do_zip(caminho_zip, 4, COLS_ARQ4_CURSO)
    df["CO_CURSO"] = pd.to_numeric(df["CO_CURSO"]).astype("int64")
    for coluna in ITENS_ARQ4:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").astype("Int16")
    df.insert(0, "id", range(1, len(df) + 1))
    return df


def preparar_cursos(caminho_zip):
    df = ler_do_zip(caminho_zip, 1, ["CO_CURSO"] + ATRIBUTOS_CURSO)
    for coluna in ["CO_CURSO"] + ATRIBUTOS_CURSO:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").astype("Int64")
    inconsistentes = int((df.groupby("CO_CURSO")[ATRIBUTOS_CURSO].nunique() > 1).any(axis=1).sum())
    if inconsistentes:
        raise SystemExit(f"[carga] {inconsistentes} cursos com atributos inconsistentes no arq1")
    return df.groupby("CO_CURSO", as_index=False)[ATRIBUTOS_CURSO].first()


def contar(tabela):
    try:
        return cliente().table(tabela).select("*", count="exact").limit(1).execute().count
    except Exception:
        chave = "CO_CURSO" if tabela == TABELA_CURSOS_SUPABASE else "id"
        maior = cliente().table(tabela).select(chave).order(chave, desc=True).limit(1).execute().data
        return maior[0][chave] if maior and chave == "id" else len(maior)


def enviar_lote(tabela, lote, tentativas=5):
    registros = json.loads(lote.to_json(orient="records"))
    for tentativa in range(tentativas):
        try:
            cliente().table(tabela).upsert(registros).execute()
            return len(registros)
        except Exception:
            if tentativa == tentativas - 1:
                raise
            time.sleep(2 ** tentativa)


def carregar_tabela(tabela, df, tamanho_lote, paralelismo, substituir):
    existentes = contar(tabela)
    if existentes and not substituir:
        raise SystemExit(f"[carga] {tabela} ja tem {existentes} linhas. Use --substituir para recarregar.")
    if existentes:
        print(f"[carga] esvaziando {tabela} ({existentes} linhas)")
        cliente().rpc("truncar_tabela", {"nome_tabela": tabela}).execute()

    lotes = [df.iloc[i:i + tamanho_lote] for i in range(0, len(df), tamanho_lote)]
    print(f"[carga] enviando {len(df)} linhas para {tabela} em {len(lotes)} lotes")
    inicio = time.perf_counter()
    enviados, marco = 0, 0.1
    with ThreadPoolExecutor(paralelismo) as pool:
        futuros = [pool.submit(enviar_lote, tabela, lote) for lote in lotes]
        for futuro in as_completed(futuros):
            enviados += futuro.result()
            if enviados / len(df) >= marco:
                print(f"[carga]   {enviados / len(df):.0%}")
                marco += 0.1

    final = contar(tabela)
    situacao = "ok" if final == len(df) else "DIVERGENTE"
    print(f"[carga] {tabela}: {final} linhas no banco, {len(df)} esperadas, {situacao} ({time.perf_counter() - inicio:.0f}s)")
    if final != len(df):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Carga da base nacional do ENADE 2021 nas tabelas do EduCluster no Supabase")
    parser.add_argument("--zip", default=str(CAMINHO_ZIP_MICRODADOS))
    parser.add_argument("--tabelas", nargs="+", default=["cursos", "arq3", "arq4"], choices=["cursos", "arq3", "arq4"])
    parser.add_argument("--lote", type=int, default=1000)
    parser.add_argument("--paralelismo", type=int, default=6)
    parser.add_argument("--substituir", action="store_true")
    args = parser.parse_args()

    preparos = {
        "cursos": (TABELA_CURSOS_SUPABASE, preparar_cursos),
        "arq3": (TABELAS_SUPABASE[3], preparar_arq3),
        "arq4": (TABELAS_SUPABASE[4], preparar_arq4),
    }
    for nome in args.tabelas:
        tabela, preparar = preparos[nome]
        carregar_tabela(tabela, preparar(args.zip), args.lote, args.paralelismo, args.substituir)


if __name__ == "__main__":
    main()
