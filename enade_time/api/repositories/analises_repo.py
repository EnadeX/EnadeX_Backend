from psycopg2.extensions import cursor as PgCursor

from enade_time.api.dependencies import FiltrosAnalise


def resumo_anual(cursor: PgCursor, filtros: FiltrosAnalise) -> list[dict]:
    where, params = filtros.to_where()
    cursor.execute(
        f"""
        SELECT
            nu_ano,
            COUNT(*)::int AS total_registros,
            COUNT(DISTINCT co_curso)::int AS total_cursos,
            AVG(media_nt_fg)::float AS media_geral,
            MIN(media_nt_fg)::float AS media_min,
            MAX(media_nt_fg)::float AS media_max,
            STDDEV(media_nt_fg)::float AS desvio_padrao,
            AVG(media_nt_ger)::float AS media_geral_ger,
            AVG(media_nt_ce)::float  AS media_geral_ce
        FROM tbl_enade_time_fato
        WHERE 1=1 {where}
        GROUP BY nu_ano
        ORDER BY nu_ano
        """,
        params,
    )
    return list(cursor.fetchall())


def resumo_regiao(cursor: PgCursor, filtros: FiltrosAnalise) -> list[dict]:
    where, params = filtros.to_where(alias="f")
    cursor.execute(
        f"""
        SELECT
            r.co_regiao,
            r.nome,
            COUNT(*)::int AS total_registros,
            COUNT(DISTINCT f.co_curso)::int AS total_cursos,
            AVG(f.media_nt_fg)::float AS media_geral,
            MIN(f.media_nt_fg)::float AS media_min,
            MAX(f.media_nt_fg)::float AS media_max,
            STDDEV(f.media_nt_fg)::float AS desvio_padrao,
            AVG(f.media_nt_ger)::float AS media_geral_ger,
            AVG(f.media_nt_ce)::float  AS media_geral_ce
        FROM tbl_enade_time_fato f
        JOIN tbl_enade_time_dim_regiao r ON f.co_regiao_curso = r.co_regiao
        WHERE 1=1 {where}
        GROUP BY r.co_regiao, r.nome
        ORDER BY r.co_regiao
        """,
        params,
    )
    return list(cursor.fetchall())


def resumo_uf(cursor: PgCursor, filtros: FiltrosAnalise) -> list[dict]:
    where, params = filtros.to_where(alias="f")
    cursor.execute(
        f"""
        SELECT
            u.co_uf,
            u.sigla,
            u.nome,
            u.co_regiao,
            COUNT(*)::int AS total_registros,
            COUNT(DISTINCT f.co_curso)::int AS total_cursos,
            AVG(f.media_nt_fg)::float AS media_geral,
            MIN(f.media_nt_fg)::float AS media_min,
            MAX(f.media_nt_fg)::float AS media_max,
            STDDEV(f.media_nt_fg)::float AS desvio_padrao,
            AVG(f.media_nt_ger)::float AS media_geral_ger,
            AVG(f.media_nt_ce)::float  AS media_geral_ce
        FROM tbl_enade_time_fato f
        JOIN tbl_enade_time_dim_uf u ON f.co_uf_curso = u.co_uf
        WHERE 1=1 {where}
        GROUP BY u.co_uf, u.sigla, u.nome, u.co_regiao
        ORDER BY u.co_regiao, u.sigla
        """,
        params,
    )
    return list(cursor.fetchall())


def resumo_ies(
    cursor: PgCursor,
    filtros: FiltrosAnalise,
    limit: int = 20,
    min_cursos: int = 1,
) -> list[dict]:
    where, params = filtros.to_where()
    params = {**params, "min_cursos": min_cursos, "limit": limit}
    cursor.execute(
        f"""
        SELECT
            co_ies,
            MIN(co_categad)::int AS co_categad,
            MIN(co_orgacad)::int AS co_orgacad,
            MIN(co_uf_curso)::int AS co_uf_curso,
            COUNT(*)::int AS total_registros,
            COUNT(DISTINCT co_curso)::int AS total_cursos,
            AVG(media_nt_fg)::float AS media_geral,
            AVG(media_nt_ger)::float AS media_geral_ger,
            AVG(media_nt_ce)::float  AS media_geral_ce
        FROM tbl_enade_time_fato
        WHERE 1=1 {where}
        GROUP BY co_ies
        HAVING COUNT(DISTINCT co_curso) >= %(min_cursos)s
        ORDER BY media_geral_ger DESC NULLS LAST, total_registros DESC
        LIMIT %(limit)s
        """,
        params,
    )
    return list(cursor.fetchall())


def contar_registros(cursor: PgCursor, filtros: FiltrosAnalise) -> int:
    where, params = filtros.to_where()
    cursor.execute(
        f"SELECT COUNT(*)::int AS total FROM tbl_enade_time_fato WHERE 1=1 {where}",
        params,
    )
    row = cursor.fetchone()
    return int(row["total"]) if row else 0


def listar_registros(
    cursor: PgCursor,
    filtros: FiltrosAnalise,
    limit: int,
    offset: int,
) -> list[dict]:
    where, params = filtros.to_where()
    params = {**params, "limit": limit, "offset": offset}
    cursor.execute(
        f"""
        SELECT
            id, nu_ano, co_curso, co_ies, co_categad, co_orgacad,
            co_grupo, co_modalidade, co_munic_curso,
            co_uf_curso, co_regiao_curso,
            media_nt_fg::float  AS media_nt_fg,
            media_nt_ger::float AS media_nt_ger,
            media_nt_ce::float  AS media_nt_ce
        FROM tbl_enade_time_fato
        WHERE 1=1 {where}
        ORDER BY id
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    return list(cursor.fetchall())
