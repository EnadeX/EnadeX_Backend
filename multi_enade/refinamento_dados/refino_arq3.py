import os
import uuid

import pandas as pd

from multi_enade.refinamento_dados.util_etl import leitura_inicial_dados, obter_cursos_recorte, show_df
from util.util_db import credenciais_banco, truncar_tabela_supabase, upsert_supabase

_DIC_TIPAGEM = {
    # Novas colunas adicionadas da imagem
    "NU_ITEM_OFG": "int",
    "NU_ITEM_OFG_Z": "int",
    "NU_ITEM_OFG_X": "int",
    "NU_ITEM_OFG_N": "int",
    "NU_ITEM_OCE": "int",
    "NU_ITEM_OCE_Z": "int",
    "NU_ITEM_OCE_X": "int",
    "NU_ITEM_OCE_N": "int",

    # Colunas de notas anteriores
    "NT_GER": "float",
    "NT_FG": "float",
    "NT_OBJ_FG": "float",
    "NT_DIS_FG": "float",
    "NT_FG_D1": "float",
    "NT_FG_D1_PT": "float",
    "NT_FG_D1_CT": "float",
    "NT_FG_D2": "float",
    "NT_FG_D2_PT": "float",
    "NT_FG_D2_CT": "float",
    "NT_CE": "float",
    "NT_OBJ_CE": "float",
    "NT_DIS_CE": "float",
    "NT_CE_D1": "float",
    "NT_CE_D2": "float",
    "NT_CE_D3": "float",
}


def main_refino_arq3(
    caminho_arq_3: str,
    cursos_recorte: pd.Series,
    url_conexao: str,
    key_conexao: str,
    print_flag: bool = False,
) -> pd.DataFrame:
    """
    Lê o arq3 (notas) bruto, filtra pelo recorte de cursos (já calculado a
    partir do arq1 — ver util_etl.obter_cursos_recorte) e persiste em
    tbl_arq3_2021 no Supabase.
    """
    dataf_inicial_arq3 = leitura_inicial_dados(caminho_arq_3, dic_de_tipagem=_DIC_TIPAGEM)
    dataf_filtrado_arq3 = dataf_inicial_arq3.dropna(how="all")

    dataf_filtrado_arq3 = dataf_filtrado_arq3[
        dataf_filtrado_arq3["CO_CURSO"].isin(cursos_recorte)
    ].copy()
    ids_unicos = [str(uuid.uuid4()) for _ in range(len(dataf_filtrado_arq3))]
    dataf_filtrado_arq3.insert(0, "id", ids_unicos)

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    dataf_filtrado_arq3.to_csv(os.path.join(diretorio_atual, "arq3_refinado.csv"), index=False)

    truncar_tabela_supabase("tbl_arq3_2021", url_conexao, key_conexao)
    upsert_supabase(dataf_filtrado_arq3, "tbl_arq3_2021", url_conexao, key_conexao)

    show_df(dataf_filtrado_arq3) if print_flag else None
    return dataf_filtrado_arq3


if __name__ == "__main__":
    base_dados = os.environ.get(
        "ENADE_DADOS_BRUTOS",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados_brutos"),
    )
    caminho_arq_3 = os.path.join(base_dados, "microdados2021_arq3.txt")
    caminho_arq_1 = os.path.join(base_dados, "microdados2021_arq1.txt")

    cursos_recorte = obter_cursos_recorte(caminho_arq_1)
    dic_credenciais = credenciais_banco()
    main_refino_arq3(caminho_arq_3, cursos_recorte, dic_credenciais["url_banco"], dic_credenciais["key_banco"])
