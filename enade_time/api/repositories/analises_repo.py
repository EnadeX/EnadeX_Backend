from psycopg2.extensions import cursor as PgCursor

from enade_time.api.dependencies import FiltrosAnalise

# Notas da estatística por curso-ano: (chave na resposta, coluna da média na tabela fato).
# Nomes fixos do código (nunca vêm da requisição), por isso podem entrar no SQL por f-string.
NOTAS_CURSO_ANO = (
    ("nt_ger", "media_nt_ger"),
    ("nt_fg", "media_nt_fg"),
    ("nt_ce", "media_nt_ce"),
)
_MEDIDAS = ("n", "media", "desvio_padrao", "variancia", "coef_variacao", "minimo", "q1", "mediana", "q3", "maximo")


def _cte_curso_ano(where: str) -> str:
    """Reduz a fato (uma linha por inscrição) a uma linha por curso-ano.

    Cada linha da fato repete a média do curso (iguais em todo o par `nu_ano, co_curso`),
    então `MAX` apenas recupera esse valor único. Nota nula fica nula (o `MAX` ignora nulos).
    O cast para `float` é necessário porque `PERCENTILE_CONT` não aceita `numeric`.
    """
    colunas = ", ".join(f"MAX(f.{coluna})::float AS {chave}" for chave, coluna in NOTAS_CURSO_ANO)
    return f"""
        WITH curso_ano AS (
            SELECT
                f.nu_ano,
                f.co_curso,
                {colunas}
            FROM tbl_enade_time_fato f
            WHERE 1=1 {where}
            GROUP BY f.nu_ano, f.co_curso
        )"""


def _agregados_nota(chave: str) -> str:
    """Medidas descritivas de uma nota sobre os curso-ano (uma observação por curso-ano)."""
    return f"""
            COUNT({chave})::int AS {chave}_n,
            AVG({chave})::float AS {chave}_media,
            STDDEV_SAMP({chave})::float AS {chave}_desvio_padrao,
            VAR_SAMP({chave})::float AS {chave}_variancia,
            (100 * STDDEV_SAMP({chave}) / NULLIF(AVG({chave}), 0))::float AS {chave}_coef_variacao,
            MIN({chave})::float AS {chave}_minimo,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {chave})::float AS {chave}_q1,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {chave})::float AS {chave}_mediana,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {chave})::float AS {chave}_q3,
            MAX({chave})::float AS {chave}_maximo"""


def descritiva(cursor: PgCursor, filtros: FiltrosAnalise) -> list[dict]:
    """Estatística descritiva por edição, com o **curso-ano** como unidade de análise.

    Primeiro a fato é reduzida a um registro por (`nu_ano`, `co_curso`); depois cada edição
    é resumida com `AVG`, `STDDEV_SAMP`, `VAR_SAMP`, `MIN`, `MAX` e os quartis por
    `PERCENTILE_CONT` (interpolação linear), para NT_GER, NT_FG e NT_CE. Os filtros valem
    antes da redução, como nas demais rotas de análise.
    """
    where, params = filtros.to_where(alias="f")
    agregados = ",".join(_agregados_nota(chave) for chave, _ in NOTAS_CURSO_ANO)
    cursor.execute(
        f"""{_cte_curso_ano(where)}
        SELECT
            nu_ano,
            COUNT(*)::int AS cursos,{agregados}
        FROM curso_ano
        GROUP BY nu_ano
        ORDER BY nu_ano
        """,
        params,
    )
    return [_aninhar_descritiva(linha) for linha in cursor.fetchall()]


def _aninhar_descritiva(linha: dict) -> dict:
    """Transforma as colunas planas (`nt_ger_media`, ...) em um objeto por nota."""
    item: dict = {"nu_ano": linha["nu_ano"], "cursos": linha["cursos"]}
    for chave, _ in NOTAS_CURSO_ANO:
        item[chave] = {medida: linha[f"{chave}_{medida}"] for medida in _MEDIDAS}
    return item



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


def _dp_curso_ano_por_grupo(where: str, colunas_grupo: tuple[str, ...]) -> str:
    """CTEs `curso_ano` e `dp_curso_ano`: desvio-padrão amostral das médias de curso por grupo.

    A unidade é o curso-ano: a fato é reduzida a uma linha por (`nu_ano`, `co_curso`) dentro
    do grupo antes de calcular o desvio-padrão (`STDDEV_SAMP`, n-1). `colunas_grupo` são as
    colunas da fato que definem o grupo (nomes fixos do código, nunca da requisição).
    """
    grupo = ", ".join(f"f.{c}" for c in colunas_grupo)
    medias = ", ".join(f"MAX(f.{coluna})::float AS {chave}" for chave, coluna in NOTAS_CURSO_ANO)
    desvios = ", ".join(
        f"STDDEV_SAMP({chave})::float AS desvio_padrao_{chave.removeprefix('nt_')}_curso_ano"
        for chave, _ in NOTAS_CURSO_ANO
    )
    chaves = ", ".join(colunas_grupo)
    return f"""
        WITH curso_ano AS (
            SELECT f.nu_ano, f.co_curso, {grupo}, {medias}
            FROM tbl_enade_time_fato f
            WHERE 1=1 {where}
            GROUP BY f.nu_ano, f.co_curso, {grupo}
        ),
        dp_curso_ano AS (
            SELECT {chaves}, {desvios}
            FROM curso_ano
            GROUP BY {chaves}
        )"""


_DP_SELECT = ", ".join(
    f"MAX(d.desvio_padrao_{chave.removeprefix('nt_')}_curso_ano) "
    f"AS desvio_padrao_{chave.removeprefix('nt_')}_curso_ano"
    for chave, _ in NOTAS_CURSO_ANO
)


def resumo_regiao(cursor: PgCursor, filtros: FiltrosAnalise) -> list[dict]:
    """Resumo por região. Os campos `desvio_padrao_*_curso_ano` têm o curso-ano como unidade."""
    where, params = filtros.to_where(alias="f")
    cursor.execute(
        f"""{_dp_curso_ano_por_grupo(where, ("co_regiao_curso",))}
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
            AVG(f.media_nt_ce)::float  AS media_geral_ce,
            {_DP_SELECT}
        FROM tbl_enade_time_fato f
        JOIN tbl_enade_time_dim_regiao r ON f.co_regiao_curso = r.co_regiao
        LEFT JOIN dp_curso_ano d ON d.co_regiao_curso = f.co_regiao_curso
        WHERE 1=1 {where}
        GROUP BY r.co_regiao, r.nome
        ORDER BY r.co_regiao
        """,
        params,
    )
    return list(cursor.fetchall())


def resumo_uf(cursor: PgCursor, filtros: FiltrosAnalise) -> list[dict]:
    """Resumo por UF. Os campos `desvio_padrao_*_curso_ano` têm o curso-ano como unidade."""
    where, params = filtros.to_where(alias="f")
    cursor.execute(
        f"""{_dp_curso_ano_por_grupo(where, ("co_uf_curso",))}
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
            AVG(f.media_nt_ce)::float  AS media_geral_ce,
            {_DP_SELECT}
        FROM tbl_enade_time_fato f
        JOIN tbl_enade_time_dim_uf u ON f.co_uf_curso = u.co_uf
        LEFT JOIN dp_curso_ano d ON d.co_uf_curso = f.co_uf_curso
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
