import os
import uuid

import pandas as pd

from multi_enade.refinamento_dados.util_etl import leitura_inicial_dados, obter_cursos_recorte, show_df
from util.util_db import credenciais_banco, truncar_tabela_supabase, upsert_supabase


def main_refino_arq29(
    caminho_arq_29: str,
    cursos_recorte: pd.Series,
    url_conexao: str,
    key_conexao: str,
    print_flag: bool = False,
) -> pd.DataFrame:
    """
    Lê o arq29 (horas de dedicação aos estudos) bruto, filtra pelo recorte de
    cursos e persiste em tbl_arq29_2021 no Supabase.
    """
    dataf_inicial_arq29 = leitura_inicial_dados(caminho_arq_29, dic_de_tipagem={"NU_ANO": "int"})
    dataf_filtrado_arq29 = dataf_inicial_arq29.dropna(how="all")

    dataf_filtrado_arq29 = dataf_filtrado_arq29[
        dataf_filtrado_arq29["CO_CURSO"].isin(cursos_recorte)
    ].copy()
    ids_unicos = [str(uuid.uuid4()) for _ in range(len(dataf_filtrado_arq29))]
    dataf_filtrado_arq29.insert(0, "id", ids_unicos)

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    dataf_filtrado_arq29.to_csv(os.path.join(diretorio_atual, "arq29_refinado.csv"), index=False)

    truncar_tabela_supabase("tbl_arq29_2021", url_conexao, key_conexao)
    upsert_supabase(dataf_filtrado_arq29, "tbl_arq29_2021", url_conexao, key_conexao)

    show_df(dataf_filtrado_arq29) if print_flag else None
    return dataf_filtrado_arq29


if __name__ == "__main__":
    base_dados = os.environ.get(
        "ENADE_DADOS_BRUTOS",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados_brutos"),
    )
    caminho_arq_29 = os.path.join(base_dados, "microdados2021_arq29.txt")
    caminho_arq_1 = os.path.join(base_dados, "microdados2021_arq1.txt")

    cursos_recorte = obter_cursos_recorte(caminho_arq_1)
    dic_credenciais = credenciais_banco()
    main_refino_arq29(caminho_arq_29, cursos_recorte, dic_credenciais["url_banco"], dic_credenciais["key_banco"])
