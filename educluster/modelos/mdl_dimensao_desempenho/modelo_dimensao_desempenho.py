import os

import pandas as pd

from educluster.educluster_config import ORIGEM_PADRAO, DIMENSOES_ARQ4, N_MINIMO_RESPONDENTES, ROTULOS_DIMENSAO
from educluster.modelos.mdl_curso_percepcao.modelo_curso_percepcao import preparar_dados_curso_percepcao

DIRETORIO_MODELO = os.path.dirname(os.path.abspath(__file__))

DIMENSOES = list(DIMENSOES_ARQ4.keys())
ALVOS = ["NT_FG", "NT_CE"]
MINIMO_CURSOS_POR_AREA = 30


def preparar_dados_dimensao(origem: str = ORIGEM_PADRAO, n_minimo: int = N_MINIMO_RESPONDENTES) -> pd.DataFrame:
    return preparar_dados_curso_percepcao(origem, n_minimo)


def correlacionar_global(df_base: pd.DataFrame) -> pd.DataFrame:
    tabela = df_base[DIMENSOES + ALVOS].corr().loc[DIMENSOES, ALVOS].round(4)
    print("\n[educluster] CORRELACAO GLOBAL entre dimensoes percebidas e desempenho")
    print(tabela.to_string())
    return tabela


def correlacionar_por_area(df_base: pd.DataFrame, alvo: str = "NT_CE") -> pd.DataFrame:
    linhas = []
    for area, grupo in df_base.groupby("area"):
        if len(grupo) < MINIMO_CURSOS_POR_AREA:
            continue
        registro = {"area": area, "cursos": len(grupo)}
        for dimensao in DIMENSOES:
            registro[dimensao] = round(float(grupo[dimensao].corr(grupo[alvo])), 4)
        vencedora = max(DIMENSOES, key=lambda d: abs(registro[d]))
        registro["dimensao_dominante"] = vencedora
        registro["correlacao_dominante"] = registro[vencedora]
        linhas.append(registro)

    tabela = pd.DataFrame(linhas).sort_values("correlacao_dominante", ascending=False)
    print(f"\n[educluster] CORRELACAO POR AREA com {alvo} ({len(tabela)} areas com {MINIMO_CURSOS_POR_AREA}+ cursos)")
    print(tabela.to_string(index=False))
    return tabela


def ranquear_dimensoes(tabela_areas: pd.DataFrame) -> dict:
    vitorias = tabela_areas["dimensao_dominante"].value_counts().to_dict()
    medias = {d: round(float(tabela_areas[d].mean()), 4) for d in DIMENSOES}
    positivas = {d: int((tabela_areas[d] > 0).sum()) for d in DIMENSOES}

    resultado = {
        "areas_avaliadas": int(len(tabela_areas)),
        "vitorias_por_dimensao": vitorias,
        "correlacao_media_entre_areas": medias,
        "areas_com_correlacao_positiva": positivas,
        "rotulos": ROTULOS_DIMENSAO,
    }

    print("\n[educluster] RANKING DAS DIMENSOES")
    for dimensao in sorted(DIMENSOES, key=lambda d: -medias[d]):
        print(
            f"  {dimensao:<6} correlacao media {medias[dimensao]:+.4f} | "
            f"dominante em {vitorias.get(dimensao, 0)} areas | "
            f"positiva em {positivas[dimensao]} de {len(tabela_areas)}"
        )
    return resultado


def educluster_modelo_dimensao_desempenho(
    origem: str = ORIGEM_PADRAO,
    n_minimo: int = N_MINIMO_RESPONDENTES,
    alvo: str = "NT_CE",
) -> dict:
    print("[educluster] A8: qual dimensao percebida mais se associa ao desempenho")
    base = preparar_dados_dimensao(origem, n_minimo)

    global_ = correlacionar_global(base)
    por_area = correlacionar_por_area(base, alvo)
    ranking = ranquear_dimensoes(por_area)

    por_area.to_csv(os.path.join(DIRETORIO_MODELO, "correlacao_por_area.csv"), index=False)
    return {
        "correlacao_global": global_.reset_index().rename(columns={"index": "dimensao"}).to_dict(orient="records"),
        "por_area": por_area.to_dict(orient="records"),
        "ranking": ranking,
        "alvo": alvo,
    }


if __name__ == "__main__":
    educluster_modelo_dimensao_desempenho()
