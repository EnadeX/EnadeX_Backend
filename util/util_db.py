from supabase import create_client, Client
from pandas import DataFrame
import pandas as pd
import warnings
import dotenv
import json
import os

# Silenciando avisos desnecessários para manter seu console limpo
warnings.filterwarnings("ignore", category=DeprecationWarning, module="supabase")


def credenciais_banco() -> dict[str, str]:
    dotenv.load_dotenv()
    prog_id = os.getenv("SUPABASE_URL")
    url_banco = f"https://{prog_id}.supabase.co"
    key_banco = os.getenv("SUPABASE_KEY")
    return {"url_banco": url_banco, "key_banco": key_banco}


def consultar_dados(
        table_name: str,
        supabase_url: str,
        supabase_key: str,
        colunas: str = "*",
        filtros: dict = None,
        limite: int = None,
        dic_tipagem: dict = None
) -> DataFrame:
    """
    Realiza consultas no Supabase com paginação automática para burlar
    o limite de 1000 registros, retornando os dados em um DataFrame.
    """
    supabase: Client = create_client(supabase_url, supabase_key)

    try:
        todos_registros = []
        tamanho_pagina = 1000
        offset = 0

        while True:
            query = supabase.table(table_name).select(colunas)

            if filtros:
                for coluna, valor in filtros.items():
                    query = query.eq(coluna, valor)

            fim = offset + tamanho_pagina - 1

            if limite:
                if offset >= limite:
                    break
                if fim >= limite:
                    fim = limite - 1

            resposta = query.range(offset, fim).execute()
            registros_pagina = resposta.data if hasattr(resposta, 'data') else resposta.get('data', [])
            todos_registros.extend(registros_pagina)

            if len(registros_pagina) < tamanho_pagina or (limite and len(todos_registros) >= limite):
                break

            offset += tamanho_pagina

        df_resultado = pd.DataFrame(todos_registros)

        if not df_resultado.empty and dic_tipagem:
            tipagem_valida = {col: tipo for col, tipo in dic_tipagem.items() if col in df_resultado.columns}
            df_resultado = df_resultado.astype(tipagem_valida)

        return df_resultado

    except Exception as e:
        print(f"Falha ao realizar a consulta e converter para DataFrame na tabela '{table_name}': {e}")
        raise e


def upsert_supabase(dataf: pd.DataFrame, nome_tabela: str, url_conexao: str, key_conexao: str) -> bool:
    """
    Executa um UPSERT no Supabase de forma nativa.
    Atualiza os registros existentes (baseado na Chave Primária da tabela) e insere as linhas novas.
    """
    print("Iniciando carga para o banco de dados...")
    if dataf.empty:
        print("O DataFrame está vazio.")
        return True

    # 1. Inicializa o cliente do Supabase
    supabase: Client = create_client(url_conexao, key_conexao)

    # 2. Prepara o Pandas para a API do Supabase. IMPORTANTE: dataf.where(...,
    # None) NÃO funciona em colunas float64 — o pandas converte o None de
    # volta para NaN por causa do dtype da coluna, e NaN não é JSON válido
    # (gera "Out of range float values are not JSON compliant: nan"). to_json
    # já serializa NaN/NaT como null corretamente, então fazemos o round-trip
    # por JSON em vez de to_dict() direto.
    dados_lote = json.loads(dataf.to_json(orient='records', date_format='iso'))

    # 3. O Upsert nativo: Ele descobre a chave primária sozinho e resolve os conflitos
    resposta = supabase.table(nome_tabela).upsert(dados_lote).execute()

    print(f"Sucesso! {len(resposta.data)} linha(s) processada(s) na tabela '{nome_tabela}'.")
    return True


def truncar_tabela_supabase(nome_tabela: str, url_conexao: str, key_conexao: str) -> bool:
    """
    Aciona uma função RPC no Supabase para esvaziar completamente uma tabela,
    zerando os contadores seriais para uma inserção limpa.
    """
    try:
        # 1. Inicializa o cliente do Supabase
        supabase: Client = create_client(url_conexao, key_conexao)

        # 2. Chama a função armazenada no banco passando o nome da tabela
        supabase.rpc("truncar_tabela", {"nome_tabela": nome_tabela}).execute()

        print(f"Sucesso absoluto! A tabela '{nome_tabela}' foi esvaziada perfeitamente.")
        return True

    except Exception as e:
        print(f"Ocorreu um erro na função (truncar_tabela_supabase): {e}")
        return False


if __name__ == "__main__":
    dic_credenciais = credenciais_banco()
    #truncar_tabela_supabase("tbl_multi_enade_associacao", dic_credenciais["url_banco"], dic_credenciais["key_banco"])
    pass