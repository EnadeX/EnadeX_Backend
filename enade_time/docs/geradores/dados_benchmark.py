"""
Dados do benchmark para os geradores de documento e apresentação — TUDO lido
do banco (views `v_enade_time_benchmark_resumo` / `v_enade_time_benchmark_metricas` e tabelas), nada
digitado. `verificar_numeros.py` confere depois que cada número do .docx/.pptx
existe nas views.

Uso típico:
    from dados_benchmark import carregar, br, pct, sx, seg
    d = carregar()            # campanha oficial mais recente
    d["resumo"]               # lista de configurações (dicts com floats)
    d["melhor"]               # configuração paralela de maior speedup mediano
    d["escalonamento"]        # saída de analise_escalonamento.analisar()
    d["historico"]            # rodadas legadas (sem campanha) agrupadas por baseline
    d["bug_baseline"]         # execuções cujo speedup "contra o sequencial mais
                              # recente" difere do pareado (o erro de 21/08)
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]          # enade_time/
RAIZ_ECO = RAIZ.parent          # raiz do EnadeX
if str(RAIZ_ECO) not in sys.path:
    sys.path.insert(0, str(RAIZ_ECO))

from enade_time.etl.bench_db import conectar, ultima_campanha_oficial  # noqa: E402

_spec = importlib.util.spec_from_file_location("analise_escalonamento", AQUI / "analise_escalonamento.py")
analise = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analise)


# ---------------------------------------------------------------------------
# Formatação pt-BR
# ---------------------------------------------------------------------------

def br(v, casas: int = 2) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v, casas: int = 1) -> str:
    return "—" if v is None else f"{br(float(v) * 100, casas)} %"


def sx(v, casas: int = 4) -> str:
    return "—" if v is None else f"{br(v, casas)}×"


def seg(v, casas: int = 2) -> str:
    return "—" if v is None else f"{br(v, casas)} s"


def inteiro(v) -> str:
    return "—" if v is None else br(round(float(v)), 0)


def rotulo(modo: str, workers: int, ordem: str | None) -> str:
    if modo == "sequencial":
        return "Sequencial (1)"
    return f"{workers} workers · {'LPT' if ordem == 'lpt' else 'crescente'}"


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def data_extenso(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _f(v):
    return None if v is None else float(v)


ROTULO_ESTRATEGIA = {
    "copy_local": "COPY no Postgres local",
    "copy_pooler": "COPY pelo Session Pooler (Supabase)",
    "upsert_postgrest": "Upsert em lotes pelo PostgREST (Supabase)",
    "controle_local_sem_estrutura": "Controle: COPY local, sem índices nem FKs",
    "controle_pooler_sem_estrutura": "Controle: COPY pelo pooler, sem índices nem FKs",
    "controle_local_so_indices": "Controle: COPY local, só PK e índices",
    "controle_local_so_fks": "Controle: COPY local, só PK e FKs",
}
ORDEM_ESTRATEGIA = list(ROTULO_ESTRATEGIA)


def carregar_carga(conn) -> dict | None:
    """Eixo de carga (D17): a medição mais recente, lida da view/tabela. None se não houver."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.v_enade_time_benchmark_carga_resumo') IS NOT NULL")
        if not cur.fetchone()[0]:
            return None
        cur.execute("""SELECT carga_id::text FROM v_enade_time_benchmark_carga_resumo
                       GROUP BY carga_id ORDER BY MAX(fim) DESC LIMIT 1""")
        linha = cur.fetchone()
        if linha is None:
            return None
        cid = linha[0]
        cur.execute("""SELECT estrategia, n, tempo_mediana, tempo_min, tempo_max, tempo_iqr,
                              throughput_mediana, rtt_mediana_ms, bytes_payload, linhas_destino,
                              md5_confere, host_destino, rede, inicio, fim
                       FROM v_enade_time_benchmark_carga_resumo WHERE carga_id = %s""", (cid,))
        resumo = {}
        for r in _dicts(cur):
            for k in ("tempo_mediana", "tempo_min", "tempo_max", "tempo_iqr", "throughput_mediana", "rtt_mediana_ms"):
                r[k] = _f(r[k])
            resumo[r["estrategia"]] = r
        cur.execute("""SELECT estrategia, repeticao, tempo_seg, rtt_ms
                       FROM tbl_enade_time_benchmark_carga WHERE carga_id = %s
                       ORDER BY estrategia, repeticao""", (cid,))
        reps = [{"estrategia": r["estrategia"], "repeticao": r["repeticao"],
                 "tempo": _f(r["tempo_seg"]), "rtt": _f(r["rtt_ms"])} for r in _dicts(cur)]
        # as rodadas anteriores (mais recente primeiro): mostram o quanto a medição varia entre rodadas
        cur.execute("""SELECT carga_id::text AS carga_id, estrategia, tempo_mediana
                       FROM v_enade_time_benchmark_carga_resumo WHERE carga_id::text <> %s
                       ORDER BY fim DESC""", (cid,))
        por_rodada: dict[str, dict[str, float]] = {}
        for r in _dicts(cur):
            por_rodada.setdefault(r["carga_id"], {})[r["estrategia"]] = _f(r["tempo_mediana"])
    return {"carga_id": cid, "resumo": resumo, "reps": reps, "anteriores": list(por_rodada.values())}


def tabela_carga(c: dict) -> list[tuple]:
    """Linhas da tabela de resultados, na ordem fixa das estratégias."""
    linhas = []
    for est in ORDEM_ESTRATEGIA:
        r = c["resumo"].get(est)
        if r is None:
            continue
        linhas.append((ROTULO_ESTRATEGIA[est], r["n"], seg(r["tempo_mediana"]),
                       f"{seg(r['tempo_min'])} – {seg(r['tempo_max'])}", seg(r["tempo_iqr"]),
                       f"{inteiro(r['throughput_mediana'])} linhas/s", f"{br(r['rtt_mediana_ms'], 1)} ms"))
    return linhas


def leitura_carga(c: dict) -> list[str]:
    """Parágrafos do eixo de carga, calculados dos dados. Só usam números que existem na tabela
    (medianas, extremos, IQR, repetições individuais), para o verificar_numeros conseguir conferir.
    Não falam em ganho de paralelismo: é custo de publicação."""
    r = c["resumo"]
    pares_ant = [(a["copy_local"], a["copy_pooler"]) for a in (c.get("anteriores") or [])
                 if a.get("copy_local") is not None and a.get("copy_pooler") is not None]
    ref = next(iter(r.values()))
    paragrafos = [
        f"Cada repetição carrega as {inteiro(ref['linhas_destino'])} linhas numa tabela vazia e dedicada "
        f"({inteiro(ref['bytes_payload'])} bytes), com o TRUNCATE por conexão direta fora do tempo medido e o md5 do "
        f"destino conferido contra a tabela fato; {ref['n']} repetições por estratégia, intercaladas, com a rede em "
        f"{ref['rede']}. É custo de publicação, não ganho de paralelismo, e vale para estas condições (rede, RTT e host): "
        f"uma medição situada, não uma propriedade do Supabase."
    ]
    lo, po = r.get("copy_local"), r.get("copy_pooler")
    if lo and po:
        razao = round(po["rtt_mediana_ms"] / lo["rtt_mediana_ms"]) if lo["rtt_mediana_ms"] else None
        texto = (
            f"A mediana do COPY no Postgres local foi {seg(lo['tempo_mediana'])} e a do COPY pelo Session Pooler do "
            f"Supabase, {seg(po['tempo_mediana'])}, com RTT mediano de {br(lo['rtt_mediana_ms'], 1)} ms e "
            f"{br(po['rtt_mediana_ms'], 1)} ms" + (f" (cerca de {razao} vezes maior na nuvem)" if razao else "") + ". "
            f"O IQR foi de {seg(lo['tempo_iqr'])} no local e de {seg(po['tempo_iqr'])} na nuvem.")
        if pares_ant:
            quando = "uma rodada anterior" if len(pares_ant) == 1 else f"{len(pares_ant)} rodadas anteriores"
            lista = "; ".join(f"{seg(a)} e {seg(b)}" for a, b in pares_ant)
            texto += (
                f" Em {quando}, com o mesmo protocolo para estas duas estratégias, as medianas do COPY local e do COPY "
                f"pelo pooler foram {lista}: o nível dos tempos e a distância entre o local e a nuvem mudam de uma rodada "
                f"para a outra com a rede e a carga da máquina, e é por isso que o resultado vale como medição situada.")
        paragrafos.append(texto)
        reps_po = sorted((x for x in c["reps"] if x["estrategia"] == "copy_pooler"), key=lambda x: -x["tempo"])
        maiores_rtt = sorted((x for x in c["reps"] if x["estrategia"] == "copy_pooler"), key=lambda x: -x["rtt"])
        if len(reps_po) >= 2 and reps_po[0]["tempo"] > 1.5 * po["tempo_mediana"]:
            if {x["repeticao"] for x in reps_po[:2]} == {x["repeticao"] for x in maiores_rtt[:2]}:
                paragrafos.append(
                    f"A cauda da nuvem vem da rede: as duas repetições mais lentas ({seg(reps_po[0]['tempo'])} e "
                    f"{seg(reps_po[1]['tempo'])}) foram também as de maior RTT ({br(reps_po[0]['rtt'], 1)} ms e "
                    f"{br(reps_po[1]['rtt'], 1)} ms).")
            else:
                paragrafos.append(
                    f"A cauda da nuvem (a repetição mais lenta levou {seg(reps_po[0]['tempo'])}) não acompanhou o RTT "
                    f"medido antes de cada carga: o RTT não a explica. Pode ser a vazão do enlace durante o envio, que "
                    f"não foi medida.")
    cl, cp = r.get("controle_local_sem_estrutura"), r.get("controle_pooler_sem_estrutura")
    ci, cf = r.get("controle_local_so_indices"), r.get("controle_local_so_fks")
    if cl and lo:
        partes = [f"Os controles localizam o custo. No Postgres local, sem índices nem chaves estrangeiras o mesmo COPY "
                  f"leva {seg(cl['tempo_mediana'])}"]
        if ci and cf:
            partes.append(f"; só com a PK e os índices secundários, {seg(ci['tempo_mediana'])}; só com a PK e as FKs, "
                          f"{seg(cf['tempo_mediana'])}; com tudo, como na tabela fato, {seg(lo['tempo_mediana'])}. "
                          f"Quase todo o tempo é manutenção de estrutura, e dentro dela as chaves estrangeiras pesam "
                          f"muito mais do que os índices.")
        else:
            partes.append(f"; com tudo, como na tabela fato, {seg(lo['tempo_mediana'])}.")
        texto = "".join(partes)
        if cp and po:
            texto += (f" Pelo Session Pooler, mesmo sem estrutura a carga leva {seg(cp['tempo_mediana'])}: esse é o "
                      f"custo de transporte (conexão, TLS e envio do payload) nas condições da medição, e responde por "
                      f"boa parte dos {seg(po['tempo_mediana'])} da carga completa na nuvem.")
        texto += (" Hipótese a testar, não medida aqui: carregar sem as chaves estrangeiras e criá-las depois (a "
                  "validação em bloco evita um gatilho por linha) reduziria o custo de uma republicação.")
        paragrafos.append(texto)
    up = r.get("upsert_postgrest")
    if up:
        texto = (f"O upsert em lotes de 2.000 linhas pelo PostgREST (util_db do grupo, com a chave pública) levou "
                 f"{seg(up['tempo_mediana'])} de mediana, com IQR de {seg(up['tempo_iqr'])} e RTT mediano de "
                 f"{br(up['rtt_mediana_ms'], 1)} ms")
        if po and po["tempo_mediana"]:
            texto += f", cerca de {br(up['tempo_mediana'] / po['tempo_mediana'], 1)} vezes o COPY pelo pooler"
        texto += (". São 13 requisições HTTP em sequência, cada uma com a ida e volta da rede e a manutenção da "
                  "estrutura no servidor; como não há controle sem estrutura para o upsert, estas medições não "
                  "separam uma coisa da outra.")
        paragrafos.append(texto)
        paragrafos.append("Para o md5 bater, as três colunas decimais da fato vão como texto já arredondado a 4 casas. "
                          "Como número, os valores que são empate exato na 5ª casa (12 na base atual) seriam "
                          "arredondados para cima pelo PostgreSQL, enquanto o COPY da etapa 06 (`%.4f` do Python) "
                          "vai para o par: a tabela sairia 0,0001 acima do COPY nessas médias.")
    else:
        paragrafos.append("O upsert em lotes pelo PostgREST (util_db do grupo) não foi medido nesta rodada: exige "
                          "SUPABASE_URL e SUPABASE_KEY públicas na máquina da medição.")
    return paragrafos


def carregar(campanha: str = "oficial") -> dict:
    conn = conectar()
    try:
        cid = ultima_campanha_oficial(conn) if campanha == "oficial" else campanha
        if cid is None:
            raise SystemExit("Nenhuma campanha oficial no banco — rode "
                             "`python scripts/10_rodar_suite_benchmark.py --oficial` primeiro.")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT modo, num_workers, ordem_submissao, n,
                       tempo_mediana, tempo_min, tempo_max, tempo_iqr, throughput_mediana,
                       speedup_mediana, speedup_min, speedup_max,
                       eficiencia_mediana, eficiencia_min, eficiencia_max
                FROM v_enade_time_benchmark_resumo WHERE campanha_id = %s
                ORDER BY num_workers, ordem_submissao NULLS FIRST
            """, (cid,))
            resumo = _dicts(cur)
            for r in resumo:
                for k, v in list(r.items()):
                    if k not in ("modo", "num_workers", "ordem_submissao", "n"):
                        r[k] = _f(v)
                r["rotulo"] = rotulo(r["modo"], r["num_workers"], r["ordem_submissao"])

            cur.execute("""
                SELECT MIN(cpu_fisicos) AS cpu_fisicos, MIN(cpu_logicos) AS cpu_logicos,
                       MIN(cpu_modelo) AS cpu_modelo, bool_and(cache_quente) AS cache_quente,
                       COUNT(DISTINCT suite_id) AS n_suites, COUNT(*) AS n_execucoes,
                       MIN(timestamp_inicio) AS inicio, MAX(timestamp_inicio) AS fim,
                       MIN(observacoes) AS observacoes,
                       ROUND(AVG(cpu_percent_medio), 1) AS cpu_percent_medio,
                       MIN(memoria_pico_mb) AS mem_min, MAX(memoria_pico_mb) AS mem_max
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %s AND NOT aquecimento
            """, (cid,))
            maquina = _dicts(cur)[0]
            m = re.search(r"cpu_ocioso=([\d.]+)%", maquina.get("observacoes") or "")
            maquina["cpu_ocioso"] = float(m.group(1)) if m else None

            # suítes completas × parciais: uma interrupção real (queda da
            # máquina) deixa uma suíte com menos execuções; as linhas gravadas
            # permanecem válidas (pareamento por suíte) e elevam o n de
            # algumas configurações.
            cur.execute("""
                SELECT suite_id::text AS suite_id, COUNT(*) AS n_execs,
                       MIN(timestamp_inicio) AS inicio
                FROM tbl_enade_time_benchmark_execucao
                WHERE campanha_id = %s AND NOT aquecimento
                GROUP BY suite_id ORDER BY MIN(timestamp_inicio)
            """, (cid,))
            suites_info = _dicts(cur)
            _n_cfg = max((int(s["n_execs"]) for s in suites_info), default=0)
            maquina["n_suites"] = len(suites_info)
            maquina["n_suites_completas"] = sum(
                1 for s in suites_info if int(s["n_execs"]) == _n_cfg)
            maquina["suites_parciais"] = [
                {"suite_id": s["suite_id"], "n_execs": int(s["n_execs"]), "inicio": s["inicio"]}
                for s in suites_info if int(s["n_execs"]) != _n_cfg
            ]

            cur.execute("""
                SELECT id, tempo_total_seg, disco_bytes_lidos, cpu_percent_medio
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %s AND aquecimento ORDER BY id
            """, (cid,))
            aquecimento = [{"id": r["id"], "tempo": _f(r["tempo_total_seg"]),
                            "disco_mb": (r["disco_bytes_lidos"] or 0) / 1e6,
                            "cpu": _f(r["cpu_percent_medio"])} for r in _dicts(cur)]

            # execuções quentes: disco e cpu por configuração
            cur.execute("""
                SELECT modo, num_workers, ordem_submissao,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY disco_bytes_lidos) AS disco_med,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY cpu_percent_medio) AS cpu_med
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %s AND NOT aquecimento
                GROUP BY modo, num_workers, ordem_submissao
            """, (cid,))
            instr = {(r["modo"], r["num_workers"], r["ordem_submissao"]):
                     {"disco_mb": (_f(r["disco_med"]) or 0) / 1e6, "cpu": _f(r["cpu_med"])}
                     for r in _dicts(cur)}
            for r in resumo:
                i = instr.get((r["modo"], r["num_workers"], r["ordem_submissao"]), {})
                r["disco_mb"] = i.get("disco_mb")
                r["cpu"] = i.get("cpu")

            # histórico: execuções sem campanha (rodadas de 21/06 e 21/08)
            cur.execute("""
                SELECT e.id, e.modo, e.num_workers, e.tempo_total_seg, e.throughput_lps,
                       e.timestamp_inicio, e.observacoes,
                       m.speedup, m.eficiencia, m.baseline_execucao_id
                FROM tbl_enade_time_benchmark_execucao e
                LEFT JOIN v_enade_time_benchmark_metricas m ON m.execucao_id = e.id
                WHERE e.campanha_id IS NULL ORDER BY e.id
            """)
            legado = _dicts(cur)
            for r in legado:
                for k in ("tempo_total_seg", "throughput_lps", "speedup", "eficiencia"):
                    r[k] = _f(r[k])
            rodadas: dict[int, dict] = {}
            for r in legado:
                if r["modo"] == "sequencial":
                    rodadas[r["id"]] = {"baseline": r, "paralelas": [], "data": r["timestamp_inicio"]}
            for r in legado:
                if r["modo"] == "paralelo" and r["baseline_execucao_id"] in rodadas:
                    rodadas[r["baseline_execucao_id"]]["paralelas"].append(r)
            historico = [rodadas[k] for k in sorted(rodadas)]

            # o erro de 21/08: speedup contra o sequencial mais recente × pareado
            seqs = [r for r in legado if r["modo"] == "sequencial"]
            mais_recente = max(seqs, key=lambda r: r["timestamp_inicio"]) if seqs else None
            bug = []
            if mais_recente:
                for r in legado:
                    if r["modo"] == "paralelo" and r["speedup"] is not None:
                        s_err = mais_recente["tempo_total_seg"] / r["tempo_total_seg"]
                        if abs(s_err - r["speedup"]) > 0.01:
                            bug.append({"exec": r["id"], "workers": r["num_workers"],
                                        "tempo": r["tempo_total_seg"],
                                        "baseline_errado": mais_recente["id"],
                                        "t_errado": mais_recente["tempo_total_seg"],
                                        "s_errado": s_err, "e_errado": s_err / r["num_workers"],
                                        "baseline_certo": r["baseline_execucao_id"],
                                        "s_certo": r["speedup"], "e_certo": r["eficiencia"]})

            cur.execute("""
                SELECT campanha_id::text AS campanha_id, MIN(timestamp_inicio) AS inicio,
                       COUNT(*) FILTER (WHERE NOT aquecimento) AS n, bool_and(oficial) AS oficial,
                       MIN(observacoes) AS observacoes
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id IS NOT NULL AND campanha_id <> %s
                GROUP BY campanha_id ORDER BY 2
            """, (cid,))
            outras = _dicts(cur)

        execs, etapas = analise.carregar(conn, cid, None)
        esc = analise.analisar(execs, etapas)
        carga = carregar_carga(conn)
    finally:
        conn.close()

    paralelos = [r for r in resumo if r["modo"] == "paralelo" and r["speedup_mediana"] is not None]
    melhor = max(paralelos, key=lambda r: r["speedup_mediana"]) if paralelos else None
    seq_row = next((r for r in resumo if r["modo"] == "sequencial"), None)

    def cfg(w, o):
        return next((r for r in resumo if r["modo"] == "paralelo" and r["num_workers"] == w
                     and r["ordem_submissao"] == o), None)

    def esc_cfg(w, o):
        return next((r for r in esc["agregado"] if r["workers"] == w and r["ordem"] == o), None)

    workers = sorted({r["num_workers"] for r in paralelos})
    ordens = [o for o in ("crescente", "lpt") if any(r["ordem_submissao"] == o for r in paralelos)]

    return {
        "campanha_id": cid,
        "resumo": resumo,
        "sequencial": seq_row,
        "paralelos": paralelos,
        "melhor": melhor,
        "workers": workers,
        "ordens": ordens,
        "cfg": cfg,
        "esc_cfg": esc_cfg,
        "maquina": maquina,
        "aquecimento": aquecimento,
        "escalonamento": esc,
        "historico": historico,
        "bug_baseline": bug,
        "outras_campanhas": outras,
        "carga": carga,
        "gerado_em": datetime.now(),
    }


if __name__ == "__main__":
    d = carregar()
    print("campanha", d["campanha_id"], "suítes", d["maquina"]["n_suites"], "execuções", d["maquina"]["n_execucoes"])
    for r in d["resumo"]:
        print(f"  {r['rotulo']:<22} n={r['n']} t={seg(r['tempo_mediana'])} [{seg(r['tempo_min'])}–{seg(r['tempo_max'])}] "
              f"S={sx(r['speedup_mediana'])} E={pct(r['eficiencia_mediana'])} disco={br(r['disco_mb'], 1)} MB cpu={br(r['cpu'], 1)} %")
    print("melhor:", d["melhor"] and d["melhor"]["rotulo"])
    print("hipóteses:", d["escalonamento"]["hipoteses"])
    print("bug baseline:", [(b["exec"], round(b["s_errado"], 4), b["s_certo"]) for b in d["bug_baseline"]])
