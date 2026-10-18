"""
Função pura `processar_ano(ano) -> dict` — executa o ETL completo de UM ano
do ENADE sobre os TXT brutos e devolve métricas, SEM ESCREVER NADA EM DISCO
e SEM CONECTAR EM BANCO.

Reaproveita a lógica de `scripts/02_processar_microdados_enade.py` (constantes
e utilitários), mas removeu:
  - escrita do CSV filtrado por ano
  - escrita do CSV consolidado
  - geração de relatorio_processamento.csv
  - prints intermediários

Esta função é executada por workers do ProcessPoolExecutor. Por isso:
  - é top-level (importável)
  - não tem efeitos colaterais
  - todas as constantes são imutáveis
  - não abre conexão de banco

Retorna um `dict` com:
    ano, worker_pid, timestamp_inicio, timestamp_fim, tempo_seg,
    linhas_arq1, linhas_arq3, linhas_filtradas, cursos_unicos,
    min_media, max_media, mean_media, count_cursos_com_media,
    status ('ok' | 'erro'), observacoes
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Configurações (cópia das do scripts/02_processar_microdados_enade.py)
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent


def _dir_microdados() -> Path:
    """Onde estão as pastas microdados_enade_*: ENADE_TIME_MICRODADOS_DIR ou candidatos padrão.

    Os TXT brutos do INEP (3+ GB) NÃO entram no repositório do grupo. Candidatos:
    1. env ENADE_TIME_MICRODADOS_DIR;
    2. <pai do EnadeX>/microdados (convenção do ecossistema — mesma do educluster);
    3. <pai do EnadeX>/ENADE (repositório original do subprojeto);
    4. o próprio enade_time/ (layout antigo).
    """
    import os as _os
    env = _os.environ.get("ENADE_TIME_MICRODADOS_DIR")
    candidatos = ([Path(env)] if env else []) + [
        RAIZ.parent.parent / "microdados",
        RAIZ.parent.parent / "ENADE",
        RAIZ,
    ]
    for c in candidatos:
        try:
            if c.is_dir() and any(c.glob("microdados_enade_*")):
                return c
        except OSError:
            continue
    return candidatos[0]


DIR_MICRODADOS = _dir_microdados()


def _dir_microdados() -> Path:
    """Onde estão as pastas microdados_enade_*: ENADE_TIME_MICRODADOS_DIR ou candidatos padrão.

    Os TXT brutos do INEP (3+ GB) NÃO entram no repositório do grupo. Candidatos:
    1. env ENADE_TIME_MICRODADOS_DIR;
    2. <pai do EnadeX>/microdados (convenção do ecossistema — mesma do educluster);
    3. <pai do EnadeX>/ENADE (repositório original do subprojeto);
    4. o próprio enade_time/ (layout antigo).
    """
    import os as _os
    env = _os.environ.get("ENADE_TIME_MICRODADOS_DIR")
    candidatos = ([Path(env)] if env else []) + [
        RAIZ.parent.parent / "microdados",
        RAIZ.parent.parent / "ENADE",
        RAIZ,
    ]
    for c in candidatos:
        try:
            if c.is_dir() and any(c.glob("microdados_enade_*")):
                return c
        except OSError:
            continue
    return candidatos[0]


DIR_MICRODADOS = _dir_microdados()

COLUNAS_ARQ1_OBRIGATORIAS = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MUNIC_CURSO", "CO_UF_CURSO", "CO_REGIAO_CURSO",
]
COLUNAS_ARQ1_OPCIONAIS = ["CO_MODALIDADE"]
COLUNAS_ARQ3 = ["CO_CURSO", "NT_FG"]

REGIOES_PERMITIDAS = frozenset({1, 2})
CODIGOS_COMPUTACAO = frozenset({40, 4004})

ENCODINGS = ("utf-8", "latin1", "cp1252")
SEPARADORES = (";", ",", "\t")

SENTINELAS_NA = ("", ".", "NA", "N/A", "nan", "NaN", "NAN", "null", "Null",
                 "NULL", "None", "none")


# ---------------------------------------------------------------------------
# Localização e leitura (cópia adaptada do script 02)
# ---------------------------------------------------------------------------

def encontrar_pasta_ano(ano: int) -> Path | None:
    for c in sorted(DIR_MICRODADOS.glob(f"microdados_enade_{ano}*")):
        if c.is_dir():
            return c
    return None


def encontrar_arquivo_arq(pasta_ano: Path, ano: int, n_arq: int) -> Path | None:
    padroes = (
        f"**/microdados{ano}_arq{n_arq}.*",
        f"**/microdados_{ano}_arq{n_arq}.*",
        f"**/microdados{ano}_arq{n_arq}*",
    )
    for padrao in padroes:
        for m in sorted(pasta_ano.glob(padrao)):
            if m.is_file():
                return m
    return None


def _detectar_encoding_separador(path: Path) -> tuple[str | None, str | None, list[str]]:
    melhor = (None, None, [], 0)
    for enc in ENCODINGS:
        for sep in SEPARADORES:
            try:
                df = pd.read_csv(
                    path, sep=sep, encoding=enc, nrows=5,
                    dtype=str, engine="python", on_bad_lines="skip",
                )
            except Exception:
                continue
            n = len(df.columns)
            if n > melhor[3] and n >= 2:
                melhor = (enc, sep, list(df.columns), n)
    return melhor[0], melhor[1], melhor[2]


def _ler_arquivo(path: Path, colunas: list[str] | None = None
                 ) -> tuple[pd.DataFrame | None, str, str]:
    enc, sep, header = _detectar_encoding_separador(path)
    if enc is None:
        return None, "", ""
    use = None
    if colunas is not None:
        use = [c for c in colunas if c in header]
        if not use:
            return None, enc, sep
    df = pd.read_csv(
        path, sep=sep, encoding=enc, dtype=str,
        usecols=use, engine="python", on_bad_lines="skip",
    )
    return df, enc, sep


# ---------------------------------------------------------------------------
# Conversões numéricas
# ---------------------------------------------------------------------------

def _converter_inteiro(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip().str.strip('"').str.strip("'")
    s = s.replace(list(SENTINELAS_NA), np.nan)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def _converter_nt_fg(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip().str.strip('"').str.strip("'")
    s = s.replace(list(SENTINELAS_NA), np.nan)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


# ---------------------------------------------------------------------------
# Função principal — pura, sem efeitos colaterais
# ---------------------------------------------------------------------------

def _agora() -> tuple[datetime, str]:
    dt = datetime.now(timezone.utc)
    return dt, dt.isoformat()


def processar_ano(ano: int) -> dict:
    """
    Executa o ETL de um ano e devolve métricas.

    SEM I/O em disco. SEM conexão de banco. SEM prints.
    Pode ser invocada por workers de ProcessPoolExecutor.

    Em caso de erro de leitura, devolve dict com status='erro' e mensagem
    em 'observacoes'. NÃO levanta exceção (para o pool continuar).
    """
    dt_ini, ts_ini = _agora()
    t0 = time.perf_counter()
    pid = os.getpid()

    out: dict = {
        "ano": ano,
        "worker_pid": pid,
        "timestamp_inicio": ts_ini,
        "timestamp_fim": ts_ini,
        "tempo_seg": 0.0,
        "linhas_arq1": 0,
        "linhas_arq3": 0,
        "linhas_filtradas": 0,
        "cursos_unicos": 0,
        "min_media": None,
        "max_media": None,
        "mean_media": None,
        "count_cursos_com_media": 0,
        "status": "erro",
        "observacoes": "",
    }

    try:
        pasta = encontrar_pasta_ano(ano)
        if pasta is None:
            out["observacoes"] = f"Pasta 'microdados_enade_{ano}*' não existe"
            return _fechar(out, t0)

        arq1 = encontrar_arquivo_arq(pasta, ano, 1)
        arq3 = encontrar_arquivo_arq(pasta, ano, 3)
        if arq1 is None or arq3 is None:
            falt = [n for n, p in (("arq1", arq1), ("arq3", arq3)) if p is None]
            out["observacoes"] = "Não encontrado(s): " + ", ".join(falt)
            return _fechar(out, t0)

        # ----- arq1 (cadastro) -----
        cols_pedidas = COLUNAS_ARQ1_OBRIGATORIAS + COLUNAS_ARQ1_OPCIONAIS
        df1, _, _ = _ler_arquivo(arq1, colunas=cols_pedidas)
        if df1 is None:
            out["observacoes"] = "Falha ao ler arq1"
            return _fechar(out, t0)
        out["linhas_arq1"] = len(df1)

        ausentes = [c for c in COLUNAS_ARQ1_OBRIGATORIAS if c not in df1.columns]
        if ausentes:
            out["observacoes"] = f"arq1 sem colunas obrigatórias: {ausentes}"
            return _fechar(out, t0)

        obs_extra: list[str] = []
        if "CO_MODALIDADE" not in df1.columns:
            df1["CO_MODALIDADE"] = pd.NA
            obs_extra.append("CO_MODALIDADE ausente — preenchida com NA")

        for col in COLUNAS_ARQ1_OBRIGATORIAS + COLUNAS_ARQ1_OPCIONAIS:
            df1[col] = _converter_inteiro(df1[col])

        df1f = df1[
            df1["CO_REGIAO_CURSO"].isin(REGIOES_PERMITIDAS)
            & df1["CO_GRUPO"].isin(CODIGOS_COMPUTACAO)
        ]
        out["linhas_filtradas"] = len(df1f)
        out["cursos_unicos"] = int(df1f["CO_CURSO"].nunique())

        if df1f.empty:
            out["status"] = "ok"
            out["observacoes"] = "; ".join(
                [*obs_extra, "Nenhum aluno de 40/4004 nas regiões 1/2"])
            return _fechar(out, t0)

        # ----- arq3 (notas) -----
        df3, _, _ = _ler_arquivo(arq3, colunas=COLUNAS_ARQ3)
        if (df3 is None
                or "NT_FG" not in df3.columns
                or "CO_CURSO" not in df3.columns):
            out["observacoes"] = "; ".join(
                [*obs_extra, "arq3 sem NT_FG ou CO_CURSO"])
            return _fechar(out, t0)
        out["linhas_arq3"] = len(df3)

        df3["CO_CURSO"] = _converter_inteiro(df3["CO_CURSO"])
        df3["NT_FG"] = _converter_nt_fg(df3["NT_FG"])
        df3 = df3.dropna(subset=["CO_CURSO", "NT_FG"])

        medias = (df3.groupby("CO_CURSO", as_index=False)["NT_FG"]
                  .mean()
                  .rename(columns={"NT_FG": "MEDIA_NT_FG"}))

        if medias.empty:
            out["status"] = "ok"
            out["observacoes"] = "; ".join(
                [*obs_extra, "Nenhum NT_FG válido para calcular média"])
            return _fechar(out, t0)

        # ----- merge (não persiste; só para contar cursos com média) -----
        final = df1f[["CO_CURSO"]].merge(medias, on="CO_CURSO", how="left")
        out["count_cursos_com_media"] = int(
            final.loc[final["MEDIA_NT_FG"].notna(), "CO_CURSO"].nunique())

        out["min_media"] = float(medias["MEDIA_NT_FG"].min())
        out["max_media"] = float(medias["MEDIA_NT_FG"].max())
        out["mean_media"] = float(medias["MEDIA_NT_FG"].mean())
        out["status"] = "ok"
        out["observacoes"] = "; ".join(obs_extra) if obs_extra else ""

    except Exception as exc:  # nunca quebra o pool
        out["status"] = "erro"
        out["observacoes"] = f"{type(exc).__name__}: {exc}"

    return _fechar(out, t0)


def _fechar(out: dict, t0: float) -> dict:
    dt_fim, ts_fim = _agora()
    out["timestamp_fim"] = ts_fim
    out["tempo_seg"] = round(time.perf_counter() - t0, 4)
    return out
