"""
Benchmark SEQUENCIAL do ETL ENADE.

Processa os 6 anos um após o outro no processo principal (sem
multiprocessing). Mede tempo total, throughput, memória de pico, CPU média do
sistema e bytes lidos do disco. Grava 1 linha em tbl_enade_time_benchmark_execucao e 6 em
tbl_enade_time_benchmark_etapa.

Uso:
  python scripts/08_benchmark_sequencial.py
  python scripts/08_benchmark_sequencial.py --obs "rodada 1, máquina A"
  python scripts/08_benchmark_sequencial.py --campanha <uuid> --suite <uuid> --oficial

Os argumentos de campanha/suíte são preenchidos pelo script 10 (campanha
oficial); rodando solto, a execução fica fora de qualquer campanha
(oficial = FALSE).

Requer: psycopg2-binary, psutil. Schema com `scripts/14_migrar_schema_v2.py`.
"""

from __future__ import annotations

import argparse
import sys
import time
from uuid import UUID

# garante importação de `etl.*` quando rodado de qualquer CWD
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))  # raiz do EnadeX

from enade_time.etl.bench_db import (  # noqa: E402
    AmostradorCpu, bytes_lidos_disco, coletar_metadados_maquina, conectar,
    gravar_execucao, memoria_atual_mb,
)
from enade_time.etl.processar_ano import processar_ano  # noqa: E402

ANOS = (2005, 2008, 2011, 2014, 2017, 2021)


def _mb(bytes_: int | None) -> str:
    return "n/d" if bytes_ is None else f"{bytes_ / 1024 / 1024:,.1f} MB"


def rodar_sequencial(observacoes: str = "", *,
                     campanha_id: UUID | str | None = None,
                     suite_id: UUID | str | None = None,
                     oficial: bool = False,
                     aquecimento: bool = False,
                     cache_quente: bool | None = None) -> int:
    """
    Executa o pipeline sequencial e grava no banco. Retorna execucao_id.
    Função reutilizável pela campanha (script 10).
    """
    meta = coletar_metadados_maquina()
    print("=" * 80)
    print("BENCHMARK SEQUENCIAL" + ("  [AQUECIMENTO — descartado]" if aquecimento else ""))
    print("=" * 80)
    print(f"CPU      : {meta['cpu_modelo']}  "
          f"({meta['cpu_fisicos']} físicos / {meta['cpu_logicos']} lógicos)")
    print(f"Memória  : {meta['memoria_total_mb']:.0f} MB total")
    print(f"Anos     : {list(ANOS)}")
    if suite_id:
        print(f"Suíte    : {suite_id}  campanha: {campanha_id}  oficial: {oficial}")
    print()

    mem_inicio = memoria_atual_mb()
    disco_ini = bytes_lidos_disco()
    amostrador = AmostradorCpu().iniciar()
    t0 = time.perf_counter()
    etapas: list[dict] = []
    mem_pico = mem_inicio

    for ano in ANOS:
        print(f"  [{ano}] iniciando...", end="", flush=True)
        et = processar_ano(ano)
        etapas.append(et)
        mem_pico = max(mem_pico, memoria_atual_mb())
        print(f" {et['tempo_seg']:>7.2f}s  "
              f"linhas_arq1={et['linhas_arq1']:>7}  "
              f"linhas_arq3={et['linhas_arq3']:>7}  "
              f"filtradas={et['linhas_filtradas']:>5}  "
              f"status={et['status']}")

    tempo_total = round(time.perf_counter() - t0, 4)
    cpu_medio = amostrador.parar()
    disco_fim = bytes_lidos_disco()
    disco_lido = (disco_fim - disco_ini) if (disco_ini is not None and disco_fim is not None) else None

    linhas_processadas = sum(e["linhas_arq1"] + e["linhas_arq3"] for e in etapas)
    throughput = round(linhas_processadas / tempo_total, 2) if tempo_total > 0 else 0.0

    print()
    print(f"Tempo total           : {tempo_total:.2f}s")
    print(f"Linhas processadas    : {linhas_processadas:,}  "
          f"(arq1+arq3 dos 6 anos)")
    print(f"Throughput            : {throughput:,.0f} linhas/s")
    print(f"Memória pico (RSS)    : {mem_pico:.1f} MB "
          f"(início: {mem_inicio:.1f} MB)")
    print(f"CPU média do sistema  : {cpu_medio if cpu_medio is not None else 'n/d'} %")
    print(f"Lido do disco         : {_mb(disco_lido)}")

    erros = [e for e in etapas if e["status"] != "ok"]
    if erros:
        print(f"\nATENÇÃO: {len(erros)} ano(s) com erro:")
        for e in erros:
            print(f"  [{e['ano']}] {e['observacoes']}")

    # ----- grava no banco -----
    print("\nGravando em tbl_enade_time_benchmark_execucao + tbl_enade_time_benchmark_etapa...")
    conn = conectar()
    try:
        execucao_id, ts = gravar_execucao(
            conn,
            modo="sequencial",
            num_workers=1,
            tempo_total_seg=tempo_total,
            linhas_processadas=linhas_processadas,
            throughput_lps=throughput,
            cpu_count=meta["cpu_count"],
            cpu_modelo=meta["cpu_modelo"],
            memoria_pico_mb=mem_pico,
            observacoes=observacoes,
            etapas=etapas,
            campanha_id=campanha_id,
            suite_id=suite_id,
            oficial=oficial,
            ordem_submissao=None,
            cpu_fisicos=meta["cpu_fisicos"],
            cpu_logicos=meta["cpu_logicos"],
            cpu_percent_medio=cpu_medio,
            disco_bytes_lidos=disco_lido,
            cache_quente=cache_quente,
            aquecimento=aquecimento,
        )
    finally:
        conn.close()

    print(f"  execucao_id = {execucao_id}   timestamp = {ts}")
    return execucao_id


def _flag_cache(valor: str | None) -> bool | None:
    return None if valor is None else (valor == "sim")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--obs", default="", help="Observação livre (texto).")
    ap.add_argument("--campanha", type=UUID, default=None, help="campanha_id (preenchido pelo 10).")
    ap.add_argument("--suite", type=UUID, default=None, help="suite_id (preenchido pelo 10).")
    ap.add_argument("--oficial", action="store_true", help="Marca a execução como oficial.")
    ap.add_argument("--aquecimento", action="store_true",
                    help="Passada de aquecimento de cache (descartada das métricas).")
    ap.add_argument("--cache-quente", choices=("sim", "nao"), default=None,
                    help="Declara a condição de cache de páginas (o 10 preenche).")
    args = ap.parse_args()
    rodar_sequencial(observacoes=args.obs, campanha_id=args.campanha, suite_id=args.suite,
                     oficial=args.oficial, aquecimento=args.aquecimento,
                     cache_quente=_flag_cache(args.cache_quente))
    return 0


if __name__ == "__main__":
    sys.exit(main())
