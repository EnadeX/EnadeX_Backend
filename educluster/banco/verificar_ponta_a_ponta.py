import argparse
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from educluster.banco.carga_supabase import preparar_arq3, preparar_arq4, preparar_cursos
from educluster.educluster_config import (
    CAMINHO_ZIP_MICRODADOS,
    COLS_ARQ3_CURSO,
    COLS_ARQ4_CURSO,
    ATRIBUTOS_CURSO,
    SUPABASE_PAGINA,
    TABELA_CURSOS_SUPABASE,
    TABELAS_SUPABASE,
)
from educluster.educluster_dados import _cliente_supabase, carregar_arq3, carregar_arq4
from educluster.educluster_preparo import montar_base_curso
from educluster.modelos.mdl_calibracao_prova.modelo_calibracao_prova import (
    classificar_calibracao,
    medir_calibracao,
    perfilar_calibracao,
    preparar_dados_calibracao,
)
from educluster.modelos.mdl_comparacao_tradicional.modelo_comparacao_tradicional import (
    classificar_tradicional,
    comparar_particoes,
    encontrar_gemeos_divergentes,
    medir_informacao_perdida,
)
from educluster.modelos.mdl_curso_percepcao.modelo_curso_percepcao import (
    ARQ_KMEANS,
    ARQ_PCA,
    ARQ_SCALER,
    DIRETORIO_MODELO as DIR_A6,
    aplicar_clusters,
    avaliar_clusters,
    identificar_discrepantes,
    medir_estabilidade,
    treinar_e_salvar_clusters,
)
from educluster.modelos.mdl_dimensao_desempenho.modelo_dimensao_desempenho import (
    DIRETORIO_MODELO as DIR_A8,
    correlacionar_por_area,
    ranquear_dimensoes,
)
from educluster.modelos.mdl_perfil_desempenho import modelo_perfil_desempenho as a1
from educluster.modelos.mdl_situacao_discursiva.modelo_situacao_discursiva import (
    classificar_perfis_discursivos,
    medir_situacao,
    perfilar_situacao,
    preparar_dados_situacao,
)

RAIZ_MODELOS = Path(__file__).resolve().parent.parent / "modelos"
resultados = []


def checar(nome, condicao, detalhe=""):
    resultados.append((nome, bool(condicao)))
    print(f"  [{'OK' if condicao else 'FALHA'}] {nome}" + (f"  ({detalhe})" if detalhe else ""))


def iguais(a, b, tolerancia=1e-9):
    a, b = a.reset_index(drop=True), b.reset_index(drop=True)
    if a.shape != b.shape or list(a.columns) != list(b.columns):
        return False
    for coluna in a.columns:
        x, y = a[coluna], b[coluna]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv, yv = x.astype("float64").to_numpy(), y.astype("float64").to_numpy()
            if not np.allclose(xv, yv, atol=tolerancia, equal_nan=True):
                return False
        elif not x.astype("string").fillna("<NA>").equals(y.astype("string").fillna("<NA>")):
            return False
    return True


def baixar_com_id(tabela, colunas, chave="id"):
    cliente = _cliente_supabase()
    maior = cliente.table(tabela).select(chave).order(chave, desc=True).limit(1).execute().data[0][chave]
    menor = cliente.table(tabela).select(chave).order(chave).limit(1).execute().data[0][chave]
    faixas = [(i, min(i + SUPABASE_PAGINA - 1, maior)) for i in range(menor, maior + 1, SUPABASE_PAGINA)]
    projecao = ",".join(colunas)

    def faixa(intervalo):
        for tentativa in range(5):
            try:
                consulta = _cliente_supabase().table(tabela).select(projecao)
                return consulta.gte(chave, intervalo[0]).lte(chave, intervalo[1]).execute().data
            except Exception:
                if tentativa == 4:
                    raise
                time.sleep(2 ** tentativa)

    with ThreadPoolExecutor(8) as pool:
        partes = list(pool.map(faixa, faixas))
    return pd.DataFrame([r for p in partes for r in p]).sort_values(chave).reset_index(drop=True)


def parte_integridade(caminho_zip):
    print("\n1. INTEGRIDADE: Supabase contra o zip do INEP, linha a linha")
    origem = {
        TABELAS_SUPABASE[3]: (preparar_arq3(caminho_zip), ["id"] + COLS_ARQ3_CURSO, "id"),
        TABELAS_SUPABASE[4]: (preparar_arq4(caminho_zip), ["id"] + COLS_ARQ4_CURSO, "id"),
        TABELA_CURSOS_SUPABASE: (preparar_cursos(caminho_zip), ["CO_CURSO"] + ATRIBUTOS_CURSO, "CO_CURSO"),
    }
    for tabela, (zip_df, colunas, chave) in origem.items():
        banco = baixar_com_id(tabela, colunas, chave)
        zip_df = zip_df[colunas].sort_values(chave).reset_index(drop=True)
        checar(f"{tabela}: mesmo numero de linhas", len(banco) == len(zip_df), f"{len(banco)} no banco, {len(zip_df)} no zip")
        divergentes = [c for c in colunas if not iguais(banco[[c]], zip_df[[c]])]
        checar(f"{tabela}: todas as celulas identicas", not divergentes, f"colunas divergentes: {divergentes}" if divergentes else f"{len(colunas)} colunas")


def parte_a6(pasta_temp):
    print("\n2. A6, A7 e estabilidade: cursos por desempenho e percepcao")
    base = montar_base_curso(carregar_arq3(), carregar_arq4())
    ref = pd.read_csv(RAIZ_MODELOS / "mdl_curso_percepcao/dados_curso_percepcao.csv", index_col="CO_CURSO")
    checar("base de curso com 3.832 cursos e 316.232 estudantes", len(base) == 3832 and int(base["n_notas"].sum()) == 316232)
    checar("mesmos cursos da base aprovada", set(base.index) == set(ref.index))
    colunas = ["n_notas", "n_qe", "NT_FG", "NT_CE", "NT_OBJ_FG", "NT_DIS_FG", "NT_OBJ_CE", "NT_DIS_CE", "tx_presenca", "ODP", "OPORT", "INFRA"]
    checar("valores agregados iguais aos aprovados", iguais(base.loc[ref.index, colunas], ref[colunas]))

    res = aplicar_clusters(base)
    checar("100% dos cursos no mesmo cluster aprovado", (res.loc[ref.index, "Cluster_ID"] == ref["Cluster_ID"]).all())
    metricas = avaliar_clusters(res)
    checar("silhouette 0,2505, variancia 2D 0,7397, ARI 0,0536",
           (metricas["silhouette"], metricas["variancia_explicada_2d"], metricas["ari_contra_area"]) == (0.2505, 0.7397, 0.0536))

    treinar_e_salvar_clusters(base, None, str(pasta_temp))
    escolha_nova = pd.read_csv(pasta_temp / "escolha_de_k.csv")
    checar("retreino do zero reproduz a escolha de k", iguais(escolha_nova, pd.read_csv(DIR_A6 + "/escolha_de_k.csv"), 0.01))
    for arquivo, atributo in [(ARQ_KMEANS, "cluster_centers_"), (ARQ_PCA, "components_"), (ARQ_SCALER, "mean_")]:
        novo = getattr(joblib.load(pasta_temp / arquivo), atributo)
        versionado = getattr(joblib.load(Path(DIR_A6) / arquivo), atributo)
        checar(f"retreino reproduz {arquivo}", np.allclose(novo, versionado, atol=1e-9))

    estab = medir_estabilidade(base, 3, rodadas=20)
    checar("estabilidade k=3 com ARI medio 0,9780", estab["ari_medio"] == 0.978, f"{estab['ari_medio']}")

    disc = identificar_discrepantes(res, 1.0)
    quad = disc["quadrante"].value_counts().to_dict()
    esperado = {"reconhecimento_sem_entrega": 705, "entrega_sem_reconhecimento": 609, "coerente_alto": 229, "coerente_baixo": 187}
    checar("A7: 1.730 discrepantes nos quatro quadrantes aprovados", quad == esperado, str(quad))
    return base, res


def parte_a8_comparacao(base, res):
    print("\n3. A8 e comparacao com a analise tradicional")
    por_area = correlacionar_por_area(base, "NT_CE")
    checar("A8: correlacoes por area iguais as aprovadas", iguais(por_area, pd.read_csv(DIR_A8 + "/correlacao_por_area.csv"), 1e-4))
    ranking = ranquear_dimensoes(por_area)
    checar("A8: OPORT dominante em 11 areas, media +0,1222",
           ranking["vitorias_por_dimensao"].get("OPORT") == 11 and ranking["correlacao_media_entre_areas"]["OPORT"] == 0.1222)

    df = classificar_tradicional(res)
    comparacao = comparar_particoes(df)
    checar("comparacao: ARI 0,2686 e NMI 0,2958", (comparacao["ari"], comparacao["nmi"]) == (0.2686, 0.2958))
    informacao = medir_informacao_perdida(df)
    checar("comparacao: 4 componentes para 90% da variancia", informacao["componentes_para_90_porcento"] == 4)
    pares, total = encontrar_gemeos_divergentes(df, 0.5)
    ref_pares = pd.read_csv(RAIZ_MODELOS / "mdl_comparacao_tradicional/gemeos_divergentes.csv")
    checar("comparacao: 1.744 pares de gemeos divergentes", total == 1744, f"{total}")
    checar("comparacao: tabela de gemeos igual a aprovada", iguais(pares, ref_pares, 1e-6))


def parte_estudantes(pasta_temp):
    print("\n4. Analises no nivel do estudante (A1, A3, A4)")
    base = a1.preparar_dados_perfil_desempenho(espaco="objetivo_discursivo")
    checar("A1: 354.899 estudantes com as quatro notas", len(base) == 354899)
    a1.treinar_e_salvar_perfil(base, "objetivo_discursivo", None, str(pasta_temp))
    checar("A1: retreino reproduz a escolha de k",
           iguais(pd.read_csv(pasta_temp / "escolha_de_k_objetivo_discursivo.csv"),
                  pd.read_csv(RAIZ_MODELOS / "mdl_perfil_desempenho/escolha_de_k_objetivo_discursivo.csv"), 1e-4))
    centros_novos = joblib.load(pasta_temp / a1.ARQ_KMEANS).cluster_centers_
    centros_versionados = joblib.load(Path(a1.DIRETORIO_MODELO) / a1.ARQ_KMEANS).cluster_centers_
    checar("A1: retreino reproduz os centroides", np.allclose(centros_novos, centros_versionados, atol=1e-9))
    perfil = a1.perfilar_desempenho(a1.aplicar_perfil(base, "objetivo_discursivo"), "objetivo_discursivo").reset_index()
    checar("A1: perfis iguais aos aprovados", iguais(perfil, pd.read_csv(RAIZ_MODELOS / "mdl_perfil_desempenho/perfil_objetivo_discursivo.csv"), 1e-6))

    cal = classificar_calibracao(preparar_dados_calibracao())
    checar("A3: perfis de calibracao iguais aos aprovados",
           iguais(perfilar_calibracao(cal).reset_index(), pd.read_csv(RAIZ_MODELOS / "mdl_calibracao_prova/perfil_calibracao.csv"), 1e-6))
    m3 = medir_calibracao(cal)
    checar("A3: correlacao -0,1227 e 47,5% descalibrados", (m3["correlacao_dificuldade_desempenho"], round(m3["taxa_descalibrados"], 3)) == (-0.1227, 0.475))

    sit = classificar_perfis_discursivos(preparar_dados_situacao())
    checar("A4: perfis discursivos iguais aos aprovados",
           iguais(perfilar_situacao(sit).reset_index(), pd.read_csv(RAIZ_MODELOS / "mdl_situacao_discursiva/perfil_situacao_discursiva.csv"), 1e-6))
    m4 = medir_situacao(sit)
    checar("A4: abandono 19,5%, todas 6,0%, sabe mas nao escreve 16,3%",
           (round(m4["taxa_abandono_media"], 3), round(m4["abandonaram_todas"], 3), round(m4["sabe_mas_nao_escreve"], 3)) == (0.195, 0.06, 0.163))


def main():
    parser = argparse.ArgumentParser(description="Verificacao ponta a ponta do EduCluster contra os resultados aprovados")
    parser.add_argument("--zip", default=str(CAMINHO_ZIP_MICRODADOS))
    parser.add_argument("--sem-integridade", action="store_true")
    args = parser.parse_args()

    inicio = time.perf_counter()
    if not args.sem_integridade:
        parte_integridade(args.zip)
    with tempfile.TemporaryDirectory() as pasta:
        pasta_a6, pasta_a1 = Path(pasta) / "a6", Path(pasta) / "a1"
        pasta_a6.mkdir()
        pasta_a1.mkdir()
        base, res = parte_a6(pasta_a6)
        parte_a8_comparacao(base, res)
        parte_estudantes(pasta_a1)

    falhas = [nome for nome, ok in resultados if not ok]
    print(f"\nRESUMO: {len(resultados) - len(falhas)} de {len(resultados)} verificacoes OK em {time.perf_counter() - inicio:.0f}s")
    for nome in falhas:
        print(f"  FALHOU: {nome}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
