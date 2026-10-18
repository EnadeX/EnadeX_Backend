"""
Checagem cruzada das métricas do benchmark — Python × views × API.

A definição ÚNICA de speedup/eficiência é a view `v_enade_time_benchmark_metricas`
(pareamento por suíte; temporal só para linhas antigas sem `suite_id`). Este
script recalcula tudo em Python a partir das TABELAS (não das views) e falha
se qualquer número divergir — é a garantia de que a view diz o que o
documento diz que ela diz.

Checagens
  A. v_enade_time_benchmark_metricas: para cada execução paralela, speedup =
     round(t_seq_pareado / t_par, 4) e eficiência = round(speedup / p, 4),
     com o pareamento recalculado em Python (mesma suíte; senão, sequencial
     imediatamente anterior no tempo, sem aquecimento).
  B. v_enade_time_benchmark_resumo: por (campanha, modo, workers, ordem): n, mediana,
     mín, máx, IQR (percentile_cont = interpolação linear) de tempo, mediana
     de throughput, mediana/mín/máx de speedup e eficiência — recalculados
     com numpy sobre as execuções (aquecimento excluído; sequencial = 1,0).
  C. (--api URL) GET /api/benchmark/comparativo e /metricas: os valores
     servidos são exatamente os das views.
  D. (--cruzado) local × Supabase: schema coluna a coluna, md5 linha a linha das tabelas e
     views publicadas, e as garantias de segurança do que o ENADE-Time publica.

Uso
  python scripts/13_validar_metricas.py                       # campanha oficial mais recente
  python scripts/13_validar_metricas.py --campanha <uuid>
  python scripts/13_validar_metricas.py --campanha todas       # todas as campanhas + legado
  python scripts/13_validar_metricas.py --api http://127.0.0.1:8000
  python scripts/13_validar_metricas.py --api http://127.0.0.1:8002 --prefixo /api/enade-time

Saída: relatório por checagem e código de saída 0 (tudo confere) ou 1.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # raiz do EnadeX

from enade_time.etl.bench_db import conectar, ultima_campanha_oficial  # noqa: E402

problemas: list[str] = []


def check(cond: bool, ok: str, falha: str) -> None:
    if cond:
        print(f"  OK   {ok}")
    else:
        print(f"  FAIL {falha}")
        problemas.append(falha)


def r4(x) -> Decimal:
    """Arredondamento igual ao ROUND(x::numeric, 4) do Postgres (half up)."""
    return Decimal(str(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def r2(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def secao(t: str) -> None:
    print("\n" + "-" * 78 + f"\n{t}\n" + "-" * 78)


# ---------------------------------------------------------------------------
# Carga das tabelas (nunca das views)
# ---------------------------------------------------------------------------

def carregar_execucoes(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, modo, num_workers, tempo_total_seg, throughput_lps, timestamp_inicio,
                   campanha_id::text AS campanha_id, suite_id::text AS suite_id,
                   ordem_submissao, oficial, aquecimento
            FROM tbl_enade_time_benchmark_execucao ORDER BY id
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def parear_em_python(execs: list[dict]) -> dict[int, dict | None]:
    """Reproduz a regra da view: mesma suíte; senão o sequencial anterior no tempo."""
    seqs = [e for e in execs if e["modo"] == "sequencial" and not e["aquecimento"]]
    out: dict[int, dict | None] = {}
    for p in execs:
        if p["modo"] != "paralelo":
            continue
        if p["suite_id"] is not None:
            cands = [s for s in seqs if s["suite_id"] == p["suite_id"]]
        else:
            cands = [s for s in seqs if s["timestamp_inicio"] < p["timestamp_inicio"]]
        out[p["id"]] = max(cands, key=lambda s: s["timestamp_inicio"]) if cands else None
    return out


# ---------------------------------------------------------------------------
# A. v_enade_time_benchmark_metricas
# ---------------------------------------------------------------------------

def checar_metricas(conn, execs: list[dict], campanha: str | None) -> dict[int, dict]:
    secao("A) v_enade_time_benchmark_metricas × recálculo em Python")
    pares = parear_em_python(execs)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT execucao_id, tempo_sequencial, tempo_paralelo, speedup, eficiencia,
                   baseline_execucao_id, pareamento, num_workers, campanha_id::text
            FROM v_enade_time_benchmark_metricas
        """)
        cols = [d[0] for d in cur.description]
        view = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}

    por_id = {e["id"]: e for e in execs}
    alvo = [e for e in execs if e["modo"] == "paralelo"
            and (campanha in (None, "todas") or e["campanha_id"] == campanha)]
    check(len(alvo) > 0, f"{len(alvo)} execução(ões) paralela(s) no escopo", "nenhuma execução paralela no escopo")
    n_ok = 0
    for p in alvo:
        v = view.get(p["id"])
        base = pares[p["id"]]
        if v is None:
            check(False, "", f"exec {p['id']} ausente na view")
            continue
        if base is None:
            cond = v["speedup"] is None and v["baseline_execucao_id"] is None
            check(cond, f"exec {p['id']}: sem baseline (NULL) como esperado",
                  f"exec {p['id']}: Python não achou baseline, view devolveu {v['baseline_execucao_id']}")
            continue
        s_py = r4(Decimal(str(base["tempo_total_seg"])) / Decimal(str(p["tempo_total_seg"])))
        e_py = r4(Decimal(str(base["tempo_total_seg"])) / Decimal(str(p["tempo_total_seg"])) / p["num_workers"])
        pare_py = "suite" if p["suite_id"] is not None else "temporal"
        cond = (v["baseline_execucao_id"] == base["id"]
                and Decimal(str(v["speedup"])) == s_py
                and Decimal(str(v["eficiencia"])) == e_py
                and v["pareamento"] == pare_py)
        if cond:
            n_ok += 1
        else:
            check(False, "", f"exec {p['id']}: view (base {v['baseline_execucao_id']}, S {v['speedup']}, "
                             f"E {v['eficiencia']}, {v['pareamento']}) × Python (base {base['id']}, "
                             f"S {s_py}, E {e_py}, {pare_py})")
    check(n_ok == len([p for p in alvo if pares[p['id']] is not None]),
          f"{n_ok} execução(ões) paralela(s) com speedup/eficiência/pareamento idênticos",
          "há execuções com divergência entre view e Python")
    return view


# ---------------------------------------------------------------------------
# B. v_enade_time_benchmark_resumo
# ---------------------------------------------------------------------------

def checar_resumo(conn, execs: list[dict], view: dict[int, dict], campanha: str | None) -> None:
    secao("B) v_enade_time_benchmark_resumo × numpy")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT campanha_id::text, modo, num_workers, ordem_submissao, n,
                   tempo_mediana, tempo_min, tempo_max, tempo_iqr, throughput_mediana,
                   speedup_mediana, speedup_min, speedup_max,
                   eficiencia_mediana, eficiencia_min, eficiencia_max
            FROM v_enade_time_benchmark_resumo
        """)
        cols = [d[0] for d in cur.description]
        resumo = [dict(zip(cols, r)) for r in cur.fetchall()]

    if campanha not in (None, "todas"):
        resumo = [r for r in resumo if r["campanha_id"] == campanha]
    check(len(resumo) > 0, f"{len(resumo)} configuração(ões) no resumo", "resumo vazio no escopo")

    grupos: dict[tuple, list[dict]] = {}
    for e in execs:
        if e["campanha_id"] is None or e["aquecimento"]:
            continue
        if campanha not in (None, "todas") and e["campanha_id"] != campanha:
            continue
        ordem = None if e["modo"] == "sequencial" else e["ordem_submissao"]
        grupos.setdefault((e["campanha_id"], e["modo"], e["num_workers"], ordem), []).append(e)

    check(len(grupos) == len(resumo),
          f"{len(grupos)} grupo(s) em Python == {len(resumo)} linha(s) na view",
          f"{len(grupos)} grupo(s) em Python != {len(resumo)} linha(s) na view")

    for r in resumo:
        chave = (r["campanha_id"], r["modo"], r["num_workers"], r["ordem_submissao"])
        g = grupos.get(chave)
        if not g:
            check(False, "", f"grupo {chave} existe na view mas não nas tabelas")
            continue
        t = np.array([float(e["tempo_total_seg"]) for e in g])
        thr = np.array([float(e["throughput_lps"]) for e in g])
        if r["modo"] == "sequencial":
            s = np.ones(len(g)); ef = np.ones(len(g))
        else:
            s = np.array([float(view[e["id"]]["speedup"]) for e in g])
            ef = np.array([float(view[e["id"]]["eficiencia"]) for e in g])
        esperado = {
            "n": len(g),
            "tempo_mediana": r4(np.percentile(t, 50)),
            "tempo_min": Decimal(str(r["tempo_min"])) == Decimal(str(t.min())) and Decimal(str(r["tempo_min"])),
            "tempo_max": Decimal(str(t.max())),
            "tempo_iqr": r4(np.percentile(t, 75) - np.percentile(t, 25)),
            "throughput_mediana": r2(np.percentile(thr, 50)),
            "speedup_mediana": r4(np.percentile(s, 50)),
            "speedup_min": r4(s.min()),
            "speedup_max": r4(s.max()),
            "eficiencia_mediana": r4(np.percentile(ef, 50)),
            "eficiencia_min": r4(ef.min()),
            "eficiencia_max": r4(ef.max()),
        }
        difs = []
        for k, esp in esperado.items():
            obt = r[k]
            if k == "n":
                if int(obt) != esp:
                    difs.append(f"{k}: view {obt} × py {esp}")
            elif k in ("tempo_min", "tempo_max"):
                if Decimal(str(obt)) != Decimal(str(t.min() if k == "tempo_min" else t.max())):
                    difs.append(f"{k}: view {obt} × py {t.min() if k == 'tempo_min' else t.max()}")
            else:
                if r4(obt) != r4(esp) and not (k == "throughput_mediana" and r2(obt) == esp):
                    difs.append(f"{k}: view {obt} × py {esp}")
        rot = f"{r['modo']} w={r['num_workers']} ordem={r['ordem_submissao'] or '-'} (campanha {r['campanha_id'][:8]})"
        check(not difs, f"{rot}: n={r['n']} mediana/min/max/IQR/speedup/eficiência conferem",
              f"{rot}: " + "; ".join(difs))


# ---------------------------------------------------------------------------
# C. API
# ---------------------------------------------------------------------------

def _get(url: str):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def checar_api(base: str, view: dict[int, dict], conn, campanha: str | None, prefixo: str = "/api") -> None:
    secao(f"C) API em {base}")
    try:
        params = f"?campanha_id={campanha}" if campanha not in (None, "todas") else ""
        comp = _get(f"{base}{prefixo}/benchmark/comparativo{params}")
        mets = _get(f"{base}{prefixo}/benchmark/metricas{params}")
    except (urllib.error.URLError, OSError) as e:
        check(False, "", f"API indisponível: {e}")
        return

    difs = 0
    for i in comp["itens"]:
        if i["modo"] != "paralelo":
            continue
        v = view.get(i["execucao_id"])
        if v is None or v["speedup"] is None:
            continue
        if r4(i["speedup"]) != r4(v["speedup"]) or r4(i["eficiencia"]) != r4(v["eficiencia"]):
            difs += 1
            print(f"  DIFF exec {i['execucao_id']}: API S={i['speedup']} E={i['eficiencia']} × view S={v['speedup']} E={v['eficiencia']}")
    check(difs == 0, f"comparativo.itens ({len(comp['itens'])}) idênticos à view",
          f"{difs} item(ns) do comparativo divergem da view")

    difs = 0
    for m in mets:
        v = view.get(m["execucao_id"])
        if v is None:
            difs += 1; continue
        if (v["speedup"] is None) != (m["speedup"] is None) or (
            v["speedup"] is not None and r4(m["speedup"]) != r4(v["speedup"])):
            difs += 1
    check(difs == 0, f"/metricas ({len(mets)}) idênticas à view", f"{difs} linha(s) de /metricas divergem")

    if comp.get("campanha_id"):
        with conn.cursor() as cur:
            cur.execute("SELECT modo, num_workers, ordem_submissao, speedup_mediana, tempo_mediana "
                        "FROM v_enade_time_benchmark_resumo WHERE campanha_id = %s", (comp["campanha_id"],))
            vr = {(r[0], r[1], r[2]): (r[3], r[4]) for r in cur.fetchall()}
        difs = 0
        for r in comp["resumo"]:
            k = (r["modo"], r["num_workers"], r["ordem_submissao"])
            if k not in vr or r4(r["tempo_mediana"]) != r4(vr[k][1]) or (
                vr[k][0] is not None and r4(r["speedup_mediana"]) != r4(vr[k][0])):
                difs += 1
        check(difs == 0 and len(comp["resumo"]) == len(vr),
              f"comparativo.resumo ({len(comp['resumo'])}) idêntico a v_enade_time_benchmark_resumo",
              f"comparativo.resumo diverge de v_enade_time_benchmark_resumo ({difs} dif., {len(comp['resumo'])} × {len(vr)})")


def checar_cruzado() -> None:
    """D. Banco local × Supabase: o que foi publicado é exatamente o que está no instrumento."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "publicar_supabase", Path(__file__).resolve().parent / "12_publicar_supabase.py")
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    from psycopg2 import sql

    print("\n" + "-" * 78 + "\nD) Local × Supabase\n" + "-" * 78)
    local, remoto = pub.conectar_local(), pub.conectar_remoto()
    try:
        lc, rc = local.cursor(), remoto.cursor()

        # 1. schema: mesmas colunas, tipos e anulabilidade em cada tabela
        sql_cols = """SELECT column_name, data_type, coalesce(character_maximum_length, 0),
                             coalesce(numeric_precision, 0), coalesce(numeric_scale, 0), is_nullable
                      FROM information_schema.columns
                      WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position"""
        for tabela, _ in pub.PUBLICADAS + [(pub.TABELA_LOG, [])]:
            lc.execute(sql_cols, (tabela,))
            rc.execute(sql_cols, (tabela,))
            a, b = lc.fetchall(), rc.fetchall()
            check(a == b and len(a) > 0, f"schema de {tabela}: {len(a)} colunas iguais",
                  f"schema de {tabela} diverge: local {[c[0] for c in a if c not in b]} × nuvem {[c[0] for c in b if c not in a]}")

        # 2. conteúdo: contagem e md5 linha a linha
        for tabela, _ in pub.PUBLICADAS:
            n_l, h_l = pub._md5_tabela(lc, tabela)
            n_r, h_r = pub._md5_tabela(rc, tabela)
            check((n_l, h_l) == (n_r, h_r), f"{tabela}: {n_l} linhas, md5 {h_l[:10]} igual nos dois bancos",
                  f"{tabela} diverge: local {n_l} linhas md5 {h_l[:10]} × nuvem {n_r} linhas md5 {h_r[:10]}")

        # 3. views: mesmo resultado, linha a linha
        ordem_views = {
            "v_enade_time_benchmark_metricas": "execucao_id",
            "v_enade_time_benchmark_resumo": "campanha_id, modo, num_workers, ordem_submissao NULLS FIRST",
            "v_enade_time_curso_ano": '"NU_ANO", "CO_CURSO"',
        }
        for view, ordem in ordem_views.items():
            # subselect ordenado: a ordem dos resultados é a das colunas da view, igual nos dois bancos
            consulta = sql.SQL(
                "SELECT count(*), coalesce(md5(string_agg(x::text, '|')), '') "
                "FROM (SELECT * FROM {} ORDER BY " + ordem + ") x"
            ).format(sql.Identifier("public", view))
            lc.execute(consulta)
            rc.execute(consulta)
            a, b = lc.fetchone(), rc.fetchone()
            check(a == b, f"{view}: {a[0]} linhas, resultado idêntico nos dois bancos",
                  f"{view} diverge: local {a} × nuvem {b}")

        # 4. a unidade analítica
        rc.execute('SELECT count(*) FROM public.v_enade_time_curso_ano')
        check(rc.fetchone()[0] == 582, "v_enade_time_curso_ano na nuvem tem 582 linhas (curso-ano)",
              "v_enade_time_curso_ano na nuvem não tem 582 linhas")

        # 5. segurança do que o ENADE-Time publica
        todas = [t for t, _ in pub.PUBLICADAS] + [pub.TABELA_LOG]
        rc.execute("SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace "
                   "AND relname = ANY(%s) AND NOT relrowsecurity", (todas,))
        sem_rls = [r[0] for r in rc.fetchall()]
        check(not sem_rls, "RLS ligada em todas as tabelas do ENADE-Time", f"sem RLS: {sem_rls}")
        rc.execute("""SELECT t, p FROM unnest(%s::text[]) t, unnest(ARRAY['INSERT','UPDATE','DELETE','TRUNCATE']) p
                      WHERE has_table_privilege('anon', 'public.' || t, p)
                         OR has_table_privilege('authenticated', 'public.' || t, p)""", (todas,))
        escrita = rc.fetchall()
        check(not escrita, "anon/authenticated sem permissão de escrita nas tabelas do ENADE-Time",
              f"permissões de escrita abertas: {escrita}")
        rc.execute("""SELECT c.relname FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace
                      AND c.relname = ANY(%s)
                      AND NOT coalesce(c.reloptions @> ARRAY['security_invoker=true'], false)""",
                   ([v for v in ordem_views],))
        sem_invoker = [r[0] for r in rc.fetchall()]
        check(not sem_invoker, "views com security_invoker = true", f"sem security_invoker: {sem_invoker}")
        rc.execute("""SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb
                      FROM pg_roles WHERE rolname = %s""", (pub.PAPEL_LEITOR,))
        linha = rc.fetchone()
        check(linha is not None and not linha[0], f"papel {pub.PAPEL_LEITOR} existe e não tem privilégios extras",
              f"papel {pub.PAPEL_LEITOR} ausente ou com privilégios demais")

        # 6. aviso, fora do escopo do ENADE-Time (não falha): a RPC aberta do projeto
        rc.execute("""SELECT bool_or(has_function_privilege('anon', p.oid, 'EXECUTE'))
                      FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.proname = 'truncar_tabela'""")
        aberta = rc.fetchone()[0]
        if aberta:
            print("  AVISO (fora do escopo do ENADE-Time, não reprova): a RPC public.truncar_tabela ainda é "
                  "executável por anon/authenticated e esvazia qualquer tabela do projeto, inclusive as do "
                  "ENADE-Time. Correção a cargo do líder — ver docs/COMUNICADO_SEGURANCA.md.")
        elif aberta is False:
            print("  OK   RPC truncar_tabela não é executável por anon/authenticated")
    finally:
        local.rollback()
        remoto.rollback()
        local.close()
        remoto.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campanha", default="oficial",
                    help="'oficial' (padrão), 'todas' ou um uuid.")
    ap.add_argument("--api", default=None, help="Base URL da API para a checagem C (ex.: http://127.0.0.1:8000).")
    ap.add_argument("--prefixo", default="/api",
                    help="Prefixo das rotas: /api (API legada) ou /api/enade-time (router do ecossistema).")
    ap.add_argument("--cruzado", action="store_true",
                    help="Checagem D: banco local × Supabase (precisa de SUPABASE_DB_PASSWORD).")
    args = ap.parse_args()

    conn = conectar()
    try:
        campanha: str | None
        if args.campanha == "oficial":
            campanha = ultima_campanha_oficial(conn)
            if campanha is None:
                print("Nenhuma campanha oficial no banco; validando TODAS as execuções (legado).")
                campanha = "todas"
        else:
            campanha = args.campanha
        print(f"Escopo: campanha = {campanha}")

        execs = carregar_execucoes(conn)
        view = checar_metricas(conn, execs, campanha)
        if any(e["campanha_id"] for e in execs):
            checar_resumo(conn, execs, view, campanha)
        else:
            print("\n(B) pulada: não há campanhas no banco.")
        if args.api:
            checar_api(args.api.rstrip("/"), view, conn, campanha, args.prefixo.rstrip("/"))
        if args.cruzado:
            checar_cruzado()
    finally:
        conn.close()

    print("\n" + "=" * 78)
    if problemas:
        print(f"MÉTRICAS COM DIVERGÊNCIA ({len(problemas)}):")
        for p in problemas:
            print("  -", p)
        return 1
    print("MÉTRICAS VALIDADAS: Python, views" + (" e API" if args.api else "")
          + (" e Supabase" if args.cruzado else "") + " concordam.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
