from functools import wraps
from pathlib import Path
import pandas as pd
import time


def leitura_inicial_dados(caminho_str: str, colunas_manter=False, dic_de_tipagem=False, print_flag=False):
    try:
        caminho_arq: str = Path(caminho_str)
        data_frame = pd.read_csv(caminho_arq, sep=";", dtype=str, encoding="latin1")
        data_frame = data_frame[colunas_manter] if colunas_manter is not False else data_frame
        data_frame = data_frame.astype(dic_de_tipagem) if dic_de_tipagem is not False else data_frame
        print(data_frame) if print_flag else None
        return data_frame
    except Exception as erro:
        raise erro


def calcula_tempo(func):
    @wraps(func)
    def warpper(*args, **kwargs):
        inicio = time.perf_counter()
        resultado = func(*args, **kwargs)
        fim = time.perf_counter()
        tempo_final = round(fim - inicio, 2)
        if tempo_final <= 60:
            print(f"Tempo de execucao: {tempo_final}s")
        else:
            tempo_final = round(tempo_final / 60, 2)
            print(f"Tempo de execucao: {tempo_final}m")
        return resultado
    return warpper


def show_df(dataf: pd.DataFrame):
    print(dataf.head())
    print("-" * 20)
    dataf.info()
    print("-" * 20)
    print(dataf.describe())


def juncao(dataf_1: pd.DataFrame, dataf_2: pd.DataFrame, coluna_juncao: str, print_flag=False) -> pd.DataFrame:
    try:
        dataf_merged = dataf_1.merge(dataf_2, on=coluna_juncao, how="inner")
        print(dataf_merged) if print_flag else None
        return dataf_merged
    except Exception as erro:
        raise erro


def obter_cursos_recorte(caminho_arq_1: str, grupos=("4004", "4006"), regioes=("1", "2")) -> pd.Series:
    """
    Lê o arq1 (curso/IES) uma única vez e devolve os CO_CURSO que entram no
    recorte do projeto: grupo (CO_GRUPO) em `grupos` e região (CO_REGIAO_CURSO)
    em `regioes` (1=Norte, 2=Nordeste). Compartilhada pelos refino_arqN para
    não reler e refiltrar o mesmo arq1.txt a cada arquivo processado.
    """
    dataf_arq1 = leitura_inicial_dados(caminho_arq_1, ["CO_CURSO", "CO_REGIAO_CURSO", "CO_GRUPO"])
    dataf_arq1 = dataf_arq1.dropna(how="all")
    dataf_arq1 = dataf_arq1[dataf_arq1["CO_REGIAO_CURSO"].isin(regioes)]
    dataf_arq1 = dataf_arq1[dataf_arq1["CO_GRUPO"].isin(grupos)]
    return dataf_arq1["CO_CURSO"]
