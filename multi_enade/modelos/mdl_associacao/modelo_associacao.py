from mlxtend.frequent_patterns import apriori, association_rules
from util.util_db import consultar_dados, credenciais_banco, upsert_supabase, truncar_tabela_supabase
from util.util_general import calcular_tempo
from pandas import DataFrame
import pandas as pd
import warnings
import os

warnings.filterwarnings("ignore", category=DeprecationWarning, module="supabase")

# Com os limiares validados (suporte 0,03/confiança 0,5) a base de ~6
# itens + desempenho gera milhares de regras (muitas delas permutações do
# mesmo padrão) — inviável publicar direto (a tabela tinha 7 linhas antes).
# Mantém só regras simples (no máx. 3 itens no total) e as melhores por lift.
MAX_ITENS_POR_REGRA = 3
LIMITE_REGRAS_PUBLICADAS = 50

# Itens Likert diversos (1 por tema, em vez dos 3 originais do mesmo
# microtema "satisfação com professores") — ver
# multi_enade/EXPLORACAO_MODELO_ASSOCIACAO.md para a validação completa.
ITENS_ASSOCIACAO = {
    'QE_I57': 'professores_dominio',    # professores/didática
    'QE_I61': 'infra_salas',            # infraestrutura
    'QE_I34': 'formacao_critica',       # formação/currículo
    'QE_I44': 'oportunidades_ic',       # oportunidades extracurriculares (iniciação científica)
    'QE_I30': 'metodologia_inovadora',  # já usado no modelo original
    'QE_I56': 'profs_disponibilidade',  # já usado no modelo original
}


def _filtrar_likert(df: DataFrame, coluna: str) -> pd.Series:
    """Escala de concordância 1-6 (6=Concordo totalmente, resposta legítima);
    só 7 (Não sei responder) e 8 (Não se aplica) quebram a ordinalidade."""
    s = pd.to_numeric(df[coluna], errors='coerce')
    return s.where(~s.isin([7, 8]))


def montar_banda_desempenho(df_arq3: DataFrame) -> pd.Series:
    """Tercis de NT_GER médio por curso — anexado a cada aluno via CO_CURSO
    (válido e compatível com LGPD: é uma característica do curso, não um
    vínculo entre alunos de arquivos diferentes)."""
    df = df_arq3[['CO_CURSO', 'NT_GER']].copy()
    df['NT_GER'] = pd.to_numeric(df['NT_GER'], errors='coerce')
    df = df[(df['NT_GER'].notna()) & (df['NT_GER'] > 0)]
    media_por_curso = df.groupby('CO_CURSO')['NT_GER'].mean()
    media_por_curso.index = media_por_curso.index.astype(str)
    return pd.qcut(media_por_curso, q=3, labels=['desempenho_baixo', 'desempenho_medio', 'desempenho_alto'])


def preparar_dados_associacao(df_arq4: DataFrame, df_arq3: DataFrame, suporte_minimo: float = 0.03,
                              confianca_minima: float = 0.5) -> pd.DataFrame:
    try:
        nomes_itens = list(ITENS_ASSOCIACAO.values())

        base = df_arq4[['CO_CURSO']].copy()
        base['CO_CURSO'] = base['CO_CURSO'].astype(str)
        for coluna, nome in ITENS_ASSOCIACAO.items():
            base[nome] = _filtrar_likert(df_arq4, coluna)

        base = base.dropna(subset=nomes_itens).copy()
        base[nomes_itens] = base[nomes_itens].astype(int)

        # Banda de desempenho do curso, anexada por CO_CURSO
        banda = montar_banda_desempenho(df_arq3)
        base['desempenho'] = base['CO_CURSO'].map(banda)
        base = base.dropna(subset=['desempenho'])

        df_binario = pd.get_dummies(base, columns=nomes_itens + ['desempenho'], dtype=bool).drop(columns=['CO_CURSO'])

        itemsets_frequentes = apriori(df_binario, min_support=suporte_minimo, use_colnames=True)

        if itemsets_frequentes.empty:
            print("Nenhum padrão frequente encontrado com o suporte mínimo definido.")
            return pd.DataFrame()
        regras = association_rules(itemsets_frequentes, metric="confidence", min_threshold=confianca_minima)
        regras = regras.sort_values(by="lift", ascending=False).reset_index(drop=True)
        print("Tratamento de dados realizado com sucesso.")
        return regras
    except Exception as e:
        print(f"Erro na funcao (preparar_dados_associacao): {e}")
        raise e

@calcular_tempo
def multi_enade_modelo_associacao(url_conexao, key_conexao, suporte_minimo: float = 0.03,
                                  confianca_minima: float = 0.5, print_flag=False):
    try:
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        dataf_arq4 = consultar_dados("tbl_arq4_2021", url_conexao, key_conexao)
        dataf_arq3 = consultar_dados("tbl_arq3_2021", url_conexao, key_conexao)

        regras_gerais = preparar_dados_associacao(dataf_arq4, dataf_arq3, suporte_minimo, confianca_minima)
        if regras_gerais.empty:
            print("Nenhuma regra encontrada — nada a persistir.")
            return

        # Mantém só regras simples e interpretáveis, as melhores por lift
        tamanho_regra = regras_gerais['antecedents'].apply(len) + regras_gerais['consequents'].apply(len)
        regras_simples = regras_gerais[tamanho_regra <= MAX_ITENS_POR_REGRA]
        print(f"[INFO] {len(regras_gerais)} regras encontradas -> {len(regras_simples)} simples (<={MAX_ITENS_POR_REGRA} itens)")

        regras_ordenadas = regras_simples.sort_values(
            by=["lift", "confidence"],
            ascending=[False, False]
        ).head(LIMITE_REGRAS_PUBLICADAS).reset_index(drop=True)
        print(f"[INFO] Publicando as {len(regras_ordenadas)} melhores por lift.")
        caminho_arq_csv1 = os.path.join(diretorio_atual, 'dados_associacao_binario.csv')
        regras_ordenadas.to_csv(caminho_arq_csv1, index=False)

        # Ajustes 2 e 3: Tratamento de tela para extrair o frozenset e aplicar porcentagem
        regras_formatadas = regras_ordenadas[['antecedents', 'consequents', 'support', 'confidence', 'lift']].copy()
        # Extrai o texto limpo unindo os itens do conjunto
        regras_formatadas['antecedents'] = regras_formatadas['antecedents'].apply(lambda x: ', '.join(sorted(x)))
        regras_formatadas['consequents'] = regras_formatadas['consequents'].apply(lambda x: ', '.join(sorted(x)))
        # Formata como porcentagem e o lift com 3 casas decimais
        regras_formatadas['support'] = (regras_formatadas['support'] * 100).map("{:.2f}".format)
        regras_formatadas['confidence'] = (regras_formatadas['confidence'] * 100).map("{:.2f}".format)
        regras_formatadas['lift'] = regras_formatadas['lift'].map("{:.3f}".format)

        caminho_arq_csv2 = os.path.join(diretorio_atual, "dados_associacao_resultado.csv")
        regras_formatadas.to_csv(caminho_arq_csv2, index=False)

        truncar_tabela_supabase("tbl_multi_enade_associacao", url_conexao, key_conexao)
        upsert_supabase(regras_formatadas, "tbl_multi_enade_associacao", url_conexao, key_conexao)

        print(regras_formatadas) if print_flag else None
    except Exception as e:
        print(f"Erro na funcao (multi_enade_modelo_associacao): {e}")
        raise e


if __name__ == "__main__":
    dic_credenciais = credenciais_banco()
    multi_enade_modelo_associacao(dic_credenciais["url_banco"], dic_credenciais["key_banco"], 0.03, 0.5)
