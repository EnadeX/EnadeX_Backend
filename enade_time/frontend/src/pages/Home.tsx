import {
  Award,
  Calendar,
  Cpu,
  Database,
  Flag,
  Gauge,
  Map,
  Timer,
  Zap,
} from "lucide-react";

import { KpiGrid } from "@/components/cards/KpiGrid";
import { MetricCard } from "@/components/cards/MetricCard";
import { Card, CardHeader } from "@/components/ui/Card";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { PageContainer } from "@/components/layout/PageContainer";
import { Link } from "react-router-dom";

import { useComparativo } from "@/hooks/useBenchmark";
import {
  useResumoAnual,
  useResumoRegiao,
  useResumoUF,
} from "@/hooks/useAnalises";
import { ROTULO_ORDEM, melhorSerie, seriesDoComparativo, type SerieBenchmark } from "@/lib/benchmark";
import {
  formatDecimal,
  formatInt,
  formatPercent,
  formatSeconds,
  formatSpeedup,
} from "@/lib/format";

function dica(s: SerieBenchmark | null, agregado: boolean): string | undefined {
  if (!s) return undefined;
  const ordem = s.ordem_submissao ? ` · ${ROTULO_ORDEM[s.ordem_submissao]}` : "";
  if (agregado) return `${s.num_workers} workers${ordem} · mediana de ${s.n} suítes`;
  return `${s.num_workers} workers${ordem} (#${s.execucao_id})`;
}

export default function Home() {
  const anual = useResumoAnual({});
  const regiao = useResumoRegiao({});
  const uf = useResumoUF({});
  const comparativo = useComparativo(true);

  const totalRegistros =
    anual.data?.reduce((acc, r) => acc + r.total_registros, 0) ?? null;
  const anosCobertos = anual.data?.length ?? null;
  const totalRegioes = regiao.data?.length ?? null;
  const totalUFs = uf.data?.length ?? null;

  const tempoBase = comparativo.data?.tempo_baseline_seg ?? null;
  const { series, agregado } = comparativo.data
    ? seriesDoComparativo(comparativo.data)
    : { series: [] as SerieBenchmark[], agregado: false };
  const paralelos = series.filter((s) => s.modo === "paralelo");
  const melhorSpeedup = melhorSerie(series);
  const melhorEficiencia = paralelos.reduce<SerieBenchmark | null>(
    (best, cur) =>
      cur.eficiencia !== null && (best === null || (cur.eficiencia ?? 0) > (best.eficiencia ?? 0))
        ? cur
        : best,
    null,
  );
  const melhorThroughput = paralelos.reduce<SerieBenchmark | null>(
    (best, cur) => (best === null || cur.throughput > best.throughput ? cur : best),
    null,
  );
  const dicaBaseline = agregado
    ? comparativo.data?.n_suites
      ? `mediana de ${comparativo.data.n_suites} suítes`
      : "mediana da campanha"
    : comparativo.data?.baseline_sequencial_id
    ? `Execução #${comparativo.data.baseline_sequencial_id}`
    : undefined;

  return (
    <PageContainer
      title="Visão Geral"
      description="Indicadores principais do projeto: cobertura dos microdados ENADE (Norte e Nordeste, Computação) e resultados do experimento de processamento paralelo."
    >
      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-academia-600 mb-2">
          Microdados ENADE
        </h3>
        <KpiGrid>
          <MetricCard
            label="Total de registros"
            value={
              anual.isPending
                ? "…"
                : totalRegistros !== null
                ? formatInt(totalRegistros)
                : "—"
            }
            unit="inscrições (582 cursos-ano)"
            icon={Database}
          />
          <MetricCard
            label="Anos analisados"
            value={anual.isPending ? "…" : formatInt(anosCobertos)}
            unit="edições ENADE"
            icon={Calendar}
            hint="2005 a 2021"
          />
          <MetricCard
            label="Regiões cobertas"
            value={regiao.isPending ? "…" : formatInt(totalRegioes)}
            unit="Norte + Nordeste"
            icon={Map}
          />
          <MetricCard
            label="UFs cobertas"
            value={uf.isPending ? "…" : formatInt(totalUFs)}
            unit="estados"
            icon={Flag}
          />
        </KpiGrid>
      </section>

      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-academia-600 mb-2">
          Processamento paralelo (SPD)
        </h3>
        <KpiGrid>
          <MetricCard
            label="Tempo sequencial (baseline)"
            value={formatSeconds(tempoBase)}
            icon={Timer}
            hint={dicaBaseline}
          />
          <MetricCard
            label="Melhor speedup"
            value={formatSpeedup(melhorSpeedup?.speedup ?? null)}
            icon={Zap}
            tone="primary"
            hint={dica(melhorSpeedup, agregado)}
          />
          <MetricCard
            label="Melhor eficiência"
            value={formatPercent(melhorEficiencia?.eficiencia ?? null)}
            icon={Gauge}
            tone="success"
            hint={dica(melhorEficiencia, agregado)}
          />
          <MetricCard
            label="Throughput máximo"
            value={melhorThroughput ? formatDecimal(melhorThroughput.throughput, 2) : "—"}
            unit="linhas/s"
            icon={Cpu}
            tone="warning"
            hint={dica(melhorThroughput, agregado)}
          />
        </KpiGrid>
      </section>

      <Card className="border-emerald-200 bg-emerald-50">
        <div className="flex items-start gap-3">
          <Award className="h-6 w-6 text-emerald-600 shrink-0" aria-hidden />
          <div>
            <h3 className="text-base font-semibold text-emerald-900">
              {melhorSpeedup
                ? `Melhor configuração da ${agregado ? "campanha oficial" : "rodada carregada"}: ${melhorSpeedup.num_workers} workers${
                    melhorSpeedup.ordem_submissao ? ` · ${ROTULO_ORDEM[melhorSpeedup.ordem_submissao]}` : ""
                  }`
                : "Benchmark de processamento paralelo"}
            </h3>
            <p className="text-sm text-emerald-800 mt-1 max-w-3xl">
              {melhorSpeedup ? (
                <>
                  {agregado
                    ? "Na campanha oficial carregada no banco, a configuração com "
                    : "Na rodada de benchmark atualmente carregada no banco, a configuração com "}
                  <strong>{melhorSpeedup.num_workers} workers</strong> obteve o melhor
                  desempenho: speedup {agregado ? "mediano " : ""}de{" "}
                  <strong>{formatSpeedup(melhorSpeedup.speedup)}</strong> e eficiência de{" "}
                  <strong>{formatPercent(melhorSpeedup.eficiencia)}</strong>
                  {agregado ? ` (${melhorSpeedup.n} suítes, cada paralela pareada com o sequencial da própria suíte)` : ""}
                  . A melhor configuração depende da máquina (núcleos físicos, cache, ordem de
                  submissão).{" "}
                </>
              ) : (
                <>
                  A melhor configuração pode variar conforme a rodada (CPU, disco
                  e condições da máquina).{" "}
                </>
              )}
              Consulte{" "}
              <Link className="underline" to="/spd/comparativo">
                Benchmark · Comparativo
              </Link>{" "}
              para ver os resultados carregados no banco.
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Status dos dados carregados"
          description="Carregamento direto da API. Atualizado em tempo real."
        />
        <QueryBoundary
          query={anual}
          isEmpty={(d) => d.length === 0}
          loadingLabel="Carregando resumo anual…"
        >
          {(rows) => (
            <ul className="text-sm grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              {rows.map((r) => (
                <li
                  key={r.nu_ano}
                  className="rounded-md border border-academia-100 px-3 py-2"
                >
                  <div className="text-xs text-academia-500">
                    Edição {r.nu_ano}
                  </div>
                  <div className="font-semibold">{formatInt(r.total_registros)} reg.</div>
                  <div className="text-xs text-academia-600">
                    média {formatDecimal(r.media_geral, 2)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </QueryBoundary>
      </Card>
    </PageContainer>
  );
}
