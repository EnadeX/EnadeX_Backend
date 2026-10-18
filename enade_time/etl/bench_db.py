"""
Helpers de banco, metadados e instrumentação da máquina para os scripts de
benchmark (08, 09, 10, 13, 15).

Tudo aqui é executado apenas pelo **processo principal** — workers do
ProcessPoolExecutor não importam nada deste módulo, não abrem conexão e
não tocam em psutil. `etl.processar_ano` continua puro.

Compatibilidade: `gravar_execucao` aceita os mesmos argumentos de antes; os
campos da v2 (campanha, suíte, ordem de submissão, instrumentação) são
opcionais. O schema precisa ter passado por `scripts/14_migrar_schema_v2.py`.
"""

from __future__ import annotations

import os
import platform
import sys
import threading
import time
from typing import Iterable
from uuid import UUID

import psycopg2


# ---------------------------------------------------------------------------
# Configuração do PostgreSQL (mesmas env vars dos scripts 05/06/07)
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname":   os.environ.get("POSTGRES_DB", "enade_db"),
    "user":     os.environ.get("POSTGRES_USER", "enade_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "enade_password"),
}


def conectar() -> psycopg2.extensions.connection:
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        print(f"\nERRO ao conectar no PostgreSQL: {e}", file=sys.stderr)
        print("Sobe o container com:  docker compose up -d postgres",
              file=sys.stderr)
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# psutil opcional — falha amigável se não instalado
# ---------------------------------------------------------------------------

def carregar_psutil():
    """Retorna o módulo psutil ou aborta com mensagem amigável."""
    try:
        import psutil  # noqa: WPS433
        return psutil
    except ImportError:
        print("\nDependência ausente: psutil", file=sys.stderr)
        print("Instale com:  pip install psutil", file=sys.stderr)
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Metadados da máquina
# ---------------------------------------------------------------------------

def coletar_metadados_maquina() -> dict:
    """CPU (modelo, núcleos físicos e lógicos) e memória total.

    `cpu_count` é mantido por compatibilidade e é o número LÓGICO
    (os.cpu_count()). `cpu_fisicos` vem de psutil.cpu_count(logical=False).
    """
    psutil = carregar_psutil()
    cpu_logicos = os.cpu_count() or 1
    cpu_fisicos = psutil.cpu_count(logical=False) or cpu_logicos
    cpu_modelo = (platform.processor() or "").strip() or "desconhecido"
    memoria_total_mb = round(psutil.virtual_memory().total / (1024 * 1024), 2)
    return {
        "cpu_count": cpu_logicos,
        "cpu_logicos": cpu_logicos,
        "cpu_fisicos": cpu_fisicos,
        "cpu_modelo": cpu_modelo,
        "memoria_total_mb": memoria_total_mb,
    }


def memoria_atual_mb() -> float:
    psutil = carregar_psutil()
    return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)


def bytes_lidos_disco() -> int | None:
    """Total acumulado de bytes lidos do disco (sistema inteiro), ou None."""
    psutil = carregar_psutil()
    io = psutil.disk_io_counters()
    return int(io.read_bytes) if io else None


class AmostradorCpu:
    """Amostra psutil.cpu_percent(percpu=True) num thread do processo principal.

    Média do sistema (todos os núcleos lógicos) ao longo da execução. Custo
    desprezível (uma leitura a cada `intervalo` segundos). Não toca nos workers.
    """

    def __init__(self, intervalo: float = 0.5) -> None:
        self._psutil = carregar_psutil()
        self._intervalo = intervalo
        self._amostras: list[float] = []
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        self._psutil.cpu_percent(percpu=True)  # descarta a 1ª leitura (sem intervalo)
        while not self._parar.wait(self._intervalo):
            por_nucleo = self._psutil.cpu_percent(percpu=True)
            if por_nucleo:
                self._amostras.append(sum(por_nucleo) / len(por_nucleo))

    def iniciar(self) -> "AmostradorCpu":
        self._thread.start()
        return self

    def parar(self) -> float | None:
        self._parar.set()
        self._thread.join(timeout=2)
        if not self._amostras:
            return None
        return round(sum(self._amostras) / len(self._amostras), 2)


# ---------------------------------------------------------------------------
# Persistência no banco — apenas o main chama isto
# ---------------------------------------------------------------------------

SQL_INSERT_EXECUCAO = """
INSERT INTO tbl_enade_time_benchmark_execucao
    (modo, num_workers, tempo_total_seg, linhas_processadas, throughput_lps,
     cpu_count_maquina, cpu_modelo, memoria_pico_mb, observacoes,
     campanha_id, suite_id, oficial, ordem_submissao,
     cpu_fisicos, cpu_logicos, cpu_percent_medio, disco_bytes_lidos,
     cache_quente, aquecimento)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s)
RETURNING id, timestamp_inicio;
"""

SQL_INSERT_ETAPA = """
INSERT INTO tbl_enade_time_benchmark_etapa
    (execucao_id, ano, tempo_seg, linhas_arq3,
     worker_pid, timestamp_inicio, timestamp_fim)
VALUES (%s, %s, %s, %s, %s, %s, %s);
"""


def gravar_execucao(conn, *, modo: str, num_workers: int,
                    tempo_total_seg: float, linhas_processadas: int,
                    throughput_lps: float, cpu_count: int, cpu_modelo: str,
                    memoria_pico_mb: float, observacoes: str,
                    etapas: Iterable[dict],
                    campanha_id: UUID | str | None = None,
                    suite_id: UUID | str | None = None,
                    oficial: bool = False,
                    ordem_submissao: str | None = None,
                    cpu_fisicos: int | None = None,
                    cpu_logicos: int | None = None,
                    cpu_percent_medio: float | None = None,
                    disco_bytes_lidos: int | None = None,
                    cache_quente: bool | None = None,
                    aquecimento: bool = False) -> tuple[int, str]:
    """
    Grava 1 execução + N etapas em uma única transação.
    Retorna (execucao_id, timestamp_inicio_iso).
    """
    if ordem_submissao not in (None, "crescente", "lpt"):
        raise ValueError(f"ordem_submissao inválida: {ordem_submissao!r}")
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SQL_INSERT_EXECUCAO, (
                    modo, num_workers, tempo_total_seg, linhas_processadas,
                    throughput_lps, cpu_count, cpu_modelo, memoria_pico_mb,
                    observacoes,
                    str(campanha_id) if campanha_id else None,
                    str(suite_id) if suite_id else None,
                    bool(oficial), ordem_submissao,
                    cpu_fisicos, cpu_logicos, cpu_percent_medio, disco_bytes_lidos,
                    cache_quente, bool(aquecimento),
                ))
                execucao_id, ts_inicio = cur.fetchone()

                for et in etapas:
                    cur.execute(SQL_INSERT_ETAPA, (
                        execucao_id,
                        et["ano"],
                        et["tempo_seg"],
                        et["linhas_arq3"],
                        et["worker_pid"],
                        et["timestamp_inicio"],
                        et["timestamp_fim"],
                    ))
    except psycopg2.errors.UndefinedColumn as e:
        primeira = (e.pgerror or str(e)).strip().splitlines()[0]
        print(f"\nERRO: schema sem as colunas da v2 ({primeira})", file=sys.stderr)
        print("Aplique a migração aditiva:  python scripts/14_migrar_schema_v2.py",
              file=sys.stderr)
        raise SystemExit(1)
    return execucao_id, str(ts_inicio)


# ---------------------------------------------------------------------------
# Consultas usadas pela suíte (10), pela validação (13) e pelos geradores
# ---------------------------------------------------------------------------

def _linhas_como_dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def tempos_por_ano(conn, execucao_id: int) -> dict[int, float]:
    """Tempo de cada ano (tbl_enade_time_benchmark_etapa) de uma execução — base da ordem LPT."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ano, tempo_seg FROM tbl_enade_time_benchmark_etapa WHERE execucao_id = %s ORDER BY ano",
            (execucao_id,),
        )
        return {int(a): float(t) for a, t in cur.fetchall()}


def consultar_metricas(conn, execucao_ids: list[int]) -> list[dict]:
    """Lê v_enade_time_benchmark_metricas filtrando pelos IDs informados."""
    if not execucao_ids:
        return []
    placeholders = ",".join(["%s"] * len(execucao_ids))
    sql = f"""
        SELECT execucao_id, num_workers, ordem_submissao,
               tempo_sequencial, tempo_paralelo,
               speedup, eficiencia,
               throughput_sequencial, throughput_paralelo,
               cpu_count_maquina, suite_id, campanha_id,
               baseline_execucao_id, pareamento
        FROM v_enade_time_benchmark_metricas
        WHERE execucao_id IN ({placeholders})
        ORDER BY num_workers, ordem_submissao, execucao_id;
    """
    with conn.cursor() as cur:
        cur.execute(sql, execucao_ids)
        return _linhas_como_dicts(cur)


def consultar_resumo(conn, campanha_id: UUID | str) -> list[dict]:
    """Lê v_enade_time_benchmark_resumo de uma campanha (mediana/min/máx/IQR/n por config)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT modo, num_workers, ordem_submissao, n,
                   tempo_mediana, tempo_min, tempo_max, tempo_iqr,
                   throughput_mediana,
                   speedup_mediana, speedup_min, speedup_max,
                   eficiencia_mediana, eficiencia_min, eficiencia_max,
                   oficial, cpu_fisicos, cpu_logicos, cache_quente
            FROM v_enade_time_benchmark_resumo
            WHERE campanha_id = %s
            ORDER BY num_workers, ordem_submissao NULLS FIRST
            """,
            (str(campanha_id),),
        )
        return _linhas_como_dicts(cur)


def ultima_campanha_oficial(conn) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT campanha_id::text
            FROM tbl_enade_time_benchmark_execucao
            WHERE oficial AND campanha_id IS NOT NULL
            GROUP BY campanha_id
            ORDER BY MIN(timestamp_inicio) DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return row[0] if row else None


def pausar(segundos: float) -> None:
    """Pausa entre execuções da suíte (só no processo principal)."""
    if segundos > 0:
        time.sleep(segundos)
