"""
Benchmark PARALELO do ETL ENADE (processamento de dados por ano).

Cada worker processa 1 ano completo via `etl.processar_ano.processar_ano`.
Usa `concurrent.futures.ProcessPoolExecutor` (processos, não threads —
trabalho é CPU+I/O bound e o GIL atrapalha em threads).

No Windows o método padrão é SPAWN, por isso:
  - `processar_ano` está em módulo top-level (etl/processar_ano.py)
  - este script tem `if __name__ == "__main__":` + `freeze_support()`
  - apenas o processo principal conecta no PostgreSQL

ORDEM DE SUBMISSÃO (--ordem)
  O executor entrega cada tarefa ao primeiro worker livre, na ordem em que
  foi submetida — ele NÃO faz balanceamento. Com 6 unidades de tamanhos
  diferentes, a ordem de submissão muda o makespan:
    crescente : anos em ordem crescente (2005 … 2021) — comportamento
                histórico deste script (rodadas de 21/06 e 21/08).
    lpt       : Longest Processing Time first (Graham, 1969): anos em ordem
                DECRESCENTE de tempo, usando os tempos por ano do sequencial
                da mesma suíte (--tempos-de <execucao_id>, preenchido pelo
                script 10). Sem referência, usa o tamanho de arq1+arq3 em
                bytes como proxy.
  A ordem efetivamente usada é gravada em `ordem_submissao` e listada em
  `observacoes`.

Uso:
  python scripts/09_benchmark_paralelo.py                       # 4 workers, lpt (proxy)
  python scripts/09_benchmark_paralelo.py --workers 2 --ordem crescente
  python scripts/09_benchmark_paralelo.py --workers 4 --ordem lpt --tempos-de 4
  python scripts/09_benchmark_paralelo.py --workers 4 --obs "rodada A"

Requer: psycopg2-binary, psutil. Schema com `scripts/14_migrar_schema_v2.py`.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import freeze_support
from uuid import UUID

# garante importação de `etl.*` quando rodado de qualquer CWD
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))  # raiz do EnadeX

from enade_time.etl.bench_db import (  # noqa: E402
    AmostradorCpu, bytes_lidos_disco, coletar_metadados_maquina, conectar,
    gravar_execucao, memoria_atual_mb, tempos_por_ano,
)
from enade_time.etl.processar_ano import (  # noqa: E402
    encontrar_arquivo_arq, encontrar_pasta_ano, processar_ano,
)

ANOS = (2005, 2008, 2011, 2014, 2017, 2021)
ORDENS = ("crescente", "lpt")


# ---------------------------------------------------------------------------
# Ordem de submissão
# ---------------------------------------------------------------------------

def tempos_proxy_tamanho() -> dict[int, float]:
    """Proxy determinístico para LPT sem sequencial de referência: bytes de arq1+arq3."""
    out: dict[int, float] = {}
    for ano in ANOS:
        pasta = encontrar_pasta_ano(ano)
        total = 0
        if pasta is not None:
            for n in (1, 3):
                arq = encontrar_arquivo_arq(pasta, ano, n)
                if arq is not None:
                    total += arq.stat().st_size
        out[ano] = float(total)
    return out


def ordem_de_submissao(ordem: str, tempos_base: dict[int, float] | None) -> list[int]:
    if ordem == "crescente":
        return sorted(ANOS)
    if ordem == "lpt":
        base = tempos_base or tempos_proxy_tamanho()
        # maior primeiro; empate desfeito pelo ano (determinístico)
        return sorted(ANOS, key=lambda a: (-base.get(a, 0.0), a))
    raise ValueError(f"ordem inválida: {ordem!r} (use {ORDENS})")


def makespan_guloso(tempos: dict[int, float], ordem_anos: list[int], p: int) -> float:
    """Makespan do escalonamento 'primeiro worker livre' na ordem dada (teto teórico)."""
    cargas = [0.0] * p
    for ano in ordem_anos:
        i = cargas.index(min(cargas))
        cargas[i] += tempos.get(ano, 0.0)
    return max(cargas)


def _mb(bytes_: int | None) -> str:
    return "n/d" if bytes_ is None else f"{bytes_ / 1024 / 1024:,.1f} MB"


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def rodar_paralelo(num_workers: int, observacoes: str = "", *,
                   ordem: str = "lpt",
                   tempos_base: dict[int, float] | None = None,
                   campanha_id: UUID | str | None = None,
                   suite_id: UUID | str | None = None,
                   oficial: bool = False,
                   aquecimento: bool = False,
                   cache_quente: bool | None = None) -> int:
    """
    Executa o pipeline em paralelo com N workers e grava no banco.
    Retorna execucao_id. Reutilizável pela campanha (script 10).
    """
    if num_workers < 1:
        raise ValueError("num_workers deve ser >= 1")
    if ordem not in ORDENS:
        raise ValueError(f"ordem deve ser uma de {ORDENS}")

    meta = coletar_metadados_maquina()
    ordem_anos = ordem_de_submissao(ordem, tempos_base)
    if ordem == "crescente":
        origem_ordem = "ordem fixa"
    elif tempos_base:
        origem_ordem = "tempos do sequencial da suíte"
    else:
        origem_ordem = "proxy: tamanho dos arquivos"

    print("=" * 80)
    print(f"BENCHMARK PARALELO  (workers={num_workers}, ordem={ordem})")
    print("=" * 80)
    print(f"CPU      : {meta['cpu_modelo']}  "
          f"({meta['cpu_fisicos']} físicos / {meta['cpu_logicos']} lógicos)")
    print(f"Memória  : {meta['memoria_total_mb']:.0f} MB total")
    print(f"Submissão: {ordem_anos}  ({origem_ordem})")
    if tempos_base:
        soma = sum(tempos_base.values())
        teto = makespan_guloso(tempos_base, ordem_anos, num_workers)
        print(f"Teto     : makespan guloso {teto:.2f}s → speedup máx. por escalonamento "
              f"{soma / teto:.2f}x (sem contenção nem overhead)")
    if suite_id:
        print(f"Suíte    : {suite_id}  campanha: {campanha_id}  oficial: {oficial}")
    print()

    if num_workers > meta["cpu_fisicos"]:
        print(f"AVISO: workers ({num_workers}) > núcleos físicos ({meta['cpu_fisicos']}) — "
              f"parte dos workers roda em hyperthreads.\n")

    mem_inicio = memoria_atual_mb()
    disco_ini = bytes_lidos_disco()
    amostrador = AmostradorCpu().iniciar()
    t0 = time.perf_counter()
    etapas: list[dict] = []
    mem_pico = mem_inicio

    # ProcessPoolExecutor: submete os 6 anos NA ORDEM ESCOLHIDA; workers
    # devolvem dict. A ordem de conclusão difere da de submissão — reordenamos
    # por ano antes de gravar.
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futuros = {executor.submit(processar_ano, ano): ano for ano in ordem_anos}
        for fut in as_completed(futuros):
            ano = futuros[fut]
            try:
                et = fut.result()
            except Exception as exc:  # nunca quebra a campanha
                et = {
                    "ano": ano, "worker_pid": -1,
                    "timestamp_inicio": "", "timestamp_fim": "",
                    "tempo_seg": 0.0, "linhas_arq1": 0, "linhas_arq3": 0,
                    "linhas_filtradas": 0, "cursos_unicos": 0,
                    "min_media": None, "max_media": None, "mean_media": None,
                    "count_cursos_com_media": 0,
                    "status": "erro", "observacoes": f"future: {exc}",
                }
            etapas.append(et)
            mem_pico = max(mem_pico, memoria_atual_mb())
            print(f"  [{et['ano']}] pid={et['worker_pid']:>6}  "
                  f"{et['tempo_seg']:>7.2f}s  "
                  f"linhas_arq3={et['linhas_arq3']:>7}  "
                  f"filtradas={et['linhas_filtradas']:>5}  "
                  f"status={et['status']}")

    tempo_total = round(time.perf_counter() - t0, 4)
    cpu_medio = amostrador.parar()
    disco_fim = bytes_lidos_disco()
    disco_lido = (disco_fim - disco_ini) if (disco_ini is not None and disco_fim is not None) else None

    etapas.sort(key=lambda e: e["ano"])
    linhas_processadas = sum(e["linhas_arq1"] + e["linhas_arq3"] for e in etapas)
    throughput = round(linhas_processadas / tempo_total, 2) if tempo_total > 0 else 0.0

    soma_etapas = sum(e["tempo_seg"] for e in etapas)
    sobreposicao = soma_etapas / tempo_total if tempo_total > 0 else 0.0

    print()
    print(f"Tempo total wall-clock: {tempo_total:.2f}s")
    print(f"Soma tempos das etapas: {soma_etapas:.2f}s  "
          f"(sobreposição efetiva: {sobreposicao:.2f}x)")
    print(f"Linhas processadas    : {linhas_processadas:,}")
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

    obs_final = (observacoes + " | " if observacoes else "") + \
        f"ordem={ordem} [{','.join(str(a) for a in ordem_anos)}]"

    # ----- grava no banco (apenas no processo principal) -----
    print("\nGravando em tbl_enade_time_benchmark_execucao + tbl_enade_time_benchmark_etapa...")
    conn = conectar()
    try:
        execucao_id, ts = gravar_execucao(
            conn,
            modo="paralelo",
            num_workers=num_workers,
            tempo_total_seg=tempo_total,
            linhas_processadas=linhas_processadas,
            throughput_lps=throughput,
            cpu_count=meta["cpu_count"],
            cpu_modelo=meta["cpu_modelo"],
            memoria_pico_mb=mem_pico,
            observacoes=obs_final,
            etapas=etapas,
            campanha_id=campanha_id,
            suite_id=suite_id,
            oficial=oficial,
            ordem_submissao=ordem,
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
    ap.add_argument("--workers", type=int, default=4,
                    help="Número de processos paralelos (default: 4).")
    ap.add_argument("--ordem", choices=ORDENS, default="lpt",
                    help="Ordem de submissão dos anos (default: lpt).")
    ap.add_argument("--tempos-de", type=int, default=None, metavar="EXECUCAO_ID",
                    help="Usa os tempos por ano dessa execução sequencial para a ordem LPT.")
    ap.add_argument("--obs", default="", help="Observação livre (texto).")
    ap.add_argument("--campanha", type=UUID, default=None)
    ap.add_argument("--suite", type=UUID, default=None)
    ap.add_argument("--oficial", action="store_true")
    ap.add_argument("--aquecimento", action="store_true")
    ap.add_argument("--cache-quente", choices=("sim", "nao"), default=None)
    args = ap.parse_args()

    tempos_base = None
    if args.tempos_de is not None:
        conn = conectar()
        try:
            tempos_base = tempos_por_ano(conn, args.tempos_de)
        finally:
            conn.close()
        if not tempos_base:
            print(f"ERRO: execução {args.tempos_de} sem etapas no banco.", file=sys.stderr)
            return 1

    rodar_paralelo(num_workers=args.workers, observacoes=args.obs, ordem=args.ordem,
                   tempos_base=tempos_base, campanha_id=args.campanha, suite_id=args.suite,
                   oficial=args.oficial, aquecimento=args.aquecimento,
                   cache_quente=_flag_cache(args.cache_quente))
    return 0


if __name__ == "__main__":
    freeze_support()  # obrigatório no Windows quando empacotado (.exe)
    sys.exit(main())
