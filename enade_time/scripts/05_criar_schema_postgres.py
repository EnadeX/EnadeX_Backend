"""
Cria o schema do banco ENADE-Time Distribuído no PostgreSQL.

Tabelas criadas:
  - tbl_enade_time_dim_regiao, tbl_enade_time_dim_uf, tbl_enade_time_dim_grupo, tbl_enade_time_dim_categoria_adm, tbl_enade_time_dim_organizacao_acad,
    tbl_enade_time_dim_modalidade, tbl_enade_time_dim_ano  (lookup tables)
  - tbl_enade_time_fato                (tabela fato — 1 linha por aluno-curso-ano)
  - tbl_enade_time_benchmark_execucao        (1 execução do ETL, sequencial ou paralela)
  - tbl_enade_time_benchmark_etapa           (tempo de cada ano dentro de uma execução)
  - view v_enade_time_benchmark_metricas (speedup, eficiência, throughput)

Uso:
  python scripts/05_criar_schema_postgres.py            # cria (erro se já existe)
  python scripts/05_criar_schema_postgres.py --reset    # DROP CASCADE e recria

ATENÇÃO — `--reset` APAGA tbl_enade_time_benchmark_execucao/tbl_enade_time_benchmark_etapa (incidente D9).
Em banco que já tem dados use `scripts/14_migrar_schema_v2.py`, que é aditivo.
Este script aplica a mesma extensão v2 (campanhas, suítes, ordem de submissão,
instrumentação, v_enade_time_benchmark_resumo) logo após criar as tabelas-base, importando
`aplicar()` do script 14 — a definição vive em um único lugar.

Lê configuração de variáveis de ambiente (com defaults):
  POSTGRES_HOST=localhost  POSTGRES_PORT=5432
  POSTGRES_DB=enade_db     POSTGRES_USER=enade_user  POSTGRES_PASSWORD=enade_password
"""

from __future__ import annotations

import argparse
import os
import sys

import importlib.util
from pathlib import Path

import psycopg2
from psycopg2 import sql

# Extensão v2 do benchmark (script 14) — carregada por caminho porque o nome
# do módulo começa com dígito. Só `aplicar()` é usado.
_spec14 = importlib.util.spec_from_file_location(
    "migrar_schema_v2", Path(__file__).resolve().parent / "14_migrar_schema_v2.py"
)
_mig14 = importlib.util.module_from_spec(_spec14)
_spec14.loader.exec_module(_mig14)


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname":   os.environ.get("POSTGRES_DB", "enade_db"),
    "user":     os.environ.get("POSTGRES_USER", "enade_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "enade_password"),
}


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL_DIMENSOES = """
CREATE TABLE tbl_enade_time_dim_regiao (
    co_regiao  SMALLINT PRIMARY KEY,
    nome       VARCHAR(20) NOT NULL
);

CREATE TABLE tbl_enade_time_dim_uf (
    co_uf      SMALLINT PRIMARY KEY,
    sigla      CHAR(2)     NOT NULL,
    nome       VARCHAR(40) NOT NULL,
    co_regiao  SMALLINT    NOT NULL REFERENCES tbl_enade_time_dim_regiao(co_regiao)
);

CREATE TABLE tbl_enade_time_dim_grupo (
    co_grupo   SMALLINT PRIMARY KEY,
    nome       VARCHAR(80) NOT NULL
);

CREATE TABLE tbl_enade_time_dim_categoria_adm (
    co_categad SMALLINT PRIMARY KEY,
    nome       VARCHAR(80) NOT NULL
);

CREATE TABLE tbl_enade_time_dim_organizacao_acad (
    co_orgacad SMALLINT PRIMARY KEY,
    nome       VARCHAR(80) NOT NULL
);

CREATE TABLE tbl_enade_time_dim_modalidade (
    co_modalidade SMALLINT PRIMARY KEY,
    nome          VARCHAR(20) NOT NULL
);

CREATE TABLE tbl_enade_time_dim_ano (
    co_ano  SMALLINT PRIMARY KEY,
    edicao  VARCHAR(60) NULL
);
"""

DDL_FATO = """
CREATE TABLE tbl_enade_time_fato (
    id                BIGSERIAL PRIMARY KEY,
    nu_ano            SMALLINT  NOT NULL REFERENCES tbl_enade_time_dim_ano(co_ano),
    co_curso          INTEGER   NOT NULL,
    co_ies            INTEGER   NOT NULL,
    co_categad        SMALLINT  NOT NULL REFERENCES tbl_enade_time_dim_categoria_adm(co_categad),
    co_orgacad        SMALLINT  NOT NULL REFERENCES tbl_enade_time_dim_organizacao_acad(co_orgacad),
    co_grupo          SMALLINT  NOT NULL REFERENCES tbl_enade_time_dim_grupo(co_grupo),
    co_modalidade     SMALLINT  NULL     REFERENCES tbl_enade_time_dim_modalidade(co_modalidade),
    co_munic_curso    INTEGER   NULL,
    co_uf_curso       SMALLINT  NOT NULL REFERENCES tbl_enade_time_dim_uf(co_uf),
    co_regiao_curso   SMALLINT  NOT NULL REFERENCES tbl_enade_time_dim_regiao(co_regiao),
    media_nt_fg       NUMERIC(7,4) NULL,
    media_nt_ger      NUMERIC(7,4) NULL,
    media_nt_ce       NUMERIC(7,4) NULL,
    CHECK (media_nt_fg  IS NULL OR (media_nt_fg  >= 0 AND media_nt_fg  <= 100)),
    CHECK (media_nt_ger IS NULL OR (media_nt_ger >= 0 AND media_nt_ger <= 100)),
    CHECK (media_nt_ce  IS NULL OR (media_nt_ce  >= 0 AND media_nt_ce  <= 100))
);

CREATE INDEX idx_fato_ano        ON tbl_enade_time_fato(nu_ano);
CREATE INDEX idx_fato_regiao     ON tbl_enade_time_fato(co_regiao_curso);
CREATE INDEX idx_fato_uf         ON tbl_enade_time_fato(co_uf_curso);
CREATE INDEX idx_fato_ies        ON tbl_enade_time_fato(co_ies);
CREATE INDEX idx_fato_curso      ON tbl_enade_time_fato(co_curso);
CREATE INDEX idx_fato_modalidade ON tbl_enade_time_fato(co_modalidade);
CREATE INDEX idx_fato_categad    ON tbl_enade_time_fato(co_categad);
CREATE INDEX idx_fato_ano_regiao ON tbl_enade_time_fato(nu_ano, co_regiao_curso);
CREATE INDEX idx_fato_ano_uf     ON tbl_enade_time_fato(nu_ano, co_uf_curso);
CREATE INDEX idx_fato_media_valida
    ON tbl_enade_time_fato(nu_ano, co_regiao_curso)
    WHERE media_nt_fg IS NOT NULL;
"""

DDL_BENCHMARK = """
CREATE TABLE tbl_enade_time_benchmark_execucao (
    id                 BIGSERIAL PRIMARY KEY,
    timestamp_inicio   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modo               VARCHAR(20) NOT NULL
                       CHECK (modo IN ('sequencial','paralelo')),
    num_workers        SMALLINT    NOT NULL,
    tempo_total_seg    NUMERIC(10,4) NOT NULL,
    linhas_processadas BIGINT      NOT NULL,
    throughput_lps     NUMERIC(12,2) NOT NULL,
    cpu_count_maquina  SMALLINT    NOT NULL,
    cpu_modelo         TEXT        NULL,
    memoria_pico_mb    NUMERIC(10,2) NULL,
    observacoes        TEXT        NULL
);

CREATE TABLE tbl_enade_time_benchmark_etapa (
    id                BIGSERIAL PRIMARY KEY,
    execucao_id       BIGINT NOT NULL
                      REFERENCES tbl_enade_time_benchmark_execucao(id) ON DELETE CASCADE,
    ano               SMALLINT NOT NULL,
    tempo_seg         NUMERIC(10,4) NOT NULL,
    linhas_arq3       BIGINT   NOT NULL,
    worker_pid        INTEGER  NULL,
    timestamp_inicio  TIMESTAMPTZ NOT NULL,
    timestamp_fim     TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_bench_etapa_exec ON tbl_enade_time_benchmark_etapa(execucao_id);

-- View com speedup e eficiência: compara cada execução paralela contra
-- a execução sequencial imediatamente anterior no tempo.
CREATE VIEW v_enade_time_benchmark_metricas AS
SELECT
    p.id                 AS execucao_id,
    p.timestamp_inicio,
    p.num_workers,
    s.tempo_total_seg    AS tempo_sequencial,
    p.tempo_total_seg    AS tempo_paralelo,
    ROUND((s.tempo_total_seg / p.tempo_total_seg)::NUMERIC, 4) AS speedup,
    ROUND(((s.tempo_total_seg / p.tempo_total_seg) / p.num_workers)::NUMERIC, 4)
        AS eficiencia,
    p.throughput_lps     AS throughput_paralelo,
    s.throughput_lps     AS throughput_sequencial,
    p.cpu_count_maquina
FROM tbl_enade_time_benchmark_execucao p
LEFT JOIN LATERAL (
    SELECT * FROM tbl_enade_time_benchmark_execucao
    WHERE modo = 'sequencial' AND timestamp_inicio < p.timestamp_inicio
    ORDER BY timestamp_inicio DESC LIMIT 1
) s ON TRUE
WHERE p.modo = 'paralelo';
"""

# ---------------------------------------------------------------------------
# Lookup data (legendas oficiais do INEP — confirmar com dicionário em
# microdados_enade_*/1.LEIA-ME/ antes da apresentação)
# ---------------------------------------------------------------------------

SEED = """
INSERT INTO tbl_enade_time_dim_regiao (co_regiao, nome) VALUES
    (1, 'Norte'),
    (2, 'Nordeste');

INSERT INTO tbl_enade_time_dim_uf (co_uf, sigla, nome, co_regiao) VALUES
    (11, 'RO', 'Rondônia',            1),
    (12, 'AC', 'Acre',                1),
    (13, 'AM', 'Amazonas',            1),
    (14, 'RR', 'Roraima',             1),
    (15, 'PA', 'Pará',                1),
    (16, 'AP', 'Amapá',               1),
    (17, 'TO', 'Tocantins',           1),
    (21, 'MA', 'Maranhão',            2),
    (22, 'PI', 'Piauí',               2),
    (23, 'CE', 'Ceará',               2),
    (24, 'RN', 'Rio Grande do Norte', 2),
    (25, 'PB', 'Paraíba',             2),
    (26, 'PE', 'Pernambuco',          2),
    (27, 'AL', 'Alagoas',             2),
    (28, 'SE', 'Sergipe',             2),
    (29, 'BA', 'Bahia',               2);

-- Computação mudou de código entre ciclos do ENADE: 40 nas edições de
-- 2005/2008 e 4004 de 2011 em diante. É o MESMO curso — os dois códigos
-- nunca coexistem no mesmo ano. Os rótulos trazem o intervalo para o
-- filtro do dashboard não exibir duas opções indistinguíveis.
INSERT INTO tbl_enade_time_dim_grupo (co_grupo, nome) VALUES
    (40,   'Ciência da Computação (código 2005–2008)'),
    (4004, 'Ciência da Computação (código 2011+)');

INSERT INTO tbl_enade_time_dim_categoria_adm (co_categad, nome) VALUES
    (1, 'Pública Federal'),
    (2, 'Pública Estadual'),
    (3, 'Pública Municipal'),
    (4, 'Privada com fins lucrativos'),
    (5, 'Privada sem fins lucrativos'),
    (7, 'Especial');

INSERT INTO tbl_enade_time_dim_organizacao_acad (co_orgacad, nome) VALUES
    (10019, 'Universidade'),
    (10020, 'Centro Universitário'),
    (10022, 'Faculdade'),
    (10026, 'IF e CEFET'),
    (10027, 'Centro de Educação Tecnológica'),
    (10028, 'Faculdade Integrada');

INSERT INTO tbl_enade_time_dim_modalidade (co_modalidade, nome) VALUES
    (0, 'EAD'),
    (1, 'Presencial');

INSERT INTO tbl_enade_time_dim_ano (co_ano, edicao) VALUES
    (2005, NULL),
    (2008, NULL),
    (2011, NULL),
    (2014, NULL),
    (2017, NULL),
    (2021, 'reposição da pandemia');
"""


TABELAS_NA_ORDEM_DE_DROP = [
    # ordem inversa de dependência; CASCADE cuida do resto, mas listamos
    # explicitamente para o reset ser previsível
    "v_enade_time_benchmark_resumo",     # view (depende de v_enade_time_benchmark_metricas)
    "v_enade_time_benchmark_metricas",   # view
    "tbl_enade_time_publicacao",
    "tbl_enade_time_benchmark_etapa",
    "tbl_enade_time_benchmark_execucao",
    "tbl_enade_time_fato",
    "tbl_enade_time_dim_ano",
    "tbl_enade_time_dim_modalidade",
    "tbl_enade_time_dim_organizacao_acad",
    "tbl_enade_time_dim_categoria_adm",
    "tbl_enade_time_dim_grupo",
    "tbl_enade_time_dim_uf",
    "tbl_enade_time_dim_regiao",
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--reset", action="store_true",
        help="DROP CASCADE de todas as tabelas/views antes de criar."
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    print(f"Conectando em postgresql://{DB_CONFIG['user']}@"
          f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        print(f"\nERRO ao conectar no PostgreSQL: {e}", file=sys.stderr)
        print("\nVerifique se o container está rodando:", file=sys.stderr)
        print("  docker compose up -d postgres", file=sys.stderr)
        return 1

    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if args.reset:
                print("\n[--reset] Removendo tabelas/views existentes...")
                for nome in TABELAS_NA_ORDEM_DE_DROP:
                    cur.execute(
                        sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                            sql.Identifier(nome)
                        )
                        if not nome.startswith("v_") else
                        sql.SQL("DROP VIEW IF EXISTS {} CASCADE").format(
                            sql.Identifier(nome)
                        )
                    )
                    print(f"  drop {nome}")

            print("\nCriando dimensões...")
            cur.execute(DDL_DIMENSOES)
            print("Criando tabela fato + índices...")
            cur.execute(DDL_FATO)
            print("Criando tabelas de benchmark + view...")
            cur.execute(DDL_BENCHMARK)
            print("Aplicando extensão v2 do benchmark (script 14)...")
            _mig14.aplicar(cur, verbose=False)
            print("Inserindo lookup data...")
            cur.execute(SEED)

            # Sumário
            cur.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_type DESC, table_name;
            """)
            objs = cur.fetchall()

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("\nObjetos criados:")
    for nome, tipo in objs:
        print(f"  [{tipo:<10}] {nome}")
    print(f"\nTotal: {len(objs)} objetos.")
    print("\nSchema pronto. Próximo passo:")
    print("  python scripts/06_carregar_dados_postgres.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
