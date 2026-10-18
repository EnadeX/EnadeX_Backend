"""
Camada 1 — Ingestão, filtro e agregação por curso.

HISTÓRICO (ver DEVELOPMENT.md para os detalhes completos): a versão anterior
deste módulo unia os 43 arquivos do INEP por POSIÇÃO de linha, assumindo que
a linha N de um arquivo correspondia ao mesmo estudante da linha N de outro
arquivo. Essa suposição foi refutada em 2026-08-20: o Manual do Usuário do
INEP declara explicitamente que cada arquivo é ordenado por uma variável
distinta, exatamente para impedir a reidentificação do estudante (LGPD) — e
o teste empírico confirmou que a correspondência de `CO_CURSO` entre
arquivos, na mesma posição de linha, é puramente aleatória (<1%).

A única chave de junção que o INEP sanciona entre arquivos é `CO_CURSO`
(nível de curso). Este módulo agrega cada um dos 13 arquivos usados pelo
E-XplainENADE por `CO_CURSO` — reaproveitando `modules.loader.preprocess()`
para a recodificação de cada arquivo antes de agregar — e une os agregados
por essa chave (inner join). Cada linha do DataFrame retornado passa a
representar um CURSO, não mais um estudante.

Recorte: CO_GRUPO (CC + SI) — Brasil inteiro, sem filtro de região (decisão
registrada em DEVELOPMENT.md, 2026-08-27; o mockup original do sistema
também nunca previu um filtro de região para o E-XplainENADE).

SWAP POINT: quando o ENADE-Time (Lucas) entregar uma base normalizada
equivalente, é este o módulo a substituir — load_raw() mantém a mesma
assinatura e o mesmo schema de saída (nível curso).

FONTE DE DADOS (2026-08-30): load_raw() lê os 13 arquivos exclusivamente do
Supabase via modules.supabase_client — tabelas tbl_e_xplainenade_arqN_2021 para
N = 1, 2, 3, 5, 6, 10, 11, 14, 16, 21, 23, 27, 29 (ver ARQUIVOS_USADOS).

TABELAS PRÓPRIAS (2026-10-14 — ver DEVELOPMENT.md): até esta data o ETL lia as
tabelas compartilhadas tbl_arqN_2021, que o refino do MultiENADE passou a
truncar e regravar só com Norte+Nordeste (8 das 13 tabelas), derrubando a base
de 707 para 169 cursos. Agora o E-XplainENADE lê tabelas próprias, populadas
direto dos microdados brutos por banco/carregar_tabelas.py (CC+SI, Brasil
inteiro, só as colunas usadas aqui). Não
há mais caminho local/offline — decisão do usuário de depender só do banco
compartilhado do ecossistema EnadeX (ver DEVELOPMENT.md).

PERFORMANCE (2026-08-30, reaplicada em 2026-09-21 — ver DEVELOPMENT.md): as 13
buscas são feitas em PARALELO (ThreadPoolExecutor) — cada uma pagina ~26 vezes
contra o Supabase (~8-15s), e em série isso levava mais de 2 minutos por
chamada fria (medido: 123s). Em paralelo, o tempo total fica limitado pela
busca mais lenta, não pela soma de todas. Cada busca também pede só as
colunas realmente usadas (não mais "*"), reduzindo o payload.

CO_CATEGAD = 7 (2026-10-14 — ver DEVELOPMENT.md): o dicionário oficial do INEP
define 7 como "Especial", sem classificação como pública ou privada, então
TP_CATEGAD_BIN fica indefinido para esses cursos. Eles são excluídos aqui,
explicitamente e contados no funil (df.attrs["funil"]), em vez de serem
descartados em silêncio pelo statsmodels só quando TP_CATEGAD_BIN entra no
modelo — assim o nº de cursos da base fecha com o n_obs de qualquer modelo.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import pandas as pd

from modules.loader import preprocess


def table_name(n: int) -> str:
    """Nome da tabela no Supabase para o arquivo bruto nº n (ex: 3 -> 'tbl_e_xplainenade_arq3_2021')."""
    return f"tbl_e_xplainenade_arq{n}_2021"


# Os 13 arquivos do escopo do E-XplainENADE (ver DEVELOPMENT.md, 2026-08-26/27).
# Cada tupla: (nº do arquivo, colunas brutas a manter, colunas finais após
# preprocess() a usar na agregação). Notas (arq3) e curso/IES (arq1) têm
# tratamento próprio por serem estruturalmente diferentes (múltiplas saídas,
# filtro de presença, peso).
_ARQUIVOS_SIMPLES = [
    (2,  ["CO_TURNO_GRADUACAO"], ["CO_TURNO_V", "CO_TURNO_N", "CO_TURNO_I"]),
    (5,  ["TP_SEXO"],            ["TP_SEXO"]),
    (6,  ["NU_IDADE"],           ["NU_IDADE"]),
    (10, ["QE_I04"],             ["QE_ESC_PAI"]),
    (11, ["QE_I05"],             ["QE_ESC_MAE"]),
    (14, ["QE_I08"],             ["QE_RENDA"]),
    (16, ["QE_I10"],             ["QE_TRABALHO"]),
    (21, ["QE_I15"],             ["QE_ACAO_AFIRM_BIN"]),
    (23, ["QE_I17"],             ["QE_TIPO_EM_BIN"]),
    (27, ["QE_I21"],             ["QE_FAM_SUPERIOR"]),
    (29, ["QE_I23"],             ["QE_HORAS_ESTUDO"]),
]

# Lista explícita das 13 tabelas lidas (usada em mensagens e no config do relatório).
ARQUIVOS_USADOS = [1, 2, 3, 5, 6, 10, 11, 14, 16, 21, 23, 27, 29]

# CO_CATEGAD sem classificação pública/privada no dicionário do INEP (7 = Especial).
CATEGAD_SEM_CLASSIFICACAO = [7]

# Colunas brutas realmente necessárias por arquivo (evita pedir "*" do Supabase).
_COLUNAS_ARQ1 = ["CO_CURSO", "CO_GRUPO", "CO_REGIAO_CURSO", "CO_CATEGAD"]
_COLUNAS_ARQ3 = ["CO_CURSO", "NT_GER", "NT_FG", "NT_CE", "TP_PRES"]


def _colunas_por_arquivo() -> Dict[int, List[str]]:
    cols = {1: _COLUNAS_ARQ1, 3: _COLUNAS_ARQ3}
    for n, cols_raw, _ in _ARQUIVOS_SIMPLES:
        cols[n] = ["CO_CURSO"] + cols_raw
    return cols


def _read_arq(n: int, colunas: Optional[List[str]] = None) -> pd.DataFrame:
    from modules.supabase_client import fetch_table
    columns = ",".join(colunas) if colunas else "*"
    return fetch_table(table_name(n), columns=columns)


def _read_todos_arquivos() -> Dict[int, pd.DataFrame]:
    """Busca os 13 arquivos em paralelo (I/O-bound — cada um pagina contra o
    Supabase independentemente dos outros, então rodar em série só soma
    tempo de espera de rede à toa)."""
    colunas_por_arquivo = _colunas_por_arquivo()
    with ThreadPoolExecutor(max_workers=13) as pool:
        futures = {
            n: pool.submit(_read_arq, n, cols)
            for n, cols in colunas_por_arquivo.items()
        }
        return {n: fut.result() for n, fut in futures.items()}


def _preprocessar(df: pd.DataFrame) -> pd.DataFrame:
    df = preprocess(df)
    df["CO_CURSO"] = df["CO_CURSO"].astype("int64")
    return df


def load_raw(grupos: Optional[List[int]] = None) -> pd.DataFrame:
    """
    Lê os 13 arquivos do INEP usados pelo E-XplainENADE a partir do Supabase,
    filtra por CO_GRUPO e agrega cada um por CO_CURSO — a única chave de
    junção válida entre arquivos do INEP (ver docstring do módulo). Retorna
    um DataFrame em nível de CURSO.

    Parameters
    ----------
    grupos : list[int], optional
        Valores de CO_GRUPO a incluir. Padrão: [4004, 4006] (CC + SI).

    Returns
    -------
    pd.DataFrame
        Uma linha por curso. Colunas: CO_CURSO, NT_GER, NT_FG, NT_CE
        (médias), QT_ALUNOS (peso — nº de presentes), CO_GRUPO, CO_REGIAO,
        TP_CATEGAD_BIN, CURSO_SI (1=SI, 0=CC) (atributos de curso/IES), CO_TURNO_V/N/I, TP_SEXO,
        NU_IDADE, QE_ESC_PAI, QE_ESC_MAE, QE_RENDA, QE_TRABALHO,
        QE_ACAO_AFIRM_BIN, QE_TIPO_EM_BIN, QE_FAM_SUPERIOR, QE_HORAS_ESTUDO
        (médias/proporções por curso).

        `df.attrs["funil"]` registra quantos cursos restam a cada etapa:
        cursos_recorte (arq1), cursos_com_nota (arq3), cursos_excluidos_categad
        (CO_CATEGAD sem classificação) e cursos_final (após o inner join).
    """
    grupos = grupos or [4004, 4006]

    arquivos = _read_todos_arquivos()  # as 13 buscas rodam em paralelo aqui

    a1 = arquivos[1]
    a1["CO_GRUPO"] = a1["CO_GRUPO"].astype(int)
    cursos_recorte = set(a1.loc[a1["CO_GRUPO"].isin(grupos), "CO_CURSO"])

    def _restringir(df: pd.DataFrame) -> pd.DataFrame:
        return df[df["CO_CURSO"].isin(cursos_recorte)].reset_index(drop=True)

    # ── arq3 — notas (Y) + peso (QT_ALUNOS = nº de presentes) ────────────────
    df3 = _preprocessar(
        _restringir(arquivos[3])[["CO_CURSO", "NT_GER", "NT_FG", "NT_CE", "TP_PRES"]]
    )
    df3 = df3[df3["TP_PRES"] == 555]
    df3 = df3[df3["NT_GER"].notna() & (df3["NT_GER"] > 0)]
    notas = df3.groupby("CO_CURSO").agg(
        NT_GER=("NT_GER", "mean"),
        NT_FG=("NT_FG", "mean"),
        NT_CE=("NT_CE", "mean"),
        QT_ALUNOS=("NT_GER", "count"),
    ).reset_index()

    # ── arq1 — atributos de curso/IES (constantes por curso) ─────────────────
    df1 = _preprocessar(_restringir(a1)[["CO_CURSO", "CO_GRUPO", "CO_REGIAO_CURSO", "CO_CATEGAD"]])
    curso_info = df1.groupby("CO_CURSO").agg(
        CO_GRUPO=("CO_GRUPO", "first"),
        CO_REGIAO=("CO_REGIAO", "first"),
        TP_CATEGAD_BIN=("TP_CATEGAD_BIN", "mean"),
    ).reset_index()
    # CURSO_SI (2026-10-14 — ver DEVELOPMENT.md): controle do curso nos modelos que
    # misturam CC e SI. CO_GRUPO é código nominal (4004/4006) e não pode entrar
    # como número na regressão; vira binária com CC como referência.
    curso_info["CURSO_SI"] = (curso_info["CO_GRUPO"] == 4006).astype("int64")

    excluidos_categad = set(
        df1.loc[df1["CO_CATEGAD"].isin(CATEGAD_SEM_CLASSIFICACAO), "CO_CURSO"]
    )
    curso_info = curso_info[~curso_info["CO_CURSO"].isin(excluidos_categad)]

    base = notas.merge(curso_info, on="CO_CURSO", how="inner")

    # ── Demais arquivos: uma pergunta cada, agregada por média/proporção ─────
    for n, cols_raw, cols_final in _ARQUIVOS_SIMPLES:
        df = _preprocessar(_restringir(arquivos[n])[["CO_CURSO"] + cols_raw])
        df = df.dropna(subset=cols_final)
        agg = df.groupby("CO_CURSO")[cols_final].mean().reset_index()
        base = base.merge(agg, on="CO_CURSO", how="inner")

    base.attrs["funil"] = {
        "cursos_recorte": len(cursos_recorte),
        "cursos_com_nota": int(len(notas)),
        "cursos_excluidos_categad": len(excluidos_categad & set(notas["CO_CURSO"])),
        "motivo_exclusao_categad": (
            "CO_CATEGAD = 7 (Especial): o dicionário do INEP não classifica essa "
            "categoria como pública nem privada, então TP_CATEGAD_BIN fica indefinido"
        ),
        "cursos_final": int(len(base)),
    }
    return base
