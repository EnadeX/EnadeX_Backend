"""
Campanha de benchmark — roda N repetições (suítes) da mesma bateria e agrupa
tudo sob um `campanha_id`, para que mediana/mín/máx/IQR existam como linhas
de `v_enade_time_benchmark_resumo` (e não como número solto em documento).

Hierarquia gravada no banco
  campanha (1)  →  suíte = repetição (--reps)  →  execuções por suíte:
      1 sequencial  +  len(--workers) × len(--ordens) paralelas
  Ex.: --workers 2,3,4,6 --ordens crescente,lpt --reps 5  →  5 × 9 = 45 execuções.

Cada suíte roda o sequencial PRIMEIRO; os tempos por ano dele alimentam a
ordem LPT das paralelas da mesma suíte, e `v_enade_time_benchmark_metricas` pareia cada
paralela com esse sequencial (nunca com o de outra suíte).

Aquecimento (padrão; desligue com --sem-aquecer): um sequencial extra ANTES
da campanha, marcado aquecimento = TRUE e oficial = FALSE (fica fora do
resumo). Depois dele, todas as execuções são gravadas com cache_quente = TRUE —
condição declarada, não escondida.

Importante (Windows + multiprocessing):
  - usa `if __name__ == "__main__":` + `freeze_support()`
  - delega para `rodar_sequencial` e `rodar_paralelo` (scripts 08 e 09)
  - apenas o processo principal conecta no PostgreSQL

Uso:
  python scripts/10_rodar_suite_benchmark.py                          # 2,3,4,6 × crescente,lpt × 5, aquece
  python scripts/10_rodar_suite_benchmark.py --oficial --obs "campanha oficial v2"
  python scripts/10_rodar_suite_benchmark.py --workers 2 --ordens lpt --reps 1 --sem-aquecer --obs smoke

O manifesto da campanha (ids, parâmetros, máquina) é gravado em
backups/campanhas/<campanha_id>.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from multiprocessing import freeze_support
from pathlib import Path
from uuid import UUID, uuid4

# garante importação de `etl.*` e dos scripts irmãos
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ.parent))  # raiz do EnadeX — permite importar enade_time.*
sys.path.insert(0, str(RAIZ / "scripts"))


def _carregar(nome_modulo: str, caminho: str):
    spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seq_mod = _carregar(
    "bench_seq", str(RAIZ / "scripts" / "08_benchmark_sequencial.py"))
par_mod = _carregar(
    "bench_par", str(RAIZ / "scripts" / "09_benchmark_paralelo.py"))

from enade_time.etl.bench_db import (  # noqa: E402
    AmostradorCpu, coletar_metadados_maquina, conectar, consultar_resumo, pausar,
    tempos_por_ano,
)


def banner(titulo: str) -> None:
    print("\n" + "#" * 80)
    print(f"##  {titulo}")
    print("#" * 80)


def _lista_int(txt: str) -> list[int]:
    vals = sorted({int(x) for x in txt.split(",") if x.strip()})
    if any(v < 2 for v in vals):
        raise argparse.ArgumentTypeError("--workers só aceita valores >= 2 (o sequencial é automático)")
    return vals


def _lista_ordens(txt: str) -> list[str]:
    vals = [x.strip() for x in txt.split(",") if x.strip()]
    for v in vals:
        if v not in par_mod.ORDENS:
            raise argparse.ArgumentTypeError(f"ordem inválida: {v} (use {par_mod.ORDENS})")
    return vals


def imprimir_resumo(linhas: list[dict]) -> None:
    if not linhas:
        print("  (v_enade_time_benchmark_resumo vazia para esta campanha)")
        return
    print(f"{'modo':>10} {'w':>2} {'ordem':>9} {'n':>2} {'t_med(s)':>9} {'t_min':>8} {'t_max':>8} "
          f"{'IQR':>6} {'S_med':>6} {'S_min':>6} {'S_max':>6} {'E_med':>6}")
    for r in linhas:
        print(f"{r['modo']:>10} {r['num_workers']:>2} {str(r['ordem_submissao'] or '-'):>9} {r['n']:>2} "
              f"{float(r['tempo_mediana']):>9.2f} {float(r['tempo_min']):>8.2f} {float(r['tempo_max']):>8.2f} "
              f"{float(r['tempo_iqr']):>6.2f} {float(r['speedup_mediana']):>6.3f} "
              f"{float(r['speedup_min']):>6.3f} {float(r['speedup_max']):>6.3f} "
              f"{float(r['eficiencia_mediana']):>6.3f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=_lista_int, default=[2, 3, 4, 6],
                    help="Lista de workers das paralelas (default: 2,3,4,6).")
    ap.add_argument("--ordens", type=_lista_ordens, default=["crescente", "lpt"],
                    help="Ordens de submissão a medir (default: crescente,lpt).")
    ap.add_argument("--reps", type=int, default=5, help="Repetições (suítes) (default: 5).")
    ap.add_argument("--oficial", action="store_true",
                    help="Marca todas as execuções da campanha como oficiais.")
    ap.add_argument("--sem-aquecer", action="store_true",
                    help="Não roda a passada de aquecimento (cache_quente fica indefinido na 1ª suíte).")
    ap.add_argument("--pausa", type=float, default=5.0,
                    help="Segundos de pausa entre execuções (default: 5).")
    ap.add_argument("--obs", default="",
                    help="Observação livre aplicada a todas as execuções.")
    ap.add_argument("--campanha-id", type=UUID, default=None,
                    help="CONTINUA uma campanha existente (mesmo campanha_id) — use após "
                         "interrupção; rode com aquecimento se a máquina reiniciou.")
    args = ap.parse_args()

    if args.reps < 1:
        print("--reps deve ser >= 1", file=sys.stderr)
        return 2

    campanha_id = args.campanha_id or uuid4()
    continuacao = args.campanha_id is not None
    meta = coletar_metadados_maquina()
    ts_ini = datetime.now(timezone.utc)
    # Condição da máquina ANTES de medir: CPU ociosa por 10 s e containers ativos.
    # Vai para o manifesto e para `observacoes` de todas as execuções (auditável).
    print("  medindo CPU ociosa por 10 s antes de começar...")
    _am = AmostradorCpu().iniciar()
    time.sleep(10)
    cpu_ocioso = _am.parar()
    try:
        _ps = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                             capture_output=True, text=True, timeout=20)
        containers = sorted(x for x in _ps.stdout.split() if x) if _ps.returncode == 0 else []
    except Exception:  # docker ausente ou parado: só registra
        containers = []
    print(f"  CPU ociosa: {cpu_ocioso} %   containers: {containers or '(nenhum/indisponível)'}")
    obs_base = (f"[campanha {str(campanha_id)[:8]}] {args.obs}".strip()
                + f" | cpu_ocioso={cpu_ocioso}%"
                + (" | continuacao" if continuacao else ""))
    aquecer = not args.sem_aquecer

    n_por_suite = 1 + len(args.workers) * len(args.ordens)
    print(f"CAMPANHA {campanha_id}  iniciada em {ts_ini.isoformat(timespec='seconds')}")
    print(f"  máquina : {meta['cpu_modelo']} — {meta['cpu_fisicos']} físicos / "
          f"{meta['cpu_logicos']} lógicos, {meta['memoria_total_mb']:.0f} MB")
    print(f"  bateria : sequencial + workers {args.workers} × ordens {args.ordens}"
          f"  → {n_por_suite} execuções por suíte × {args.reps} suítes = {n_por_suite * args.reps}")
    print(f"  oficial : {args.oficial}   aquecimento: {aquecer}   pausa: {args.pausa}s")

    manifesto = {
        "campanha_id": str(campanha_id),
        "continuacao": continuacao,
        "inicio_utc": ts_ini.isoformat(),
        "oficial": args.oficial,
        "workers": args.workers, "ordens": args.ordens, "reps": args.reps,
        "aquecimento": aquecer, "pausa_seg": args.pausa, "obs": args.obs,
        "maquina": meta,
        "cpu_ocioso_percent": cpu_ocioso,
        "containers_ativos": containers,
        "suites": [],
        "aquecimento_execucao_id": None,
    }
    todos_ids: list[int] = []

    # ----- aquecimento (fora das métricas) -----
    if aquecer:
        banner("AQUECIMENTO — sequencial descartado (aquecimento = TRUE, oficial = FALSE)")
        aq_id = seq_mod.rodar_sequencial(
            observacoes=obs_base + " | aquecimento",
            campanha_id=campanha_id, suite_id=uuid4(),
            oficial=False, aquecimento=True, cache_quente=None,
        )
        manifesto["aquecimento_execucao_id"] = aq_id
        pausar(args.pausa)

    # ----- suítes -----
    for rep in range(1, args.reps + 1):
        suite_id = uuid4()
        # Após o aquecimento (ou a partir da 2ª suíte) os arquivos já estão no
        # cache de páginas: declaramos cache_quente = TRUE. Sem aquecimento, a
        # 1ª suíte fica com condição indefinida (None) — não se inventa dado.
        cache_quente: bool | None = True if (aquecer or rep > 1) else None
        ids_suite: dict = {"suite_id": str(suite_id), "rep": rep, "sequencial": None, "paralelas": []}

        banner(f"SUÍTE {rep}/{args.reps} — {suite_id} — SEQUENCIAL (baseline da suíte)")
        seq_id = seq_mod.rodar_sequencial(
            observacoes=obs_base + f" | suite {rep}/{args.reps}",
            campanha_id=campanha_id, suite_id=suite_id,
            oficial=args.oficial, aquecimento=False, cache_quente=cache_quente,
        )
        ids_suite["sequencial"] = seq_id
        todos_ids.append(seq_id)

        conn = conectar()
        try:
            tempos = tempos_por_ano(conn, seq_id)
        finally:
            conn.close()
        pausar(args.pausa)

        for ordem in args.ordens:
            for w in args.workers:
                banner(f"SUÍTE {rep}/{args.reps} — PARALELO workers={w} ordem={ordem}")
                par_id = par_mod.rodar_paralelo(
                    num_workers=w,
                    observacoes=obs_base + f" | suite {rep}/{args.reps}",
                    ordem=ordem, tempos_base=tempos,
                    campanha_id=campanha_id, suite_id=suite_id,
                    oficial=args.oficial, aquecimento=False,
                    cache_quente=True,  # o sequencial da própria suíte acabou de ler tudo
                )
                ids_suite["paralelas"].append({"id": par_id, "workers": w, "ordem": ordem})
                todos_ids.append(par_id)
                pausar(args.pausa)

        manifesto["suites"].append(ids_suite)

    # ----- resumo da campanha -----
    banner("RESUMO DA CAMPANHA (v_enade_time_benchmark_resumo)")
    print("Cada paralela é pareada com o sequencial da PRÓPRIA suíte; "
          "mediana/mín/máx/IQR sobre as suítes.\n")
    conn = conectar()
    try:
        resumo = consultar_resumo(conn, campanha_id)
    finally:
        conn.close()
    imprimir_resumo(resumo)

    manifesto["fim_utc"] = datetime.now(timezone.utc).isoformat()
    manifesto["execucao_ids"] = todos_ids
    pasta = RAIZ / "backups" / "campanhas"
    pasta.mkdir(parents=True, exist_ok=True)
    sufixo = f"-cont-{ts_ini.strftime('%Y%m%d_%H%M%S')}" if continuacao else ""
    caminho = pasta / f"{campanha_id}{sufixo}.json"
    caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1, default=str),
                       encoding="utf-8")

    print(f"\nIDs gerados nesta campanha: {todos_ids}")
    print(f"Manifesto: {caminho.relative_to(RAIZ).as_posix()}")
    print("\nPara inspecionar manualmente:")
    print("  psql -h localhost -U enade_user -d enade_db")
    print(f"  SELECT * FROM v_enade_time_benchmark_resumo WHERE campanha_id = '{campanha_id}' "
          f"ORDER BY num_workers, ordem_submissao;")
    return 0


if __name__ == "__main__":
    freeze_support()  # obrigatório no Windows
    sys.exit(main())
