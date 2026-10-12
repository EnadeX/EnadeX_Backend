"""
Valida a carga no PostgreSQL.

Checagens:
  1. COUNT(*) em tbl_enade_time_fato == 24967
  2. SELECT DISTINCT nu_ano = {2005, 2008, 2011, 2014, 2017, 2021}
  3. MIN(media_nt_fg) >= 0 e MAX(media_nt_fg) <= 100 (quando não NULL)
  4. Integridade referencial (JOIN nas dims, sem órfãos)
  5. Lookup tables populadas
  6. Schema esperado nas colunas

Imprime BASE VALIDADA COM SUCESSO ou BASE TEM PROBLEMAS no final.
"""

from __future__ import annotations

import os
import sys

import psycopg2


DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname":   os.environ.get("POSTGRES_DB", "enade_db"),
    "user":     os.environ.get("POSTGRES_USER", "enade_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "enade_password"),
}

LINHAS_ESPERADAS = 24_967
ANOS_ESPERADOS = {2005, 2008, 2011, 2014, 2017, 2021}
CODIGOS_COMPUTACAO = {40, 4004}
REGIOES_ESPERADAS = {1, 2}

# Notas: as três colunas têm o mesmo padrão de preenchimento (média por curso).
NOTAS = ["media_nt_fg", "media_nt_ger", "media_nt_ce"]
NAO_NULOS_NOTA_ESPERADO = 24_775
NULOS_NOTA_ESPERADO = 192

problemas: list[str] = []


def secao(titulo: str) -> None:
    print("\n" + "-" * 80)
    print(titulo)
    print("-" * 80)


def check(condicao: bool, sucesso: str, falha: str) -> None:
    if condicao:
        print(f"  OK   {sucesso}")
    else:
        print(f"  FAIL {falha}")
        problemas.append(falha)


def main() -> int:
    print("=" * 80)
    print("VALIDAÇÃO DO BANCO ENADE-Time")
    print("=" * 80)
    print(f"Conectando em postgresql://{DB_CONFIG['user']}@"
          f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        print(f"\nERRO ao conectar: {e}", file=sys.stderr)
        return 1

    with conn, conn.cursor() as cur:
        # 1) contagem total
        secao("1) Contagem total em tbl_enade_time_fato")
        cur.execute("SELECT COUNT(*) FROM tbl_enade_time_fato;")
        total = cur.fetchone()[0]
        print(f"  COUNT(*) = {total}")
        check(total == LINHAS_ESPERADAS,
              f"COUNT(*) == {LINHAS_ESPERADAS}",
              f"COUNT(*) = {total}, esperado {LINHAS_ESPERADAS}")

        # 2) anos distintos
        secao("2) Anos distintos em tbl_enade_time_fato")
        cur.execute("SELECT DISTINCT nu_ano FROM tbl_enade_time_fato ORDER BY nu_ano;")
        anos = {row[0] for row in cur.fetchall()}
        print(f"  anos: {sorted(anos)}")
        check(anos == ANOS_ESPERADOS,
              f"anos == {sorted(ANOS_ESPERADOS)}",
              f"anos divergem do esperado {sorted(ANOS_ESPERADOS)}: "
              f"{sorted(anos)}")

        # 2b) linhas por ano
        cur.execute("""
            SELECT nu_ano, COUNT(*) FROM tbl_enade_time_fato
            GROUP BY nu_ano ORDER BY nu_ano;
        """)
        for ano, n in cur.fetchall():
            print(f"    {ano}: {n}")

        # 3) escala media_nt_fg
        secao("3) Escala de media_nt_fg")
        cur.execute("""
            SELECT MIN(media_nt_fg), MAX(media_nt_fg),
                   AVG(media_nt_fg), COUNT(media_nt_fg),
                   COUNT(*) - COUNT(media_nt_fg) AS nulas
            FROM tbl_enade_time_fato;
        """)
        mn, mx, mean, ncount, nnulas = cur.fetchone()
        print(f"  min={mn}  max={mx}  mean={mean}")
        print(f"  válidas: {ncount}  nulas: {nnulas} "
              f"({nnulas/total*100:.2f}%)")
        check(mn is None or mn >= 0,
              f"MIN(media_nt_fg) = {mn} >= 0",
              f"MIN(media_nt_fg) = {mn} < 0")
        check(mx is None or mx <= 100,
              f"MAX(media_nt_fg) = {mx} <= 100",
              f"MAX(media_nt_fg) = {mx} > 100")

        # 3b) as três notas: contagem de não nulos / nulos + escala
        secao("3b) Notas: media_nt_fg, media_nt_ger, media_nt_ce")
        for nota in NOTAS:
            cur.execute(f"""
                SELECT COUNT({nota}) AS nao_nulos,
                       COUNT(*) - COUNT({nota}) AS nulos,
                       MIN({nota}), MAX({nota})
                FROM tbl_enade_time_fato;
            """)
            nao_nulos, nulos, mn_n, mx_n = cur.fetchone()
            print(f"  {nota:<13} não_nulos={nao_nulos}  nulos={nulos}  "
                  f"min={mn_n}  max={mx_n}")
            check(nao_nulos == NAO_NULOS_NOTA_ESPERADO,
                  f"{nota}: {nao_nulos} não nulos == {NAO_NULOS_NOTA_ESPERADO}",
                  f"{nota}: {nao_nulos} não nulos (esperado {NAO_NULOS_NOTA_ESPERADO})")
            check(nulos == NULOS_NOTA_ESPERADO,
                  f"{nota}: {nulos} nulos == {NULOS_NOTA_ESPERADO}",
                  f"{nota}: {nulos} nulos (esperado {NULOS_NOTA_ESPERADO})")
            check(mn_n is None or mn_n >= 0,
                  f"{nota}: MIN = {mn_n} >= 0",
                  f"{nota}: MIN = {mn_n} < 0")
            check(mx_n is None or mx_n <= 100,
                  f"{nota}: MAX = {mx_n} <= 100",
                  f"{nota}: MAX = {mx_n} > 100")

        # 3c) coerência dos nulos: as linhas com media_nt_fg nula devem ser
        # exatamente as mesmas com media_nt_ger e media_nt_ce nulas.
        secao("3c) Coerência dos nulos entre as três notas")
        cur.execute("""
            SELECT
              SUM(CASE WHEN (media_nt_fg IS NULL) <> (media_nt_ger IS NULL)
                       THEN 1 ELSE 0 END) AS difere_ger,
              SUM(CASE WHEN (media_nt_fg IS NULL) <> (media_nt_ce IS NULL)
                       THEN 1 ELSE 0 END) AS difere_ce,
              COUNT(*) FILTER (WHERE media_nt_fg IS NULL
                                 AND media_nt_ger IS NULL
                                 AND media_nt_ce IS NULL) AS nulos_nas_tres
            FROM tbl_enade_time_fato;
        """)
        difere_ger, difere_ce, nulos_tres = cur.fetchone()
        difere_ger = int(difere_ger or 0)
        difere_ce = int(difere_ce or 0)
        print(f"  divergências fg/ger={difere_ger}  fg/ce={difere_ce}  "
              f"nulos nas três simultaneamente={nulos_tres}")
        check(difere_ger == 0,
              "nulos de media_nt_ger coincidem com media_nt_fg",
              f"{difere_ger} linhas com nulidade divergente fg/ger")
        check(difere_ce == 0,
              "nulos de media_nt_ce coincidem com media_nt_fg",
              f"{difere_ce} linhas com nulidade divergente fg/ce")
        check(nulos_tres == NULOS_NOTA_ESPERADO,
              f"{nulos_tres} linhas com as três notas nulas == {NULOS_NOTA_ESPERADO}",
              f"{nulos_tres} linhas com as três notas nulas (esperado {NULOS_NOTA_ESPERADO})")

        # 4) integridade referencial
        secao("4) Integridade referencial (JOIN com dims)")
        cur.execute("""
            SELECT
              SUM(CASE WHEN dr.co_regiao   IS NULL THEN 1 ELSE 0 END) AS orf_regiao,
              SUM(CASE WHEN du.co_uf       IS NULL THEN 1 ELSE 0 END) AS orf_uf,
              SUM(CASE WHEN dg.co_grupo    IS NULL THEN 1 ELSE 0 END) AS orf_grupo,
              SUM(CASE WHEN dc.co_categad  IS NULL THEN 1 ELSE 0 END) AS orf_categad,
              SUM(CASE WHEN doa.co_orgacad IS NULL THEN 1 ELSE 0 END) AS orf_orgacad,
              SUM(CASE WHEN da.co_ano      IS NULL THEN 1 ELSE 0 END) AS orf_ano,
              SUM(CASE WHEN f.co_modalidade IS NOT NULL
                       AND dm.co_modalidade IS NULL THEN 1 ELSE 0 END) AS orf_modalidade
            FROM tbl_enade_time_fato f
            LEFT JOIN tbl_enade_time_dim_regiao         dr  ON dr.co_regiao    = f.co_regiao_curso
            LEFT JOIN tbl_enade_time_dim_uf             du  ON du.co_uf        = f.co_uf_curso
            LEFT JOIN tbl_enade_time_dim_grupo          dg  ON dg.co_grupo     = f.co_grupo
            LEFT JOIN tbl_enade_time_dim_categoria_adm  dc  ON dc.co_categad   = f.co_categad
            LEFT JOIN tbl_enade_time_dim_organizacao_acad doa ON doa.co_orgacad = f.co_orgacad
            LEFT JOIN tbl_enade_time_dim_ano            da  ON da.co_ano       = f.nu_ano
            LEFT JOIN tbl_enade_time_dim_modalidade     dm  ON dm.co_modalidade = f.co_modalidade;
        """)
        orf = cur.fetchone()
        nomes = ["regiao", "uf", "grupo", "categad", "orgacad", "ano",
                 "modalidade"]
        for nome, n in zip(nomes, orf):
            n = int(n or 0)
            check(n == 0,
                  f"0 órfãos em {nome}",
                  f"{n} órfãos em {nome}")

        # 4b) regiões e grupos observados
        cur.execute("SELECT DISTINCT co_regiao_curso FROM tbl_enade_time_fato;")
        regs = {r[0] for r in cur.fetchall()}
        check(regs == REGIOES_ESPERADAS,
              f"co_regiao_curso == {sorted(REGIOES_ESPERADAS)}",
              f"co_regiao_curso = {sorted(regs)}")

        cur.execute("SELECT DISTINCT co_grupo FROM tbl_enade_time_fato;")
        grupos = {r[0] for r in cur.fetchall()}
        check(grupos == CODIGOS_COMPUTACAO,
              f"co_grupo == {sorted(CODIGOS_COMPUTACAO)}",
              f"co_grupo = {sorted(grupos)} (esperado {sorted(CODIGOS_COMPUTACAO)})")

        # 5) Lookup tables populadas
        secao("5) Lookup tables")
        esperado = {
            "tbl_enade_time_dim_regiao": 2,
            "tbl_enade_time_dim_uf": 16,
            "tbl_enade_time_dim_grupo": 2,
            "tbl_enade_time_dim_categoria_adm": 6,
            "tbl_enade_time_dim_organizacao_acad": 6,
            "tbl_enade_time_dim_modalidade": 2,
            "tbl_enade_time_dim_ano": 6,
        }
        for tbl, n_esp in esperado.items():
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            n = cur.fetchone()[0]
            check(n == n_esp,
                  f"{tbl}: {n} linhas",
                  f"{tbl}: {n} linhas (esperado {n_esp})")

        # 6) Schema das colunas
        secao("6) Schema esperado em tbl_enade_time_fato")
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'tbl_enade_time_fato'
            ORDER BY ordinal_position;
        """)
        cols = cur.fetchall()
        for c, t, nullable in cols:
            print(f"  {c:<18} {t:<22} nullable={nullable}")
        esperadas = {
            "id", "nu_ano", "co_curso", "co_ies", "co_categad",
            "co_orgacad", "co_grupo", "co_modalidade", "co_munic_curso",
            "co_uf_curso", "co_regiao_curso",
            "media_nt_fg", "media_nt_ger", "media_nt_ce",
        }
        encontradas = {c[0] for c in cols}
        check(esperadas.issubset(encontradas),
              f"todas as {len(esperadas)} colunas esperadas presentes",
              f"colunas faltando: {esperadas - encontradas}")

        # 7) Bonus: ranking IES rápido (sanity check de JOIN)
        secao("7) Sanity check — top 5 IES por média (2017)")
        cur.execute("""
            SELECT f.co_ies, dc.nome AS categoria,
                   ROUND(AVG(f.media_nt_fg)::numeric, 2) AS media,
                   COUNT(DISTINCT f.co_curso) AS qtd_cursos
            FROM tbl_enade_time_fato f
            JOIN tbl_enade_time_dim_categoria_adm dc ON dc.co_categad = f.co_categad
            WHERE f.nu_ano = 2017 AND f.media_nt_fg IS NOT NULL
            GROUP BY f.co_ies, dc.nome
            HAVING COUNT(*) >= 5
            ORDER BY media DESC LIMIT 5;
        """)
        for ies, cat, media, n in cur.fetchall():
            print(f"  IES={ies}  cat={cat}  média={media}  cursos={n}")

    conn.close()

    print("\n" + "=" * 80)
    if not problemas:
        print("BASE VALIDADA COM SUCESSO")
    else:
        print(f"BASE TEM PROBLEMAS ({len(problemas)}):")
        for p in problemas:
            print(f"  - {p}")
    print("=" * 80)

    return 0 if not problemas else 2


if __name__ == "__main__":
    sys.exit(main())
