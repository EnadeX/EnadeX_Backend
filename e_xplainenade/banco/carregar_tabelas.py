"""
Cria e popula as tabelas próprias do E-XplainENADE no Supabase
(tbl_e_xplainenade_arqN_2021) a partir dos microdados brutos do INEP.

Por quê (2026-10-14 — ver DEVELOPMENT.md): as tabelas compartilhadas
tbl_arqN_2021 são truncadas e regravadas pelo refino do MultiENADE com o
recorte Norte+Nordeste, o que derrubou a base do E-XplainENADE de 707 para
169 cursos. Com tabelas próprias, o E-XplainENADE deixa de depender do ciclo
de vida dos dados de outro subprojeto (mesmo caminho do EduCluster, que já
usa tbl_educluster_*).

O que sobe — só o necessário:
  - linhas: estudantes dos cursos CC (4004) + SI (4006), Brasil inteiro, sem
    nenhum outro filtro (presença, nulos e agregação ficam no etl.py);
  - colunas: CO_CURSO + as colunas brutas que modules/etl.py lê de cada
    arquivo (mesma fonte de verdade: etl._colunas_por_arquivo()), mais um
    `id` sequencial (ordem da linha no arquivo bruto) usado para paginar de
    forma estável.

Uso (a partir da raiz do repositório EnadeX):
    python e_xplainenade/banco/carregar_tabelas.py sql       # gera criar_tabelas_e_xplainenade.sql
    python e_xplainenade/banco/carregar_tabelas.py subir     # sobe os dados (tabelas devem existir e estar vazias)
    python e_xplainenade/banco/carregar_tabelas.py conferir  # compara banco x arquivos brutos
    python e_xplainenade/banco/carregar_tabelas.py subir --substituir  # apaga o conteúdo antes de subir

O `CREATE TABLE` precisa ser rodado no SQL Editor do Supabase Studio: a
chave do .env é de API (PostgREST), que insere/apaga linhas mas não roda DDL.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

_PASTA = Path(__file__).resolve().parent
_RAIZ_PROJETO = _PASTA.parent  # e_xplainenade/
sys.path.insert(0, str(_RAIZ_PROJETO))

from modules.etl import ARQUIVOS_USADOS, _colunas_por_arquivo, table_name  # noqa: E402
from modules.supabase_client import _client  # noqa: E402

# local/ é a pasta não versionada (ver local/LEIA-ME.md); os microdados brutos (~500 MB) ficam lá.
DADOS_BRUTOS = _RAIZ_PROJETO / "local" / "dados" / "microdados_Enade_2021_LGPD" / "2.DADOS"
SQL_SAIDA = _PASTA / "criar_tabelas_e_xplainenade.sql"
GRUPOS = ["4004", "4006"]  # CC + SI — recorte fixo do E-XplainENADE
LOTE = 1000


def _ler_bruto(n: int, colunas: List[str]) -> pd.DataFrame:
    return pd.read_csv(
        DADOS_BRUTOS / f"microdados2021_arq{n}.txt",
        sep=";", dtype=str, usecols=colunas, keep_default_na=False, na_values=[""],
    )[colunas]


def montar_tabelas() -> Dict[int, pd.DataFrame]:
    """Lê os 13 arquivos brutos, restringe aos cursos CC+SI e numera as linhas."""
    colunas = _colunas_por_arquivo()
    a1 = _ler_bruto(1, colunas[1])
    cursos = set(a1.loc[a1["CO_GRUPO"].isin(GRUPOS), "CO_CURSO"])

    tabelas = {}
    for n in ARQUIVOS_USADOS:
        df = a1 if n == 1 else _ler_bruto(n, colunas[n])
        df = df[df["CO_CURSO"].isin(cursos)].reset_index(drop=True)
        df.insert(0, "id", range(1, len(df) + 1))
        tabelas[n] = df
    return tabelas


def gerar_sql() -> str:
    colunas = _colunas_por_arquivo()
    blocos = [
        "-- Tabelas próprias do E-XplainENADE (gerado por e_xplainenade/banco/carregar_tabelas.py).",
        "-- Rodar no SQL Editor do Supabase Studio. Colunas em text (mesma convenção das",
        "-- tbl_arqN_2021 — modules/supabase_client.py normaliza tudo para string na leitura).",
        "-- RLS ligado e sem política: a chave pública não lê nem escreve; o backend usa a",
        "-- chave secreta, que ignora RLS (mesma configuração das tbl_educluster_*).",
        "",
    ]
    for n in ARQUIVOS_USADOS:
        nome = _nome(n)
        defs = ['    "id" bigint primary key']
        for c in colunas[n]:
            defs.append(f'    "{c}" text' + (" not null" if c == "CO_CURSO" else ""))
        blocos.append(f"create table if not exists public.{nome} (\n" + ",\n".join(defs) + "\n);")
        blocos.append(f"alter table public.{nome} enable row level security;")
        blocos.append("")
    return "\n".join(blocos)


def _nome(n: int) -> str:
    return table_name(n)  # mesmo nome que o ETL lê


def _contar(client, tabela: str) -> int:
    return client.table(tabela).select("id", count="exact").limit(1).execute().count or 0


def subir(substituir: bool = False) -> None:
    client = _client()
    tabelas = montar_tabelas()

    # Confere tudo antes de escrever qualquer coisa: tabelas existem e estão vazias.
    for n in tabelas:
        existentes = _contar(client, _nome(n))
        if existentes and not substituir:
            raise SystemExit(
                f"{_nome(n)} já tem {existentes} linhas. Use --substituir para apagar e subir de novo."
            )

    for n, df in tabelas.items():
        tabela = _nome(n)
        if substituir:
            client.table(tabela).delete().gte("id", 0).execute()
        # to_json -> json.loads: único caminho confiável para NaN virar null
        # (ver DEVELOPMENT.md, 2026-08-30 13:42).
        registros = json.loads(df.to_json(orient="records"))
        for i in range(0, len(registros), LOTE):
            client.table(tabela).insert(registros[i:i + LOTE]).execute()
        total = _contar(client, tabela)
        status = "ok" if total == len(df) else "DIVERGENTE"
        print(f"{tabela:32} {total:6}/{len(df):6} linhas  {status}")


def conferir() -> bool:
    """Compara, coluna a coluna, o conteúdo do banco com o dos arquivos brutos."""
    from modules.supabase_client import fetch_table

    tudo_ok = True
    for n, esperado in montar_tabelas().items():
        cols = ",".join(esperado.columns)
        banco = fetch_table(_nome(n), columns=cols).sort_values("id", key=lambda s: s.astype(int))
        banco = banco.reset_index(drop=True)
        esperado = esperado.astype({"id": str}).reset_index(drop=True)
        igual = banco.shape == esperado.shape and banco.fillna("<nulo>").equals(esperado.fillna("<nulo>"))
        tudo_ok &= igual
        print(f"{_nome(n):32} banco={len(banco):6} bruto={len(esperado):6} cursos={esperado['CO_CURSO'].nunique():4}  "
              f"{'idêntico' if igual else 'DIFERENTE'}")
    return tudo_ok


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else ""
    if acao == "sql":
        SQL_SAIDA.write_text(gerar_sql(), encoding="utf-8")
        print(f"SQL gerado em {SQL_SAIDA}")
    elif acao == "subir":
        subir(substituir="--substituir" in sys.argv)
    elif acao == "conferir":
        sys.exit(0 if conferir() else 1)
    else:
        print(__doc__)
        sys.exit(2)
