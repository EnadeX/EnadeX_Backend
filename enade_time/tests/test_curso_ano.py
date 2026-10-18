"""
`v_enade_time_curso_ano` é o contrato com o E-XplainENADE (D15): uma linha por curso e ano,
com os nomes de coluna do `load_raw()` dele. Pulado sem o Postgres local.
"""

from __future__ import annotations

COLUNAS_DO_CONTRATO = [
    "NU_ANO", "CO_CURSO", "NT_GER", "NT_FG", "NT_CE", "QT_ALUNOS", "CO_GRUPO", "CO_REGIAO", "TP_CATEGAD_BIN",
]


def test_tem_as_colunas_do_load_raw_com_os_mesmos_nomes(cur):
    cur.execute('SELECT * FROM v_enade_time_curso_ano LIMIT 1')
    assert list(cur.fetchone().keys()) == COLUNAS_DO_CONTRATO


def test_uma_linha_por_curso_e_ano_582(cur):
    cur.execute('SELECT count(*) AS n, count(DISTINCT ("NU_ANO", "CO_CURSO")) AS pares FROM v_enade_time_curso_ano')
    linha = cur.fetchone()
    assert linha["n"] == linha["pares"] == 582


def test_qt_alunos_soma_as_24967_inscricoes(cur):
    cur.execute('SELECT sum("QT_ALUNOS")::int AS total FROM v_enade_time_curso_ano')
    assert cur.fetchone()["total"] == 24_967


def test_as_colunas_da_fato_sao_constantes_dentro_do_curso_ano(cur):
    # a view usa MIN() para escolher o valor do grupo; só é correto se ele for único
    cur.execute("""
        SELECT count(*) AS n FROM (
            SELECT nu_ano, co_curso FROM tbl_enade_time_fato GROUP BY 1, 2
            HAVING count(DISTINCT media_nt_ger) > 1 OR count(DISTINCT media_nt_fg) > 1
                OR count(DISTINCT media_nt_ce) > 1 OR count(DISTINCT co_grupo) > 1
                OR count(DISTINCT co_regiao_curso) > 1 OR count(DISTINCT co_categad) > 1
        ) x
    """)
    assert cur.fetchone()["n"] == 0


def test_categoria_binaria_replica_o_map_do_e_xplainenade(cur):
    # públicas (1, 2, 3) = 0; privadas (4, 5) = 1; "Especial" (7) = NULL
    cur.execute("""
        SELECT f.co_categad AS categoria, v."TP_CATEGAD_BIN" AS bin
        FROM v_enade_time_curso_ano v
        JOIN (SELECT DISTINCT nu_ano, co_curso, co_categad FROM tbl_enade_time_fato) f
          ON f.nu_ano = v."NU_ANO" AND f.co_curso = v."CO_CURSO"
    """)
    esperado = {1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 7: None}
    for r in cur.fetchall():
        assert r["bin"] == esperado[r["categoria"]], r
