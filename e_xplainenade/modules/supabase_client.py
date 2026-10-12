"""
Cliente Supabase do E-XplainENADE — autocontido (não importa util/util_db.py do
repositório compartilhado, por decisão de independência registrada no
DEVELOPMENT.md, 2026-08-26 22:01: o E-XplainENADE não deve depender de código de
outro integrante, só do banco de dados como ponto de integração).

Lê as credenciais do `.env` na raiz do repositório EnadeX (fora desta pasta,
padrão combinado pelo grupo — ver docs/EnadeX - Diagrama de pastas.pdf), com
SUPABASE_URL e SUPABASE_KEY.
"""
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
import os

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"  # modules/ -> e_xplainenade/ -> EnadeX/

_env_loaded = False


def _ensure_env_loaded() -> None:
    global _env_loaded
    if _env_loaded:
        return
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH)
    else:
        load_dotenv()  # fallback: busca .env a partir do cwd, para outras estruturas de pasta
    _env_loaded = True


def _client():
    """
    Monta o cliente Supabase a partir de SUPABASE_URL/SUPABASE_KEY.

    Mesma convenção já usada pelo grupo (ver util/util_db.py::credenciais_banco):
    se SUPABASE_URL não começar com 'http', é tratado como o project-ref e a URL
    completa é montada como https://{ref}.supabase.co.
    """
    from supabase import create_client

    _ensure_env_loaded()
    raw_url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not raw_url or not key:
        raise RuntimeError(
            "SUPABASE_URL/SUPABASE_KEY não encontrados. Verifique o arquivo .env "
            f"na raiz do repositório EnadeX (esperado em: {_ENV_PATH})."
        )
    url = raw_url if raw_url.startswith("http") else f"https://{raw_url}.supabase.co"
    return create_client(url, key)


def fetch_table(
    table: str,
    columns: str = "*",
    filters: Optional[Dict] = None,
    page_size: int = 1000,
) -> pd.DataFrame:
    """
    Consulta uma tabela do Supabase com paginação automática (o limite do
    Postgrest é 1000 linhas por página) e devolve um DataFrame.

    Normaliza todo valor não-nulo para string, coluna a coluna: o restante do
    pipeline (modules.loader.preprocess) foi escrito para ler os .txt brutos do
    INEP com dtype=str (ex: letras 'A'..'H' do questionário, mapeadas para
    inteiro via _LETTER_TO_INT). As 13 tabelas foram populadas com as colunas
    tipadas como `text` (decisão registrada no DEVELOPMENT.md, 2026-08-30, ver
    Supabase/criar_tabelas_faltantes.sql) — a normalização aqui garante que o
    pipeline se comporte da mesma forma mesmo que isso mude no futuro.

    Chamada por até 13 threads em paralelo (ver modules/etl.py::load_raw()) —
    cada chamada cria seu próprio client via _client(), sem estado
    compartilhado entre threads.
    """
    client = _client()
    registros: List[dict] = []
    offset = 0

    while True:
        query = client.table(table).select(columns)
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        try:
            resposta = query.range(offset, offset + page_size - 1).execute()
        except Exception as e:
            # Traduz qualquer erro do cliente Supabase/Postgrest (tabela
            # inexistente, credenciais inválidas, falha de rede) para
            # RuntimeError — o mesmo tipo de erro que o restante do pipeline
            # (etl.py/loader.py) já usa para sinalizar "dado ainda não
            # disponível", tratado de forma amigável por app.py e pela API.
            raise RuntimeError(
                f"Falha ao consultar a tabela '{table}' no Supabase: {e}"
            ) from e
        pagina = resposta.data or []
        registros.extend(pagina)
        if len(pagina) < page_size:
            break
        offset += page_size

    df = pd.DataFrame(registros)
    for col in df.columns:
        df[col] = df[col].map(lambda v: v if v is None else str(v))
    return df
