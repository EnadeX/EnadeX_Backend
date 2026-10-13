"""
Camada de dados do ENADE-Time sobre o `util/util_db.py` do grupo (PostgREST do Supabase).

O `util_db` serve a todos os subprojetos; este módulo acrescenta o que o ENADE-Time precisa
para ler e gravar com segurança pelo canal HTTP, sem alterar o `util`:

  * credenciais validadas com mensagem clara (o util monta `https://None.supabase.co` quando
    SUPABASE_URL falta) e recusa de chave de serviço — o ENADE-Time lê com a chave pública
    e publica por conexão direta (scripts/12), nunca com a chave que ignora RLS;
  * `ler_tabela`: `consultar_dados` com as credenciais já resolvidas;
  * `upsert_lotes`: lotes (2.000 linhas por padrão, como o limite de payload do PostgREST),
    nova tentativa com espera crescente e colunas inteiras normalizadas para Int64 — uma
    coluna inteira com NaN vira float no pandas e sai como `2806701.0`, que o PostgREST
    recusa para `integer`;
  * `contar`: contagem exata no servidor, para conferir o que de fato chegou.

Variáveis (as mesmas do util): SUPABASE_URL (a referência do projeto, não a URL completa) e
SUPABASE_KEY (a chave publishable/anon). Vêm do ambiente ou de um .env.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

_RAIZ_ECO = Path(__file__).resolve().parents[1]  # raiz do EnadeX: onde está o pacote `util`
if str(_RAIZ_ECO) not in sys.path:
    sys.path.insert(0, str(_RAIZ_ECO))

TAMANHO_LOTE = 2_000
TENTATIVAS = 3

# Colunas inteiras da tabela fato (as demais numéricas são notas, NUMERIC(7,4)).
COLUNAS_INTEIRAS_FATO = [
    "id", "nu_ano", "co_curso", "co_ies", "co_categad", "co_orgacad", "co_grupo",
    "co_modalidade", "co_munic_curso", "co_uf_curso", "co_regiao_curso",
]
# NUMERIC(7,4) na fato. A etapa 06 formata com "%.4f" (Python: empate exato em binário vai para o par,
# 43.53125 -> 43.5312) e o PostgreSQL arredonda 43.53125 para 43.5313. Se o float for para o PostgREST
# como número, 12 médias da base (de 582 curso-ano) sairiam 0,0001 acima do que o COPY grava.
# Estas colunas vão, portanto, como o MESMO texto do COPY (normalizar_decimais).
COLUNAS_DECIMAIS_FATO = ["media_nt_fg", "media_nt_ger", "media_nt_ce"]


class CredenciaisInvalidas(RuntimeError):
    """SUPABASE_URL/SUPABASE_KEY ausentes ou inadequadas para o ENADE-Time."""


def papel_da_chave(chave: str) -> str:
    """'service_role', 'anon' ou 'desconhecido', sem validar a assinatura (só ler o papel)."""
    if chave.startswith("sb_secret_"):
        return "service_role"
    if chave.startswith("sb_publishable_"):
        return "anon"
    partes = chave.split(".")
    if len(partes) == 3:  # JWT legado (anon / service_role)
        try:
            corpo = partes[1] + "=" * (-len(partes[1]) % 4)
            return json.loads(base64.urlsafe_b64decode(corpo)).get("role", "desconhecido")
        except (ValueError, json.JSONDecodeError):
            return "desconhecido"
    return "desconhecido"


def credenciais(permitir_chave_de_servico: bool = False) -> tuple[str, str]:
    """(url, chave) prontas para o util_db, ou `CredenciaisInvalidas` com o que falta."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    referencia = (os.getenv("SUPABASE_URL") or "").strip()
    chave = (os.getenv("SUPABASE_KEY") or "").strip()
    if not referencia:
        raise CredenciaisInvalidas(
            "SUPABASE_URL não definida. O util_db espera a REFERÊNCIA do projeto "
            "(ex.: yghryywuxfwzvfjknpgk), não a URL completa."
        )
    if "://" in referencia or "." in referencia:
        raise CredenciaisInvalidas(
            f"SUPABASE_URL deve ser só a referência do projeto, sem https:// nem .supabase.co (recebido: {referencia!r})."
        )
    if not chave:
        raise CredenciaisInvalidas("SUPABASE_KEY não definida (use a chave publishable/anon).")
    if not permitir_chave_de_servico and papel_da_chave(chave) == "service_role":
        raise CredenciaisInvalidas(
            "SUPABASE_KEY é uma chave de serviço (ignora a RLS). O ENADE-Time lê com a chave pública; "
            "a publicação é por conexão direta (scripts/12_publicar_supabase.py)."
        )
    return f"https://{referencia}.supabase.co", chave


def ler_tabela(
    tabela: str,
    colunas: str = "*",
    filtros: dict | None = None,
    limite: int | None = None,
    tipagem: dict | None = None,
) -> pd.DataFrame:
    """Lê uma tabela/view do Supabase (paginação automática do util_db)."""
    from util.util_db import consultar_dados

    url, chave = credenciais()
    return consultar_dados(tabela, url, chave, colunas, filtros, limite, tipagem)


def contar(tabela: str) -> int:
    """Quantas linhas o servidor diz que a tabela tem (count exato, sem trazer os dados)."""
    from supabase import create_client

    url, chave = credenciais()
    resposta = create_client(url, chave).table(tabela).select("*", count="exact").limit(0).execute()
    return int(resposta.count)


def normalizar_inteiros(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Converte as colunas inteiras para Int64 anulável (NaN -> <NA> -> null no JSON, sem '.0')."""
    saida = df.copy()
    for coluna in colunas:
        if coluna in saida.columns:
            saida[coluna] = pd.to_numeric(saida[coluna], errors="raise").astype("Int64")
    return saida


def normalizar_decimais(df: pd.DataFrame, colunas: list[str], casas: int = 4) -> pd.DataFrame:
    """Envia colunas decimais como texto já arredondado (`%.{casas}f`, o mesmo do COPY da etapa 06),
    nulo onde faltar valor. O PostgREST converte o texto para NUMERIC sem arredondar de novo, e a
    tabela fica igual à carregada por COPY."""
    saida = df.copy()
    for coluna in colunas:
        if coluna in saida.columns:
            saida[coluna] = pd.Series(
                [None if pd.isna(v) else f"{float(v):.{casas}f}" for v in saida[coluna]],
                index=saida.index,
                dtype=object,
            )
    return saida


def upsert_lotes(
    df: pd.DataFrame,
    tabela: str,
    colunas_inteiras: list[str] | None = None,
    colunas_decimais: list[str] | None = None,
    tamanho_lote: int = TAMANHO_LOTE,
    tentativas: int = TENTATIVAS,
    espera: float = 1.0,
    esperado_total: int | None = None,
) -> int:
    """UPSERT em lotes pelo util_db. Devolve quantas linhas foram enviadas.

    Cada lote é repetido até `tentativas` vezes, com espera crescente, em erro de rede ou do
    PostgREST; se esgotar, a exceção sobe com o lote em que falhou (os anteriores já foram
    gravados: o upsert é idempotente, então reexecutar é seguro). Com `esperado_total`, a
    contagem do servidor é conferida ao final.
    """
    from util.util_db import upsert_supabase

    url, chave = credenciais()
    dados = normalizar_decimais(normalizar_inteiros(df, colunas_inteiras or []), colunas_decimais or [])
    enviadas = 0
    for inicio in range(0, len(dados), tamanho_lote):
        lote = dados.iloc[inicio:inicio + tamanho_lote]
        for tentativa in range(1, tentativas + 1):
            try:
                upsert_supabase(lote, tabela, url, chave)
                break
            except Exception as erro:  # noqa: BLE001 — rede, PostgREST, supabase-py
                if tentativa == tentativas:
                    raise RuntimeError(
                        f"upsert em {tabela} falhou no lote {inicio // tamanho_lote + 1} "
                        f"(linhas {inicio}-{inicio + len(lote) - 1}) após {tentativas} tentativas: {erro}"
                    ) from erro
                time.sleep(espera * tentativa)
        enviadas += len(lote)
    if esperado_total is not None:
        no_servidor = contar(tabela)
        if no_servidor != esperado_total:
            raise RuntimeError(f"{tabela}: o servidor tem {no_servidor} linhas, esperado {esperado_total}")
    return enviadas
