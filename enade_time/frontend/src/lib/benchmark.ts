import type {
  BenchmarkComparativo,
  ComparativoItem,
  OrdemSubmissao,
  ResumoConfiguracao,
} from "@/types/api";

/**
 * Série homogênea para os gráficos do comparativo: pode vir de `resumo[]`
 * (mediana ± mín–máx por configuração, n suítes) ou de `itens[]` (uma execução
 * por barra, como antes da v2). Os gráficos não sabem qual das duas origens
 * alimentou a série — só desenham `erro` quando ele existe.
 */
export interface SerieBenchmark {
  chave: string;
  label: string;
  modo: "sequencial" | "paralelo";
  num_workers: number;
  ordem_submissao: OrdemSubmissao | null;
  n: number;
  /** id da execução (só quando a série vem de `itens[]`) */
  execucao_id: number | null;
  tempo: number;
  tempo_erro: [number, number] | null;
  throughput: number;
  speedup: number | null;
  speedup_erro: [number, number] | null;
  eficiencia: number | null;
  eficiencia_erro: [number, number] | null;
}

export const ROTULO_ORDEM: Record<OrdemSubmissao, string> = {
  crescente: "crescente",
  lpt: "LPT",
};

function erro(
  centro: number | null,
  min: number | null | undefined,
  max: number | null | undefined,
): [number, number] | null {
  if (centro === null || min === null || min === undefined || max === null || max === undefined) {
    return null;
  }
  return [Math.max(0, centro - min), Math.max(0, max - centro)];
}

export function rotuloConfiguracao(
  modo: "sequencial" | "paralelo",
  workers: number,
  ordem: OrdemSubmissao | null | undefined,
): string {
  if (modo === "sequencial") return "Sequencial";
  return ordem ? `${workers}w · ${ROTULO_ORDEM[ordem]}` : `${workers}w`;
}

export function seriesDeResumo(resumo: ResumoConfiguracao[]): SerieBenchmark[] {
  return resumo.map((r) => ({
    chave: `${r.modo}-${r.num_workers}-${r.ordem_submissao ?? "seq"}`,
    label: rotuloConfiguracao(r.modo, r.num_workers, r.ordem_submissao),
    modo: r.modo,
    num_workers: r.num_workers,
    ordem_submissao: r.ordem_submissao,
    n: r.n,
    execucao_id: null,
    tempo: r.tempo_mediana,
    tempo_erro: erro(r.tempo_mediana, r.tempo_min, r.tempo_max),
    throughput: r.throughput_mediana,
    speedup: r.speedup_mediana,
    speedup_erro: erro(r.speedup_mediana, r.speedup_min, r.speedup_max),
    eficiencia: r.eficiencia_mediana,
    eficiencia_erro: erro(r.eficiencia_mediana, r.eficiencia_min, r.eficiencia_max),
  }));
}

export function seriesDeItens(itens: ComparativoItem[]): SerieBenchmark[] {
  return itens.map((i) => ({
    chave: `exec-${i.execucao_id}`,
    label:
      i.modo === "sequencial"
        ? `Sequencial #${i.execucao_id}`
        : `${rotuloConfiguracao(i.modo, i.num_workers, i.ordem_submissao)} #${i.execucao_id}`,
    modo: i.modo,
    num_workers: i.num_workers,
    ordem_submissao: i.ordem_submissao ?? null,
    n: 1,
    execucao_id: i.execucao_id,
    tempo: i.tempo_total_seg,
    tempo_erro: null,
    throughput: i.throughput_lps,
    speedup: i.speedup,
    speedup_erro: null,
    eficiencia: i.eficiencia,
    eficiencia_erro: null,
  }));
}

/** Prefere o agregado da campanha; cai para execuções individuais no banco legado. */
export function seriesDoComparativo(data: BenchmarkComparativo): {
  series: SerieBenchmark[];
  agregado: boolean;
} {
  if (data.resumo && data.resumo.length > 0) {
    return { series: seriesDeResumo(data.resumo), agregado: true };
  }
  return { series: seriesDeItens(data.itens), agregado: false };
}

export function melhorSerie(series: SerieBenchmark[]): SerieBenchmark | null {
  return series
    .filter((s) => s.modo === "paralelo" && s.speedup !== null)
    .reduce<SerieBenchmark | null>(
      (best, cur) =>
        best === null || (cur.speedup ?? 0) > (best.speedup ?? 0) ? cur : best,
      null,
    );
}

/**
 * Métrica de Karp–Flatt: estima a fração sequencial `e` do programa a partir
 * do speedup medido S com p processadores — e = (1/S − 1/p) / (1 − 1/p).
 * Atenção: embute granularidade, escalonamento, contenção e overhead — não é
 * uma seção serial do código.
 */
export function fracaoSerialKarpFlatt(speedup: number, p: number): number | null {
  if (p <= 1 || speedup <= 0) return null;
  const e = (1 / speedup - 1 / p) / (1 - 1 / p);
  return Number.isFinite(e) ? e : null;
}

export function ordensPresentes(series: SerieBenchmark[]): OrdemSubmissao[] {
  const set = new Set<OrdemSubmissao>();
  for (const s of series) if (s.modo === "paralelo" && s.ordem_submissao) set.add(s.ordem_submissao);
  return (["lpt", "crescente"] as OrdemSubmissao[]).filter((o) => set.has(o));
}
