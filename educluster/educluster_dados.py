import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from educluster.educluster_config import (
    ORIGEM_PADRAO,
    COLS_ARQ3_CURSO,
    COLS_ARQ4_CURSO,
    DIR_CACHE,
    DIR_MICRODADOS,
    NOTAS_ARQ3,
    ITENS_ARQ4,
    SUPABASE_PAGINA,
    SUPABASE_PARALELISMO,
    TABELAS_SUPABASE,
)

_local = threading.local()
_cache_tabelas = {}
_travas_tabelas = {}
_trava_registro = threading.Lock()

SEPARADOR = ";"
CODIFICACAO = "latin-1"


def _caminho_local(numero_arq: int):
    return DIR_MICRODADOS / f"microdados2021_arq{numero_arq}.txt"


def _caminho_cache(numero_arq: int):
    return DIR_CACHE / f"arq{numero_arq}.parquet"


def _converter_numericos(df: pd.DataFrame, colunas: list) -> pd.DataFrame:
    for coluna in colunas:
        if coluna in df.columns:
            serie = df[coluna]
            if serie.dtype == object or isinstance(serie.dtype, pd.StringDtype):
                serie = serie.str.replace(",", ".", regex=False)
            df[coluna] = pd.to_numeric(serie, errors="coerce")
    return df


def carregar_local(numero_arq: int, colunas: list = None, usar_cache: bool = True) -> pd.DataFrame:
    cache = _caminho_cache(numero_arq)
    if usar_cache and cache.exists():
        df = pd.read_parquet(cache)
        return df[colunas].copy() if colunas else df

    caminho = _caminho_local(numero_arq)
    if not caminho.exists():
        raise FileNotFoundError(f"Microdado nao encontrado: {caminho}")

    print(f"[educluster] lendo {caminho.name} do disco")
    df = pd.read_csv(caminho, sep=SEPARADOR, encoding=CODIFICACAO, dtype=str)
    df = _converter_numericos(df, ["CO_CURSO"] + NOTAS_ARQ3 + ITENS_ARQ4)

    if usar_cache:
        DIR_CACHE.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache)
        print(f"[educluster] cache gravado em {cache.name}")

    return df[colunas].copy() if colunas else df


def _cliente_supabase():
    if not hasattr(_local, "cliente"):
        from supabase import create_client
        from util.util_db import credenciais_banco

        credenciais = credenciais_banco()
        if not credenciais["key_banco"] or "None" in credenciais["url_banco"]:
            raise ConnectionError("SUPABASE_URL e SUPABASE_KEY ausentes no .env da raiz do repositorio EnadeX")
        _local.cliente = create_client(credenciais["url_banco"], credenciais["key_banco"])
    return _local.cliente


def _buscar_faixa(tabela: str, projecao: str, inicio: int, fim: int, tentativas: int = 5) -> list:
    for tentativa in range(tentativas):
        try:
            resposta = _cliente_supabase().table(tabela).select(projecao).gte("id", inicio).lte("id", fim).execute()
            return resposta.data or []
        except Exception:
            if tentativa == tentativas - 1:
                raise
            time.sleep(2 ** tentativa)


def carregar_supabase(numero_arq: int, colunas: list = None) -> pd.DataFrame:
    tabela = TABELAS_SUPABASE[numero_arq]
    projecao = ",".join(colunas) if colunas else "*"
    cliente = _cliente_supabase()

    try:
        menor = cliente.table(tabela).select("id").order("id").limit(1).execute().data
        maior = cliente.table(tabela).select("id").order("id", desc=True).limit(1).execute().data
    except Exception as erro:
        raise ConnectionError(f"Falha ao consultar {tabela} no Supabase: {erro}") from erro
    if not menor:
        raise ConnectionError(f"Tabela {tabela} vazia no Supabase. Rode educluster/banco/carga_supabase.py")

    inicio, fim = menor[0]["id"], maior[0]["id"]
    total = fim - inicio + 1
    faixas = [(i, min(i + SUPABASE_PAGINA - 1, fim)) for i in range(inicio, fim + 1, SUPABASE_PAGINA)]
    print(f"[educluster] consultando {tabela} no Supabase ({total} linhas, {len(faixas)} faixas)")

    with ThreadPoolExecutor(SUPABASE_PARALELISMO) as pool:
        partes = list(pool.map(lambda faixa: _buscar_faixa(tabela, projecao, *faixa), faixas))
    registros = [registro for parte in partes for registro in parte]
    if len(registros) != total:
        raise ConnectionError(f"{tabela}: {len(registros)} linhas recebidas de {total} esperadas")

    df = pd.DataFrame(registros)
    return _converter_numericos(df, ["CO_CURSO"] + NOTAS_ARQ3 + ITENS_ARQ4)


def _carregar_supabase_com_cache(numero_arq: int, colunas: list = None) -> pd.DataFrame:
    chave = (numero_arq, tuple(colunas) if colunas else None)
    with _trava_registro:
        trava = _travas_tabelas.setdefault(chave, threading.Lock())
    with trava:
        if chave not in _cache_tabelas:
            _cache_tabelas[chave] = carregar_supabase(numero_arq, colunas)
    return _cache_tabelas[chave]


def limpar_cache_supabase():
    _cache_tabelas.clear()


def carregar_arquivo(numero_arq: int, colunas: list = None, origem: str = ORIGEM_PADRAO) -> pd.DataFrame:
    if origem == "local":
        return carregar_local(numero_arq, colunas)
    if origem == "supabase":
        return _carregar_supabase_com_cache(numero_arq, colunas)
    raise ValueError(f"origem invalida: {origem}. Use 'local' ou 'supabase'.")


def carregar_arq3(origem: str = ORIGEM_PADRAO) -> pd.DataFrame:
    return carregar_arquivo(3, COLS_ARQ3_CURSO, origem)


def carregar_arq4(origem: str = ORIGEM_PADRAO) -> pd.DataFrame:
    return carregar_arquivo(4, COLS_ARQ4_CURSO, origem)
