import matplotlib
matplotlib.use("Agg")  # backend não-interativo: roda em servidor/API sem travar em plt.show() (sem display)

from util.util_db import consultar_dados, credenciais_banco, upsert_supabase, truncar_tabela_supabase
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestRegressor
from util.util_general import calcular_tempo
from util.util_pandas import show_df, avaliar_modelo_regressao
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
from pandas import DataFrame
import seaborn as sns
import pandas as pd
import numpy as np
import warnings
import joblib
import shap
import os

# Silencia os avisos internos do Supabase
warnings.filterwarnings("ignore", category=DeprecationWarning, module="supabase")

# Cursos com poucos respondentes geram médias instáveis (ex: 1 aluno = média
# igual à nota dele). Mesmo princípio do educluster (N_MINIMO_RESPONDENTES),
# com um piso mais permissivo já que o recorte regional (Norte+Nordeste)
# reduz bastante a base disponível.
N_MINIMO_ALUNOS = 5

# Variáveis selecionadas na revisão de lógica de negócio (ver
# multi_enade/EXPLORACAO_MODELO_REGRESSAO.md) — as 15 melhores encontradas
# na exploração, todas já com tabela própria no Supabase.
_MAPA_QE_I08 = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6}  # renda familiar
_MAPA_QE_I04 = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5}  # escolaridade do pai
_MAPA_QE_I10 = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}  # intensidade de trabalho
_MAPA_QE_I09 = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5}  # situação financeira

# Colunas finais exatas validadas na seleção (mantém só o que foi testado,
# em vez de todas as categorias de cada dummy). QE_I08/QE_I09/QE_I10 (renda,
# situação financeira, trabalho) não entram mais cada uma separada — são
# condensadas em PCA_ECON_1/2 (ver preparar_dados_regressao). Testado em
# multi_enade/EXPLORACAO_MODELO_REGRESSAO.md: ganho real de CV (0,400 -> 0,424)
# por serem 3 variáveis ordinais da mesma escala e já individualmente fortes.
COLUNAS_FEATURES = [
    'QE_I57', 'QE_I15_C', 'QE_I15_E', 'QE_I04_media', 'CO_TURNO_GRADUACAO_4',
    'QE_I13_A', 'QE_I13_B', 'QE_I13_D', 'QE_I24_A', 'QE_I12_A', 'QE_I11_A',
    'QE_I19_B', 'PCA_ECON_1', 'PCA_ECON_2',
]


def _media_ordinal(df: DataFrame, coluna: str, mapa: dict, nome_saida: str) -> DataFrame:
    df_limpo = df[['CO_CURSO', coluna]].dropna().copy()
    # Algumas tabelas têm CO_CURSO como bigint, outras como text — normaliza
    # pra string antes de qualquer merge, senão o pandas recusa o merge.
    df_limpo['CO_CURSO'] = df_limpo['CO_CURSO'].astype(str)
    df_limpo[nome_saida] = df_limpo[coluna].astype(str).str.strip().str.upper().map(mapa)
    return df_limpo.dropna(subset=[nome_saida]).groupby('CO_CURSO')[nome_saida].mean().reset_index()


def _proporcao_nominal(df: DataFrame, coluna: str) -> DataFrame:
    df_limpo = df[['CO_CURSO', coluna]].dropna().copy()
    df_limpo['CO_CURSO'] = df_limpo['CO_CURSO'].astype(str)
    df_limpo[coluna] = df_limpo[coluna].astype(str).str.strip().str.upper()
    dummies = pd.get_dummies(df_limpo, columns=[coluna], dtype=int)
    return dummies.groupby('CO_CURSO').mean().reset_index()


def preparar_dados_regressao(
    df_arq3: DataFrame, df_arq4: DataFrame, df_arq21: DataFrame,
    df_arq2: DataFrame, df_arq10: DataFrame, df_arq14: DataFrame, df_arq16: DataFrame,
    df_arq15: DataFrame, df_arq17: DataFrame, df_arq18: DataFrame,
    df_arq19: DataFrame, df_arq25: DataFrame, df_arq30: DataFrame,
    print_flag=False,
) -> DataFrame:
    """
    Trata as bases de dados realizando o mapeamento de variáveis ordinais,
    limpeza de ruídos (ausências/zeros) e agregando-as por média/proporção a
    nível de curso (CO_CURSO).
    """
    # 1. ========== Arquivo 3 (Notas de Desempenho) — alvo ==========
    df_arq3_limpo = df_arq3[['CO_CURSO', 'NT_GER']].copy()
    df_arq3_limpo['NT_GER'] = pd.to_numeric(df_arq3_limpo['NT_GER'], errors='coerce')
    df_arq3_limpo = df_arq3_limpo[(df_arq3_limpo['NT_GER'].notna()) & (df_arq3_limpo['NT_GER'] > 0)]
    df_arq3_agg = df_arq3_limpo.groupby('CO_CURSO').agg(
        NT_GER=('NT_GER', 'mean'),
        QT_ALUNOS=('NT_GER', 'count')  # âncora de peso
    ).reset_index()

    # 2. ========== Arquivo 4 (QE_I57 — professores dominam o conteúdo) ==========
    df_arq4_limpo = df_arq4[['CO_CURSO', 'QE_I57']].copy()
    df_arq4_limpo['QE_I57'] = pd.to_numeric(df_arq4_limpo['QE_I57'], errors='coerce')
    # Escala de concordância 1-6 (6=Concordo totalmente — ver dicionário do
    # INEP). Remove só 7 (Não sei responder) e 8 (Não se aplica).
    df_arq4_limpo = df_arq4_limpo[~df_arq4_limpo['QE_I57'].isin([7, 8])]
    df_arq4_agg = df_arq4_limpo.dropna().groupby('CO_CURSO')['QE_I57'].mean().reset_index()

    # 3. ========== Arquivo 21 (QE_I15 — ações afirmativas/cotas) ==========
    df_arq21_limpo = df_arq21[['CO_CURSO', 'QE_I15']].dropna().copy()
    df_arq21_limpo['QE_I15'] = df_arq21_limpo['QE_I15'].astype(str).str.strip().str.upper()
    df_arq21_dummies = pd.get_dummies(df_arq21_limpo, columns=['QE_I15'], dtype=int)
    df_arq21_agg = df_arq21_dummies.groupby('CO_CURSO').mean().reset_index()

    # 4. ========== Arquivo 2 (turno de graduação) ==========
    df_arq2_limpo = df_arq2[['CO_CURSO', 'CO_TURNO_GRADUACAO']].dropna().copy()
    df_arq2_dummies = pd.get_dummies(df_arq2_limpo, columns=['CO_TURNO_GRADUACAO'], dtype=int)
    df_arq2_agg = df_arq2_dummies.groupby('CO_CURSO').mean().reset_index()

    # 5-7. ========== Ordinais: renda (arq14), escolaridade do pai (arq10), trabalho (arq16) ==========
    df_arq14_agg = _media_ordinal(df_arq14, 'QE_I08', _MAPA_QE_I08, 'QE_I08_media')
    df_arq10_agg = _media_ordinal(df_arq10, 'QE_I04', _MAPA_QE_I04, 'QE_I04_media')
    df_arq16_agg = _media_ordinal(df_arq16, 'QE_I10', _MAPA_QE_I10, 'QE_I10_media')

    # 8. ========== Situação financeira (arq15, ordinal) ==========
    df_arq15_agg = _media_ordinal(df_arq15, 'QE_I09', _MAPA_QE_I09, 'QE_I09_media')

    # 9-12. ========== Nominais: bolsa acadêmica (arq19), idioma (arq30),
    # auxílio permanência (arq18), bolsa/financiamento (arq17), incentivo (arq25) ==========
    df_arq19_agg = _proporcao_nominal(df_arq19, 'QE_I13')
    df_arq30_agg = _proporcao_nominal(df_arq30, 'QE_I24')
    df_arq18_agg = _proporcao_nominal(df_arq18, 'QE_I12')
    df_arq17_agg = _proporcao_nominal(df_arq17, 'QE_I11')
    df_arq25_agg = _proporcao_nominal(df_arq25, 'QE_I19')

    # 13. InnerJoin dos Dataframes
    df_consolidado = df_arq3_agg.merge(df_arq4_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq21_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq2_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq14_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq10_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq16_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq15_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq19_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq30_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq18_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq17_agg, on='CO_CURSO', how='inner')
    df_consolidado = df_consolidado.merge(df_arq25_agg, on='CO_CURSO', how='inner')

    # 14. Piso mínimo de respondentes: cursos com poucos alunos geram médias
    # instáveis e não devem ter o mesmo peso visual que cursos bem amostrados.
    # Aplicado antes do PCA pra ele refletir exatamente a população modelada.
    total_antes = len(df_consolidado)
    df_consolidado = df_consolidado[df_consolidado['QT_ALUNOS'] >= N_MINIMO_ALUNOS].reset_index(drop=True)
    print(f"[INFO] Piso de {N_MINIMO_ALUNOS} alunos/curso: {total_antes} -> {len(df_consolidado)} cursos.")

    # 15. PCA das 3 variáveis econômicas (renda, situação financeira,
    # trabalho) em 2 componentes — testado em EXPLORACAO_MODELO_REGRESSAO.md:
    # ganho real de CV sobre usá-las separadas (0,400 -> 0,424), porque são
    # ordinais da mesma escala e cada uma já tinha sinal individual forte
    # (diferente de outros grupos testados — bolsas/auxílios e percepção de
    # ensino — que não melhoraram). Recalculado a cada reprocessamento (não
    # é "treinado" e salvo como o RandomForest): são só 3 variáveis estáveis,
    # sem necessidade de persistir o ajuste do PCA entre execuções.
    colunas_economicas = ['QE_I08_media', 'QE_I09_media', 'QE_I10_media']
    scaler_economico = StandardScaler()
    bloco_padronizado = scaler_economico.fit_transform(df_consolidado[colunas_economicas])
    pca_economico = PCA(n_components=2, random_state=42)
    componentes_economicos = pca_economico.fit_transform(bloco_padronizado)
    df_consolidado['PCA_ECON_1'] = componentes_economicos[:, 0]
    df_consolidado['PCA_ECON_2'] = componentes_economicos[:, 1]

    # Garante que todas as colunas selecionadas existem (uma categoria rara
    # pode não aparecer em algum recorte/reprocessamento)
    for coluna in COLUNAS_FEATURES:
        if coluna not in df_consolidado.columns:
            df_consolidado[coluna] = 0.0

    df_consolidado = df_consolidado[['CO_CURSO', 'NT_GER', 'QT_ALUNOS'] + COLUNAS_FEATURES]

    show_df(df_consolidado) if print_flag else None
    return df_consolidado


def _criar_random_forest() -> RandomForestRegressor:
    # min_samples_leaf=2 (antes 4) — validado em exploracao_modelos.py via
    # GridSearchCV + 5-fold CV como o melhor valor pra este problema.
    return RandomForestRegressor(
        n_estimators=200,
        max_depth=5,
        min_samples_split=10,
        min_samples_leaf=2,
        random_state=42
    )


def treinar_e_salvar_modelo(df_consolidado: DataFrame, fatia_treino: float = 0.2,
                            caminho_modelo: str = 'rf_regressor.joblib'):
    """
    Treina em duas etapas:
    1. Avalia honestamente num conjunto de teste nunca visto (held-out) —
       gera R²/MAE/RMSE que refletem a capacidade real de generalização.
    2. Reajusta o modelo final com 100% dos dados (prática padrão: depois de
       medir a qualidade, usa-se toda a base disponível no modelo publicado).
       Isso evita publicar previsões que misturam cursos "vistos no treino"
       (parcialmente memorizados) com cursos genuinamente fora da amostra.
    Salva (serializa) o modelo final no disco e retorna (modelo, métricas).
    """
    x = df_consolidado.drop(columns=['CO_CURSO', 'NT_GER', 'QT_ALUNOS'])
    y = df_consolidado['NT_GER']
    pesos = df_consolidado['QT_ALUNOS']

    X_train, X_test, y_train, y_test, pesos_train, pesos_test = train_test_split(
        x, y, pesos, test_size=fatia_treino, random_state=42
    )

    # 1. Avaliação honesta no conjunto de teste
    modelo_avaliacao = _criar_random_forest()
    modelo_avaliacao.fit(X_train, y_train, sample_weight=pesos_train)
    y_previsto_teste = modelo_avaliacao.predict(X_test)
    metricas = avaliar_modelo_regressao(y_test, y_previsto_teste, modelo_avaliacao, x.columns)
    metricas['n_treino'] = len(X_train)
    metricas['n_teste'] = len(X_test)

    # 2. Modelo final, reajustado com toda a base
    rf_model = _criar_random_forest()
    rf_model.fit(x, y, sample_weight=pesos)

    # Cria a pasta caso ela não exista e salva o modelo
    os.makedirs(os.path.dirname(caminho_modelo), exist_ok=True)
    joblib.dump(rf_model, caminho_modelo)
    print(f"[INFO] Inteligência Artificial treinada e salva em: {caminho_modelo}")
    return rf_model, metricas


def aplicar_modelo(df_consolidado: DataFrame, caminho_modelo: str = 'modelos/rf_regressor.joblib', print_flag=False):
    """
    Carrega o modelo do disco e aplica aos dados para gerar a nova coluna de predições.
    """
    # Carrega a IA da memória do disco
    rf_model = joblib.load(caminho_modelo)

    x = df_consolidado.drop(columns=['CO_CURSO', 'NT_GER', 'QT_ALUNOS'])

    df_pos_treino = df_consolidado.copy()
    df_pos_treino['NT_GER_PREVISTA'] = rf_model.predict(x)

    show_df(df_pos_treino) if print_flag else None
    return rf_model, df_pos_treino


def preparar_dados_plotagem(df, variavel_destaque='professores'):
    df_plot = df.copy()
    # PCA_ECON_1 condensa renda + situação financeira + trabalho (ver
    # preparar_dados_regressao) — não é "renda" pura, mas é o eixo
    # socioeconômico mais próximo disponível pós-PCA.
    df_plot['indice_socioeconomico'] = df_plot['PCA_ECON_1']

    if variavel_destaque == 'professores':
        df_plot['categoria_legenda'] = np.where(df_plot['QE_I57'] >= 5.0, 'Concordância Alta', 'Concordância Baixa/Média')
        titulo_legenda = 'Professores dominam o conteúdo (QE_I57)'
        cores = {'Concordância Alta': '#023e8a', 'Concordância Baixa/Média': '#f77f00'}
    elif variavel_destaque == 'cotas':
        # QE_I15_A (ampla concorrência) não está entre as variáveis
        # selecionadas (ver COLUNAS_FEATURES) — só QE_I15_C (cota por renda)
        # e QE_I15_E (cota por múltiplos critérios) sobreviveram à seleção.
        # Corte pela mediana (não um limiar fixo de 0.5): a soma das duas
        # raramente passa de ~0.2-0.3 do curso, um corte em 0.5 nunca
        # separaria os grupos de verdade.
        colunas_cota = [c for c in ['QE_I15_C', 'QE_I15_E'] if c in df_plot.columns]
        if colunas_cota:
            proporcao_cota = df_plot[colunas_cota].sum(axis=1)
            mediana = proporcao_cota.median()
            df_plot['categoria_legenda'] = np.where(
                proporcao_cota >= mediana, 'Mais Cotistas (renda/múlt. critérios)', 'Menos Cotistas'
            )
        else:
            df_plot['categoria_legenda'] = 'Dado Indisponível'
        titulo_legenda = 'Perfil de Cotas — renda/múltiplos critérios (QE_I15)'
        cores = {'Mais Cotistas (renda/múlt. critérios)': '#e76f51', 'Menos Cotistas': '#2a9d8f', 'Dado Indisponível': '#cccccc'}
    else:
        raise ValueError("Senhor, o parâmetro deve ser 'professores' ou 'cotas'.")

    return df_plot, titulo_legenda, cores


def plotar_grafico_tradicional(df_plot, titulo_legenda, cores, nome_arquivo='regressao_desempenho.png'):
    fig, ax = plt.subplots(figsize=(10, 6.5))
    sns.scatterplot(data=df_plot, x='indice_socioeconomico', y='NT_GER', hue='categoria_legenda', palette=cores, alpha=0.85, s=70,
                    edgecolor='w', linewidth=0.5, ax=ax)
    sns.regplot(data=df_plot, x='indice_socioeconomico', y='NT_GER', scatter=False, color='#2b2d42',
                line_kws={'linewidth': 2.5, 'linestyle': '--'}, ax=ax)


    ax.set_xlabel('Índice Socioeconômico do Curso (PCA: renda + situação financeira + trabalho)', fontsize=11, fontweight='semibold',
                  labelpad=12)
    ax.set_ylabel('Nota Geral Média do Curso (NT_GER)', fontsize=11, fontweight='semibold', labelpad=12)

    handles, labels = ax.get_legend_handles_labels()
    handles.append(Line2D([0], [0], color='#2b2d42', linewidth=2.5, linestyle='--'))
    labels.append('Tendência Geral')

    ax.legend(handles=handles, labels=labels, title=titulo_legenda, title_fontsize='10', loc='upper left', frameon=True)
    # Sem xlim fixo: PCA_ECON_1 é um escore padronizado, sem faixa fixa como
    # a escala 0-6 original de QE_I08.
    ax.set_ylim(20, 80)
    sns.despine()
    plt.tight_layout()
    plt.savefig(nome_arquivo, dpi=150, bbox_inches='tight')
    print(f"[INFO] Gráfico clássico salvo como: {nome_arquivo}")
    plt.show()


def plotar_grafico_shap(modelo_treinado, df_dados, nome_arquivo='grafico_shap_explicabilidade.png'):
    print("[INFO] Calculando a matriz de explicabilidade SHAP... Aguarde um instante.")
    colunas_ignoradas = ['CO_CURSO', 'NT_GER', 'QT_ALUNOS', 'NT_GER_PREVISTA']
    X = df_dados.drop(columns=[col for col in colunas_ignoradas if col in df_dados.columns])

    explainer = shap.TreeExplainer(modelo_treinado)
    shap_values = explainer.shap_values(X)

    plt.figure(figsize=(10, 6.5))
    plt.title('Peso de Cada Fator na Nota do ENADE (NT_GER)', fontsize=14, fontweight='bold', pad=20)
    shap.summary_plot(shap_values, X, show=False)

    plt.tight_layout()
    plt.savefig(nome_arquivo, dpi=150, bbox_inches='tight')
    print(f"[INFO] Gráfico SHAP salvo como: {nome_arquivo}")
    plt.show()


def plotar_grafico_pca_geral(df_dados, nome_arquivo='grafico_pca_geral.png'):
    """
    Visão de todas as variáveis do modelo de uma vez, reduzidas a 2
    componentes (mesma técnica usada em modelo_clusters.py::
    plotar_grafico_clusters — padroniza tudo e projeta via PCA). Diferente
    do gráfico tradicional (que foca só na variável mais importante), este
    dá uma visão geral de como os cursos se distribuem no espaço das 14
    variáveis, coloridos pela nota real.
    """
    colunas_ignoradas = ['CO_CURSO', 'NT_GER', 'QT_ALUNOS', 'NT_GER_PREVISTA']
    features = df_dados.drop(columns=[col for col in colunas_ignoradas if col in df_dados.columns])

    scaler = StandardScaler()
    dados_padronizados = scaler.fit_transform(features)

    pca = PCA(n_components=2, random_state=42)
    dados_2d = pca.fit_transform(dados_padronizados)

    fig, ax = plt.subplots(figsize=(10, 7))
    dispersao = ax.scatter(
        dados_2d[:, 0], dados_2d[:, 1], c=df_dados['NT_GER'], cmap='viridis',
        s=70, alpha=0.85, edgecolor='w', linewidth=0.5,
    )
    barra_cor = fig.colorbar(dispersao, ax=ax)
    barra_cor.set_label('Nota Geral Média do Curso (NT_GER)', fontsize=10)

    ax.set_title('Visão Geral: todas as variáveis do modelo, reduzidas a 2 dimensões (PCA)',
                 fontsize=13, fontweight='bold', pad=15)
    ax.set_xlabel(f"Componente 1 (explica {pca.explained_variance_ratio_[0] * 100:.1f}% da variação)", fontsize=11)
    ax.set_ylabel(f"Componente 2 (explica {pca.explained_variance_ratio_[1] * 100:.1f}% da variação)", fontsize=11)
    sns.despine()
    plt.tight_layout()
    plt.savefig(nome_arquivo, dpi=150, bbox_inches='tight')
    print(f"[INFO] Gráfico de visão geral (PCA de todas as variáveis) salvo como: {nome_arquivo}")
    plt.show()

def calcular_e_salvar_shap(modelo_treinado, df_dados, url_conexao, key_conexao):
    """
    Calcula a importância média absoluta de cada feature via SHAP e persiste
    no Supabase, para consumo pela API/frontend. Complementa (não substitui)
    plotar_grafico_shap, que continua gerando o gráfico local.
    """
    colunas_ignoradas = ['CO_CURSO', 'NT_GER', 'QT_ALUNOS', 'NT_GER_PREVISTA']
    X = df_dados.drop(columns=[col for col in colunas_ignoradas if col in df_dados.columns])

    explainer = shap.TreeExplainer(modelo_treinado)
    shap_values = explainer.shap_values(X)

    importancia_media = np.abs(shap_values).mean(axis=0)
    df_shap = pd.DataFrame({
        'feature': X.columns,
        'importancia_media': importancia_media
    }).sort_values('importancia_media', ascending=False).reset_index(drop=True)

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    df_shap.to_csv(os.path.join(diretorio_atual, 'dados_shap_importancia.csv'), index=False)
    truncar_tabela_supabase("tbl_multi_enade_shap", url_conexao, key_conexao)
    upsert_supabase(df_shap, "tbl_multi_enade_shap", url_conexao, key_conexao)
    print("[INFO] Importância SHAP calculada e salva no Supabase.")
    return df_shap

@calcular_tempo
def multi_enade_modelo_regressao(url_conexao, key_conexao, flag_exe_treino=False):
    print("Extraindo dados do Supabase...")
    df_arq3 = consultar_dados("tbl_arq3_2021", url_conexao, key_conexao)
    df_arq4 = consultar_dados("tbl_arq4_2021", url_conexao, key_conexao)
    df_arq21 = consultar_dados("tbl_arq21_2021", url_conexao, key_conexao)
    df_arq2 = consultar_dados("tbl_arq2_2021", url_conexao, key_conexao)
    df_arq10 = consultar_dados("tbl_arq10_2021", url_conexao, key_conexao)
    df_arq14 = consultar_dados("tbl_arq14_2021", url_conexao, key_conexao)
    df_arq16 = consultar_dados("tbl_arq16_2021", url_conexao, key_conexao)
    df_arq15 = consultar_dados("tbl_arq15_2021", url_conexao, key_conexao)
    df_arq17 = consultar_dados("tbl_arq17_2021", url_conexao, key_conexao)
    df_arq18 = consultar_dados("tbl_arq18_2021", url_conexao, key_conexao)
    df_arq19 = consultar_dados("tbl_arq19_2021", url_conexao, key_conexao)
    df_arq25 = consultar_dados("tbl_arq25_2021", url_conexao, key_conexao)
    df_arq30 = consultar_dados("tbl_arq30_2021", url_conexao, key_conexao)

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_do_modelo = os.path.join(diretorio_atual, 'rf_regressor.joblib')

    print("Preparando e agregando a base...")
    df_preparado = preparar_dados_regressao(
        df_arq3, df_arq4, df_arq21, df_arq2, df_arq10, df_arq14, df_arq16,
        df_arq15, df_arq17, df_arq18, df_arq19, df_arq25, df_arq30,
    )
    df_preparado.to_csv(os.path.join(diretorio_atual, "dados_regressao_refinados.csv"), index=False)

    if flag_exe_treino:
        _, metricas = treinar_e_salvar_modelo(df_preparado, 0.2, caminho_do_modelo)
        print(f"[INFO] Qualidade do modelo (conjunto de teste, n={metricas['n_teste']}): "
              f"R²={metricas['R2']:.3f} | MAE={metricas['MAE']:.3f} | RMSE={metricas['RMSE']:.3f}")
        pd.DataFrame([metricas]).to_csv(os.path.join(diretorio_atual, "metricas_regressao.csv"), index=False)

    print("Iniciando o treinamento dos modelos...\n")
    modelo_treinado, df_pos_treino = aplicar_modelo(df_preparado, caminho_modelo=caminho_do_modelo)
    df_pos_treino.to_csv(os.path.join(diretorio_atual, "dados_regressao_pos_treino.csv"), index=False)

    truncar_tabela_supabase("tbl_multi_enade_regressao", url_conexao, key_conexao)
    upsert_supabase(df_pos_treino, "tbl_multi_enade_regressao", url_conexao, key_conexao)

    # Persiste o SHAP antes de plotar: os gráficos são um extra visual local e,
    # num ambiente headless (servidor/API), podem falhar — isso não pode custar
    # a gravação dos dados já calculados.
    calcular_e_salvar_shap(modelo_treinado, df_pos_treino, url_conexao, key_conexao)

    try:
        visao = 'cotas'
        df_pronto, titulo, paleta = preparar_dados_plotagem(df_pos_treino, variavel_destaque=visao)
        plotar_grafico_tradicional(df_pronto, titulo, paleta, nome_arquivo=os.path.join(diretorio_atual, f'grafico_enade_{visao}.png'))
        plotar_grafico_shap(modelo_treinado, df_pos_treino, nome_arquivo=os.path.join(diretorio_atual, 'grafico_shap_explicabilidade.png'))
        plotar_grafico_pca_geral(df_pos_treino, nome_arquivo=os.path.join(diretorio_atual, 'grafico_pca_geral.png'))
    except Exception as e:
        print(f"[AVISO] Falha ao gerar gráficos locais (dados já foram persistidos): {e}")

    print("\nPipeline de Regressão finalizado!")


if __name__ == "__main__":
    dic_credenciais = credenciais_banco()
    multi_enade_modelo_regressao(dic_credenciais["url_banco"], dic_credenciais["key_banco"])