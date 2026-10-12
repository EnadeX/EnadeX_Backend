"""
Dicionário de variáveis do ENADE 2021.

Mapeia código bruto → {code, label, type}
  - code  : nome amigável usado nas fórmulas OLS e no relatório
  - label : descrição legível para exibição na interface
  - type  : 'ordinal' | 'nominal' | 'binary' | 'continuous' | 'likert'

Mapeamentos confirmados contra:
  Questionário do Estudante Enade 2021 (pasta microdados_Enade_2021_LGPD/1.LEIA-ME)
"""

VARIABLE_MAP = {
    # ── Variáveis-alvo (notas) ────────────────────────────────────────────────
    "NT_GER": {"code": "NT_GER",  "label": "Nota Geral",                      "type": "continuous"},
    "NT_FG":  {"code": "NT_FG",   "label": "Nota Formação Geral",              "type": "continuous"},
    "NT_CE":  {"code": "NT_CE",   "label": "Nota Componente Específico",       "type": "continuous"},

    # ── Contexto institucional ────────────────────────────────────────────────
    "CO_GRUPO":        {"code": "CO_GRUPO",    "label": "Curso (CC/SI)",              "type": "nominal"},
    "CO_REGIAO_CURSO": {"code": "CO_REGIAO",   "label": "Região",                     "type": "nominal"},
    "CO_CATEGAD":      {"code": "CO_CATEGAD",  "label": "Categoria Administrativa",   "type": "nominal"},
    "CO_ORGACAD":      {"code": "CO_ORGACAD",  "label": "Organização Acadêmica",      "type": "nominal"},
    "CO_MODALIDADE":   {"code": "CO_MODALIDADE","label": "Modalidade (Pres./EAD)",    "type": "binary"},
    "CO_TURNO_GRADUACAO": {"code": "CO_TURNO", "label": "Turno",                      "type": "nominal"},

    # ── Perfil do estudante ───────────────────────────────────────────────────
    "TP_SEXO":  {"code": "TP_SEXO",  "label": "Sexo (0=F, 1=M)",  "type": "binary"},
    "NU_IDADE": {"code": "NU_IDADE", "label": "Idade",             "type": "continuous"},

    # ── Questionário socioeconômico (QE_I01–QE_I26) ───────────────────────────
    # Fonte: Questionário do Estudante ENADE 2021 — mapeamentos confirmados
    "QE_I01": {"code": "QE_ESTADO_CIVIL",  "label": "Estado Civil",                         "type": "nominal"},
    "QE_I02": {"code": "QE_RACA",          "label": "Cor/Raça",                             "type": "nominal"},
    "QE_I03": {"code": "QE_NACIONALIDADE", "label": "Nacionalidade",                        "type": "nominal"},
    "QE_I04": {"code": "QE_ESC_PAI",       "label": "Escolaridade do Pai",                  "type": "ordinal"},
    "QE_I05": {"code": "QE_ESC_MAE",       "label": "Escolaridade da Mãe",                  "type": "ordinal"},
    "QE_I06": {"code": "QE_MORADIA",       "label": "Situação de Moradia",                  "type": "nominal"},
    "QE_I07": {"code": "QE_TAM_FAMILIA",   "label": "Pessoas da Família que Moram Junto",   "type": "ordinal"},
    "QE_I08": {"code": "QE_RENDA",         "label": "Renda Familiar Mensal",                "type": "ordinal"},
    "QE_I09": {"code": "QE_SITUACAO_FIN",  "label": "Situação Financeira",                  "type": "ordinal"},
    "QE_I10": {"code": "QE_TRABALHO",      "label": "Situação de Trabalho",                 "type": "ordinal"},
    "QE_I11": {"code": "QE_FINANCIAMENTO", "label": "Bolsa/Financiamento do Curso",         "type": "nominal"},
    "QE_I12": {"code": "QE_AUXILIO_PERM",  "label": "Auxílio Permanência",                  "type": "nominal"},
    "QE_I13": {"code": "QE_BOLSA_ACAD",    "label": "Bolsa Acadêmica",                      "type": "nominal"},
    "QE_I14": {"code": "QE_INTERCAMBIO",   "label": "Participação em Intercâmbio",          "type": "nominal"},
    "QE_I15": {"code": "QE_ACAO_AFIRM",    "label": "Ingresso por Ação Afirmativa",         "type": "nominal"},
    "QE_I16": {"code": "QE_UF_EM",         "label": "UF onde Concluiu o Ensino Médio",      "type": "nominal"},
    "QE_I17": {"code": "QE_TIPO_EM",       "label": "Tipo de Escola no Ensino Médio",       "type": "ordinal"},
    "QE_I18": {"code": "QE_MODALIDADE_EM", "label": "Modalidade do Ensino Médio",           "type": "nominal"},
    "QE_I19": {"code": "QE_INCENTIVO",     "label": "Incentivo para Cursar a Graduação",    "type": "nominal"},
    "QE_I20": {"code": "QE_APOIO",         "label": "Apoio para Enfrentar Dificuldades",    "type": "nominal"},
    "QE_I21": {"code": "QE_FAM_SUPERIOR",  "label": "Familiar com Ensino Superior",         "type": "binary"},
    "QE_I22": {"code": "QE_LIVROS",        "label": "Livros Lidos Além dos Obrigatórios",   "type": "ordinal"},
    "QE_I23": {"code": "QE_HORAS_ESTUDO",  "label": "Horas de Estudo por Semana",           "type": "ordinal"},
    "QE_I24": {"code": "QE_IDIOMA",        "label": "Aprendizado de Idioma Estrangeiro",    "type": "nominal"},
    "QE_I25": {"code": "QE_MOTIVO_CURSO",  "label": "Motivo para Escolher o Curso",         "type": "nominal"},
    "QE_I26": {"code": "QE_MOTIVO_IES",    "label": "Motivo para Escolher a IES",           "type": "nominal"},

    # ── Avaliação do curso/IES (QE_I27–I68, Likert 1–6) ─────────────────────
    "QE_I27": {"code": "QE_FORM_INTEGRAL",    "label": "Formação Integral (cidadão/prof.)",     "type": "likert"},
    "QE_I28": {"code": "QE_ESTAGIO_CONTEUDO", "label": "Conteúdos Favoreceram Estágio",         "type": "likert"},
    "QE_I29": {"code": "QE_METODOLOGIA",      "label": "Metodologias Desafiadoras",              "type": "likert"},
    "QE_I30": {"code": "QE_INOVACAO",         "label": "Experiências Inovadoras",                "type": "likert"},
    "QE_I31": {"code": "QE_ETICA",            "label": "Consciência Ética Profissional",         "type": "likert"},
    "QE_I32": {"code": "QE_TRABALHO_EQUIPE",  "label": "Trabalho em Equipe",                     "type": "likert"},
    "QE_I33": {"code": "QE_REFLEXAO",         "label": "Reflexão e Argumentação",                "type": "likert"},
    "QE_I34": {"code": "QE_PENSAMENTO_CRIT",  "label": "Pensamento Crítico",                     "type": "likert"},
    "QE_I35": {"code": "QE_COMUNICACAO",      "label": "Comunicação Oral e Escrita",             "type": "likert"},
    "QE_I36": {"code": "QE_APRENDIZADO_CONT", "label": "Aprendizado Contínuo",                   "type": "likert"},
    "QE_I37": {"code": "QE_REL_PROF_ALUNO",   "label": "Relação Professor-Aluno",                "type": "likert"},
    "QE_I38": {"code": "QE_PLANOS_ENSINO",    "label": "Planos de Ensino",                       "type": "likert"},
    "QE_I39": {"code": "QE_REFERENCIAS",      "label": "Referências Bibliográficas",             "type": "likert"},
    "QE_I40": {"code": "QE_SUPERACAO_DIFIC",  "label": "Oportunidades de Superação",             "type": "likert"},
    "QE_I41": {"code": "QE_COORD_DISP",       "label": "Disponibilidade da Coordenação",         "type": "likert"},
    "QE_I42": {"code": "QE_DEDICACAO",        "label": "Exigência de Dedicação",                 "type": "likert"},
    "QE_I43": {"code": "QE_EXTENSAO",         "label": "Atividades de Extensão",                 "type": "likert"},
    "QE_I44": {"code": "QE_IC",               "label": "Iniciação Científica",                   "type": "likert"},
    "QE_I45": {"code": "QE_EVENTOS",          "label": "Participação em Eventos",                "type": "likert"},
    "QE_I46": {"code": "QE_REPR_COLEGIADO",   "label": "Representação em Órgãos Colegiados",    "type": "likert"},
    "QE_I47": {"code": "QE_TEORIA_PRATICA",   "label": "Articulação Teoria-Prática",             "type": "likert"},
    "QE_I48": {"code": "QE_ATIV_PRATICAS",    "label": "Atividades Práticas",                    "type": "likert"},
    "QE_I49": {"code": "QE_ATUALIZACAO",      "label": "Conhecimentos Atualizados",              "type": "likert"},
    "QE_I50": {"code": "QE_ESTAGIO",          "label": "Estágio Supervisionado",                 "type": "likert"},
    "QE_I51": {"code": "QE_TCC",              "label": "TCC",                                    "type": "likert"},
    "QE_I52": {"code": "QE_INTERCAMBIO_PAI",  "label": "Intercâmbios no País",                   "type": "likert"},
    "QE_I53": {"code": "QE_INTERCAMBIO_EXT",  "label": "Intercâmbios no Exterior",               "type": "likert"},
    "QE_I54": {"code": "QE_AVAL_PERIODICA",   "label": "Avaliações Periódicas do Curso",         "type": "likert"},
    "QE_I55": {"code": "QE_AVAL_APREND",      "label": "Avaliações de Aprendizagem",             "type": "likert"},
    "QE_I56": {"code": "QE_PROF_DISP",        "label": "Disponibilidade dos Professores",        "type": "likert"},
    "QE_I57": {"code": "QE_PROF_DOMINIO",     "label": "Domínio de Conteúdo dos Professores",    "type": "likert"},
    "QE_I58": {"code": "QE_TIC",              "label": "Uso de TICs pelos Professores",           "type": "likert"},
    "QE_I59": {"code": "QE_APOIO_ADM",        "label": "Apoio Administrativo",                   "type": "likert"},
    "QE_I60": {"code": "QE_MONITORIA",        "label": "Monitores/Tutores",                      "type": "likert"},
    "QE_I61": {"code": "QE_INFRA_SALA",       "label": "Infraestrutura das Salas",               "type": "likert"},
    "QE_I62": {"code": "QE_EQUIP_PRATICA",    "label": "Equipamentos para Aulas Práticas",       "type": "likert"},
    "QE_I63": {"code": "QE_AMBIENTES",        "label": "Ambientes para Aulas Práticas",          "type": "likert"},
    "QE_I64": {"code": "QE_BIBLIOTECA",       "label": "Biblioteca",                             "type": "likert"},
    "QE_I65": {"code": "QE_BIBL_VIRTUAL",     "label": "Biblioteca Virtual",                     "type": "likert"},
    "QE_I66": {"code": "QE_DIVERSIDADE",      "label": "Respeito à Diversidade",                 "type": "likert"},
    "QE_I67": {"code": "QE_CULTURA_LAZER",    "label": "Cultura e Lazer",                        "type": "likert"},
    "QE_I68": {"code": "QE_REFEITORIO",       "label": "Refeitório/Cantina/Banheiros",           "type": "likert"},
}

# Mapa reverso: código amigável → coluna bruta
REVERSE_MAP = {v["code"]: k for k, v in VARIABLE_MAP.items()}

# Código amigável → rótulo legível (usado na interpretação automática)
CODE_TO_LABEL = {v["code"]: v["label"] for v in VARIABLE_MAP.values()}

# Variáveis derivadas — criadas por _enrich() em loader.py, não existem nos arquivos brutos
CODE_TO_LABEL["TP_CATEGAD_BIN"]    = "Tipo de IES (Pública/Privada)"
CODE_TO_LABEL["QE_TIPO_EM_BIN"]    = "Tipo de Escola no EM (0=Pública, 1=Privada)"
CODE_TO_LABEL["QE_ACAO_AFIRM_BIN"] = "Ingressou por Ação Afirmativa (0=Não, 1=Sim)"
CODE_TO_LABEL["CO_TURNO_V"]        = "Turno: Vespertino (ref. Matutino)"
CODE_TO_LABEL["CO_TURNO_N"]        = "Turno: Noturno (ref. Matutino)"
CODE_TO_LABEL["CO_TURNO_I"]        = "Turno: Integral (ref. Matutino)"
CODE_TO_LABEL["QT_ALUNOS"]         = "Nº de Alunos Presentes no Curso"

# Labels para valores categóricos — exibição na UI e no relatório
VALUE_LABELS = {
    "CO_TURNO": {1: "Matutino", 2: "Vespertino", 3: "Noturno", 4: "Integral"},
    "CO_CATEGAD": {
        1: "Fed. Pública", 2: "Est. Pública", 3: "Mun. Pública",
        4: "Privada s/fins", 5: "Privada c/fins",
    },
    "TP_CATEGAD_BIN":    {0: "Pública",  1: "Privada"},
    "QE_TIPO_EM_BIN":    {0: "Pública",  1: "Privada"},
    "QE_ACAO_AFIRM_BIN": {0: "Não",      1: "Sim (qualquer cota)"},
    "CO_TURNO_V":        {0: "Não",      1: "Sim"},
    "CO_TURNO_N":        {0: "Não",      1: "Sim"},
    "CO_TURNO_I":        {0: "Não",      1: "Sim"},
    "CO_GRUPO":   {4004: "Ciência da Computação", 4005: "Engenharia de Software", 4006: "Sistemas de Informação"},
    "CO_REGIAO":  {1: "Norte", 2: "Nordeste", 3: "Sudeste", 4: "Sul", 5: "Centro-Oeste"},
    "TP_SEXO":    {0: "Feminino", 1: "Masculino"},
    "QE_FAM_SUPERIOR": {0: "Não", 1: "Sim"},
    "QE_TIPO_EM": {1: "Escola Pública", 2: "Escola Privada"},
}

# Variáveis analiticamente mais relevantes para modelagem de desempenho CC/SI
# (sugeridas pela literatura e pelo MultiENADE)
VARS_SUGERIDAS = [
    "QE_RENDA",       # QE_I08 — renda familiar
    "QE_ESC_MAE",     # QE_I05 — escolaridade da mãe
    "QE_ESC_PAI",     # QE_I04 — escolaridade do pai
    "QE_TRABALHO",    # QE_I10 — situação de trabalho
    "QE_HORAS_ESTUDO",# QE_I23 — horas de estudo
    "QE_TIPO_EM",     # QE_I17 — tipo de escola no EM
    "QE_FAM_SUPERIOR",# QE_I21 — familiar com superior
    "QE_ACAO_AFIRM",  # QE_I15 — ação afirmativa
    "TP_SEXO",
    "NU_IDADE",
    "CO_TURNO",
    "TP_CATEGAD_BIN",
]


def get_label(raw_col: str) -> str:
    """Retorna o rótulo legível de uma coluna bruta."""
    return VARIABLE_MAP.get(raw_col, {}).get("label", raw_col)


def get_code(raw_col: str) -> str:
    """Retorna o código amigável de uma coluna bruta."""
    return VARIABLE_MAP.get(raw_col, {}).get("code", raw_col)


def get_type(raw_col: str) -> str:
    """Retorna o tipo da variável ('ordinal', 'nominal', 'binary', 'continuous', 'likert')."""
    return VARIABLE_MAP.get(raw_col, {}).get("type", "unknown")


# ── Opções de hipótese/filtro expostas na interface ─────────────────────────
# Usadas por app.py (Streamlit) e por e_xplainenade_rotas.py (API) — únicas,
# para as duas interfaces não divergirem sobre quais variáveis/recortes existem.

Y_OPTS = {
    "Nota Geral":            "NT_GER",
    "Formação Geral":        "NT_FG",
    "Componente Específico": "NT_CE",
}

X_OPTS = {
    # Socioeconômicas — médias/proporções por curso (base agregada por CO_CURSO)
    "Renda Familiar":                  "QE_RENDA",           # média do curso, escala 1=até 1,5SM … 7=>30SM
    "Escolaridade da Mãe":             "QE_ESC_MAE",         # média do curso, escala 1=Nunca estudou … 6=Pós-grad.
    "Escolaridade do Pai":             "QE_ESC_PAI",         # média do curso, escala 1=Nunca estudou … 6=Pós-grad.
    "Familiar com Ens. Superior":      "QE_FAM_SUPERIOR",    # proporção do curso com familiar (0-1)
    "Situação de Trabalho":            "QE_TRABALHO",        # média do curso, escala 1=Não trabalha … 5=40h+
    "Ação Afirmativa":                 "QE_ACAO_AFIRM_BIN",  # proporção do curso com alguma cota (0-1)
    # Acadêmicas
    "Horas de Estudo por Semana":      "QE_HORAS_ESTUDO",    # média do curso, escala 1=Nenhuma … 5=>12h
    "Tipo de Escola no EM":            "QE_TIPO_EM_BIN",     # proporção do curso vinda de escola privada (0-1)
    # Demográficas
    "Sexo":                            "TP_SEXO",            # proporção de alunos do curso do sexo masculino (0-1)
    # Institucionais — binárias e dummies de CO_TURNO (ref=Matutino)
    "Tipo de IES (Pública/Privada)":   "TP_CATEGAD_BIN",     # 0=Pública / 1=Privada (atributo do curso)
    "Turno: Vespertino (vs Matutino)": "CO_TURNO_V",         # proporção do curso no turno vespertino (0-1)
    "Turno: Noturno (vs Matutino)":    "CO_TURNO_N",         # proporção do curso no turno noturno (0-1)
    "Turno: Integral (vs Matutino)":   "CO_TURNO_I",         # proporção do curso no turno integral (0-1)
}

CODE_TO_UI_LABEL = {v: k for k, v in X_OPTS.items()}
CODE_TO_UI_LABEL.update({v: k for k, v in Y_OPTS.items()})

# Cursos do recorte fixo do TCC (dados via Supabase: CC + SI, Brasil inteiro, agregado por curso)
CURSO_OPTS = {
    "Todos (CC + SI)":          None,
    "Ciência da Computação":    [4004],
    "Sistemas de Informação":   [4006],
}
# Filtra por TP_CATEGAD_BIN (0=Pública, 1=Privada) — já derivado na base agregada
IES_OPTS = {"Todas": None, "Pública": [0], "Privada": [1]}

X_CATEGORIAS = {
    "Socioeconômicas": {
        "pill": "pill-blue",
        "vars": [
            "Renda Familiar", "Escolaridade da Mãe", "Escolaridade do Pai",
            "Familiar com Ens. Superior", "Situação de Trabalho", "Ação Afirmativa",
        ],
    },
    "Acadêmicas": {
        "pill": "pill-green",
        "vars": ["Horas de Estudo por Semana", "Tipo de Escola no EM"],
    },
    "Demográficas": {
        "pill": "pill-fuchsia",
        "vars": ["Sexo"],
    },
    "Institucionais": {
        "pill": "pill-amber",
        "vars": [
            "Tipo de IES (Pública/Privada)",
            "Turno: Vespertino (vs Matutino)",
            "Turno: Noturno (vs Matutino)",
            "Turno: Integral (vs Matutino)",
        ],
    },
}
