"""
Regressão de contrato da API contra os "golden JSONs" capturados na Fase 0
(backups/golden/, gerados ANTES de qualquer mudança da migração).

Semântica ADITIVA: toda chave presente no golden precisa existir na resposta
atual com o mesmo valor; chaves novas na resposta atual são permitidas.
Listas são comparadas item a item; em rotas de histórico de benchmark
(`/benchmark/execucoes`, `/benchmark/metricas`) a lista atual pode ser MAIOR
(novas execuções são esperadas) — os itens do golden têm de aparecer no
prefixo, na mesma ordem (ORDER BY id).

Exceções documentadas (reportadas, mas não falham): `/benchmark/comparativo`
(a correção do baseline muda os números de propósito — DESIGN_LOG D13), `/health`
(versão da API) e `/analises/resumo-ies` com `min_cursos` (o filtro passou a contar
cursos distintos, e não inscrições, como o nome sempre disse — DESIGN_LOG D16).

Uso:
  python tools/diff_golden.py --base http://127.0.0.1:8010
  python tools/diff_golden.py --base http://127.0.0.1:8002 --prefixo /api/enade-time   # Fase 5
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EXCECOES = ("benchmark/comparativo", "health", "min_cursos")
LISTAS_CRESCEM = ("benchmark/execucoes", "benchmark/metricas")


def get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "null")


def diff(golden, atual, caminho: str, pode_crescer: bool, out: list[str]) -> None:
    if isinstance(golden, dict):
        if not isinstance(atual, dict):
            out.append(f"{caminho}: golden é objeto, atual é {type(atual).__name__}")
            return
        for k, v in golden.items():
            if k not in atual:
                out.append(f"{caminho}.{k}: ausente na resposta atual")
            else:
                diff(v, atual[k], f"{caminho}.{k}", pode_crescer, out)
    elif isinstance(golden, list):
        if not isinstance(atual, list):
            out.append(f"{caminho}: golden é lista, atual é {type(atual).__name__}")
            return
        if len(atual) < len(golden) or (len(atual) != len(golden) and not pode_crescer):
            out.append(f"{caminho}: tamanho {len(golden)} (golden) × {len(atual)} (atual)")
        for i, (g, a) in enumerate(zip(golden, atual)):
            diff(g, a, f"{caminho}[{i}]", pode_crescer, out)
    else:
        iguais = golden == atual
        if not iguais and isinstance(golden, (int, float)) and isinstance(atual, (int, float)):
            iguais = abs(float(golden) - float(atual)) <= 1e-9
        if not iguais:
            out.append(f"{caminho}: {golden!r} → {atual!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="ex.: http://127.0.0.1:8010")
    ap.add_argument("--golden", default=str(RAIZ / "backups" / "golden"),
                help="pasta dos golden JSONs (padrão: enade_time/backups/golden; na Fase 2, aponte para o repositório antigo)")
    ap.add_argument("--prefixo", default="/api",
                    help="prefixo atual das rotas (golden foi capturado com /api)")
    ap.add_argument("--max-difs", type=int, default=6)
    args = ap.parse_args()

    pasta = Path(args.golden)
    manifest = json.loads((pasta / "_manifest.json").read_text(encoding="utf-8"))
    print(f"golden capturado em {manifest.get('capturado_em')} (commit {manifest.get('commit')}); "
          f"{len(manifest['rotas'])} rotas; alvo {args.base}{args.prefixo}")

    falhas = 0
    excecoes = 0
    for item in manifest["rotas"]:
        rota_golden = item["rota"]
        rota_atual = rota_golden.replace("/api", args.prefixo, 1)
        g = json.loads((pasta / item["arquivo"]).read_text(encoding="utf-8"))
        try:
            st, body = get(args.base.rstrip("/") + rota_atual)
        except (urllib.error.URLError, OSError) as e:
            print(f"ERRO {rota_atual}: {e}")
            falhas += 1
            continue
        difs: list[str] = []
        if st != g["status"]:
            difs.append(f"status {g['status']} → {st}")
        diff(g["body"], body, "body", any(x in rota_golden for x in LISTAS_CRESCEM), difs)
        excecao = any(x in rota_golden for x in EXCECOES)
        if not difs:
            print(f"OK    {rota_golden}")
        elif excecao:
            excecoes += 1
            print(f"EXCEÇÃO documentada  {rota_golden}: {len(difs)} diferença(s) (esperado)")
            for d in difs[: args.max_difs]:
                print(f"        · {d}")
        else:
            falhas += 1
            print(f"DIFF  {rota_golden}: {len(difs)} diferença(s)")
            for d in difs[: args.max_difs]:
                print(f"        · {d}")

    print(f"\n{len(manifest['rotas'])} rotas: {len(manifest['rotas']) - falhas - excecoes} iguais, "
          f"{excecoes} exceções documentadas, {falhas} regressões")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
