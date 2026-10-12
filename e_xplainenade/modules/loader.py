"""
Camada 2 — Recodificação (usada por etl.py) e carga da base agregada.

As funções de recodificação (preprocess() e helpers) operam em nível de
ESTUDANTE e são chamadas por modules/etl.py — uma vez por arquivo bruto,
antes da agregação por CO_CURSO — para garantir que a agregação use as
mesmas regras de recodificação em todo o sistema.

get_dataset_from_supabase() carrega a base agregada por curso direto do
Supabase (única fonte de dados do sistema desde 2026-08-30 — ver
DEVELOPMENT.md) — não precisa (e não deve) rodar preprocess() de novo, pois
etl.load_raw() já aplica a recodificação por arquivo antes da agregação.
"""
from typing import List, Optional

import pandas as pd

from config.variable_map import VARIABLE_MAP

# Mapeamento letra → inteiro para QE_I01–QE_I26 (A-E/F/G/H conforme a questão)
_LETTER_TO_INT = {chr(65 + i): i + 1 for i in range(26)}  # A=1 … Z=26


def _recode_questionnaire(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recodifica variáveis do questionário:
    - QE_I01–I26 (letras A-H): A→1, B→2, ... (mapeamento ordinal alfabético)
    - QE_I27–I68 (Likert '1'–'6'): converte para int; 7/8 → NaN (não sei/não se aplica)
    - QE_I16 (código IBGE da UF): converte para int, não reordena
    - QE_I69+ (pandemia): converte para int se possível
    """
    for col in df.columns:
        if not col.startswith("QE_I"):
            continue

        try:
            idx = int(col.replace("QE_I", ""))
        except ValueError:
            continue

        if 1 <= idx <= 26:
            if idx == 16:
                # UF do EM — código numérico IBGE, não ordinal
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = df[col].map(_LETTER_TO_INT)
        elif 27 <= idx <= 68:
            # Likert 1–6; 7 = "Não sei responder", 8 = "Não se aplica" → NaN
            numeric = pd.to_numeric(df[col], errors="coerce")
            df[col] = numeric.where(numeric <= 6, other=pd.NA)
        else:
            # QE_I69+ (questões de pandemia): recodifica letras se necessário
            first_valid = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            if first_valid and str(first_valid).isalpha():
                df[col] = df[col].map(_LETTER_TO_INT)
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _convert_types(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas para os tipos numéricos corretos."""
    qe_cols = {c for c in df.columns if c.startswith("QE_I")}

    for col in df.columns:
        if col in qe_cols:
            continue
        if col.startswith("NT_"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif col == "TP_SEXO":
            df[col] = df[col].map({"F": 0, "M": 1})
        elif not col.startswith("DS_"):
            # DS_* são strings de gabarito/resposta — não usar em modelagem
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas brutas para os códigos amigáveis definidos no variable_map."""
    rename = {
        raw: info["code"]
        for raw, info in VARIABLE_MAP.items()
        if raw in df.columns and info["code"] != raw
    }
    return df.rename(columns=rename)


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deriva variáveis analíticas para uso correto em OLS.
    Chamado internamente por preprocess() após renomeação de colunas.

    Correções de convenção:
      QE_FAM_SUPERIOR  1=Sim/2=Não  →  1=Sim/0=Não
      QE_TIPO_EM       1=Pública/2=Privada  →  QE_TIPO_EM_BIN: 0=Pública/1=Privada

    Variáveis nominais → binárias/dummies:
      QE_ACAO_AFIRM    nominal (A-E)  →  QE_ACAO_AFIRM_BIN: 0=Sem cota/1=Qualquer cota
      CO_TURNO         nominal (1-4)  →  3 dummies (ref=Matutino):
                                          CO_TURNO_V (Vespertino)
                                          CO_TURNO_N (Noturno)
                                          CO_TURNO_I (Integral)
    """
    # QE_FAM_SUPERIOR: ENADE codifica 1=Sim, 2=Não — convenção inversa à binária padrão
    if "QE_FAM_SUPERIOR" in df.columns:
        df["QE_FAM_SUPERIOR"] = df["QE_FAM_SUPERIOR"].map({1: 1, 2: 0})

    # QE_TIPO_EM: 1=Escola Pública → 0, 2=Escola Privada → 1
    if "QE_TIPO_EM" in df.columns:
        df["QE_TIPO_EM_BIN"] = df["QE_TIPO_EM"].map({1: 0, 2: 1})

    # QE_ACAO_AFIRM: 1=Sem cota → 0; 2-5=alguma cota (racial/escola/socioecon./def.) → 1
    if "QE_ACAO_AFIRM" in df.columns:
        _a = pd.to_numeric(df["QE_ACAO_AFIRM"], errors="coerce")
        df["QE_ACAO_AFIRM_BIN"] = _a.where(_a.isna(), (_a > 1).astype("float64"))

    # CO_TURNO dummies — referência: Matutino (1), categoria mais comum em CC/SI
    if "CO_TURNO" in df.columns:
        _t = pd.to_numeric(df["CO_TURNO"], errors="coerce")
        _na = _t.isna()
        df["CO_TURNO_V"] = _t.where(_na, (_t == 2).astype("float64"))
        df["CO_TURNO_N"] = _t.where(_na, (_t == 3).astype("float64"))
        df["CO_TURNO_I"] = _t.where(_na, (_t == 4).astype("float64"))

    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica recodificação, conversão de tipos, renomeação e enriquecimento analítico.
    Entrada: DataFrame bruto de etl.load_raw() ou pd.read_csv().
    Saída: DataFrame tipado, nomes amigáveis e variáveis derivadas, pronto para OLS.
    Nota: opera in-place (sem df.copy()) para economizar memória.
    """
    df = _recode_questionnaire(df)
    df = _convert_types(df)
    df = _rename_columns(df)
    # CO_CATEGAD (nominal 1-5) binarizado: 1/2/3=Pública→0, 4/5=Privada→1
    if "CO_CATEGAD" in df.columns:
        df["TP_CATEGAD_BIN"] = df["CO_CATEGAD"].map(
            {1: 0, 2: 0, 3: 0, 4: 1, 5: 1}
        )
    df = _enrich(df)
    return df


# Cache em memória (processo local) do resultado de etl.load_raw(), por
# `grupos` — evita repetir as 13 consultas paginadas ao Supabase a cada request.
# Não persiste entre reinícios do processo; ver DEVELOPMENT.md para a pendência
# em aberto sobre persistir isso no banco versus sempre recomputar.
_supabase_cache: dict = {}


def get_dataset_from_supabase(
    grupos: Optional[List[int]] = None,
    ies_filter: Optional[List[int]] = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Carrega a base agregada por curso a partir do Supabase (tbl_arq1_2021 ...
    tbl_arq29_2021) — única fonte de dados do sistema. É o ponto de entrada
    usado por app.py e por e_xplainenade_rotas.py.

    Parameters
    ----------
    grupos : list[int], optional
        CO_GRUPO a incluir (ex: [4004]). None = todos os cursos do recorte.
    ies_filter : list[int], optional
        Valores de TP_CATEGAD_BIN a incluir (0=Pública, 1=Privada).
    force_refresh : bool, optional
        Ignora o cache em memória e refaz as consultas ao Supabase.

    Returns
    -------
    pd.DataFrame
        Uma linha por curso, nomes amigáveis, pronta para modelagem.

    Raises
    ------
    RuntimeError
        Se a agregação vier vazia (ex: as tabelas do Supabase ainda não foram
        populadas com os 13 arquivos do escopo do E-XplainENADE).
    """
    from modules import etl  # import local: evita ciclo de import com etl.py

    chave = tuple(sorted(grupos)) if grupos else None
    if force_refresh or chave not in _supabase_cache:
        df = etl.load_raw(grupos=grupos)
        if df.empty:
            tabelas = ", ".join(etl.table_name(n) for n in
                                 [1, 2, 3, 5, 6, 10, 11, 14, 16, 21, 23, 27, 29])
            raise RuntimeError(
                "Nenhum curso retornado do Supabase para este recorte. "
                "Verifique se as 13 tabelas do escopo do E-XplainENADE já foram "
                f"populadas: {tabelas}."
            )
        _supabase_cache[chave] = df

    df = _supabase_cache[chave]
    if ies_filter:
        df = df[df["TP_CATEGAD_BIN"].isin(ies_filter)].reset_index(drop=True)
    return df
