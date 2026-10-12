import os
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
RAIZ_TCC = RAIZ_PROJETO.parent
DIR_MICRODADOS = RAIZ_TCC / "microdados" / "microdados_Enade_2021_LGPD" / "2.DADOS"
DIR_CACHE = RAIZ_PROJETO / "educluster" / ".cache"

ANO_EDICAO = 2021

ORIGEM_PADRAO = os.getenv("EDUCLUSTER_ORIGEM", "supabase")

RANDOM_STATE = 42
N_INIT = 10
K_MINIMO = 2
K_MAXIMO = 8

N_MINIMO_RESPONDENTES = 20

CODIGOS_NAO_RESPOSTA_ARQ4 = [7, 8]
ESCALA_ARQ4_MINIMA = 1
ESCALA_ARQ4_MAXIMA = 6

CODIGO_PRESENCA_VALIDA = "555"

DIMENSOES_ARQ4 = {
    "ODP": [f"QE_I{i}" for i in range(27, 43)],
    "OPORT": [f"QE_I{i}" for i in range(43, 58)],
    "INFRA": [f"QE_I{i}" for i in range(58, 69)],
}

ITENS_ARQ4 = [item for itens in DIMENSOES_ARQ4.values() for item in itens]

NOTAS_ARQ3 = [
    "NT_GER", "NT_FG", "NT_OBJ_FG", "NT_DIS_FG",
    "NT_CE", "NT_OBJ_CE", "NT_DIS_CE",
]

PERCEPCAO_PROVA = [f"CO_RS_I{i}" for i in range(1, 10)]

SITUACAO_DISCURSIVAS = ["TP_SFG_D1", "TP_SFG_D2", "TP_SCE_D1", "TP_SCE_D2", "TP_SCE_D3"]

CODIGOS_SITUACAO_DISCURSIVA = {
    "333": "em_branco",
    "335": "resposta_nula",
    "336": "divergente_do_tema",
    "555": "valida",
}

CODIGOS_ABANDONO = ["333", "335", "336"]

ESCALA_PERCEPCAO_PROVA = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}

ROTULOS_PERCEPCAO_PROVA = {
    "CO_RS_I1": "Dificuldade da Formacao Geral",
    "CO_RS_I2": "Dificuldade do Componente Especifico",
    "CO_RS_I3": "Extensao da prova",
    "CO_RS_I4": "Clareza dos enunciados de FG",
    "CO_RS_I5": "Clareza dos enunciados de CE",
    "CO_RS_I6": "Suficiencia das instrucoes",
    "CO_RS_I7": "Tipo de dificuldade encontrada",
    "CO_RS_I8": "Percepcao sobre as objetivas",
    "CO_RS_I9": "Tempo gasto na prova",
}

COLS_ARQ3_CURSO = (
    ["CO_CURSO", "TP_PRES", "DS_VT_GAB_OCE_FIN"] + NOTAS_ARQ3
    + PERCEPCAO_PROVA + SITUACAO_DISCURSIVAS
)
COLS_ARQ4_CURSO = ["CO_CURSO"] + ITENS_ARQ4

FEATURES_A6 = ["NT_FG", "NT_CE", "tx_presenca", "ODP", "OPORT", "INFRA"]
FEATURES_A6_RELATIVAS = ["NT_FG_z", "NT_CE_z", "tx_presenca", "ODP", "OPORT", "INFRA"]

TABELAS_SUPABASE = {3: "tbl_educluster_arq3_2021", 4: "tbl_educluster_arq4_2021"}
TABELA_CURSOS_SUPABASE = "tbl_educluster_cursos_2021"
SUPABASE_PAGINA = 1000
SUPABASE_PARALELISMO = 8

CAMINHO_ZIP_MICRODADOS = Path(os.getenv("EDUCLUSTER_ZIP_MICRODADOS", Path.home() / "Downloads" / "microdados_enade_2021.zip"))
PASTA_DADOS_NO_ZIP = "microdados_Enade_2021_LGPD/2.DADOS"
ATRIBUTOS_CURSO = [
    "CO_IES", "CO_CATEGAD", "CO_ORGACAD", "CO_GRUPO",
    "CO_MODALIDADE", "CO_MUNIC_CURSO", "CO_UF_CURSO", "CO_REGIAO_CURSO",
]

ROTULOS_DIMENSAO = {
    "ODP": "Organizacao Didatico Pedagogica",
    "OPORT": "Oportunidades de Ampliacao da Formacao",
    "INFRA": "Infraestrutura",
}

ESPACOS_PERFIL_DESEMPENHO = {
    "trio": ["NT_GER", "NT_FG", "NT_CE"],
    "par": ["NT_FG", "NT_CE"],
    "objetivo_discursivo": ["NT_OBJ_FG", "NT_DIS_FG", "NT_OBJ_CE", "NT_DIS_CE"],
}

AMOSTRA_SILHOUETTE = 20000

MODELO_GEMINI = "gemini-2.5-flash"
