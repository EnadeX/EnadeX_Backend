import { Award, Cpu, Info } from "lucide-react";

import { BarSpeedup } from "@/components/charts/BarSpeedup";
import { BarTempoExecucao } from "@/components/charts/BarTempoExecucao";
import { BarThroughput } from "@/components/charts/BarThroughput";
import { LineEficiencia } from "@/components/charts/LineEficiencia";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { useComparativo } from "@/hooks/useBenchmark";
import {
  ROTULO_ORDEM,
  fracaoSerialKarpFlatt,
  melhorSerie,
  ordensPresentes,
  seriesDoComparativo,
  type SerieBenchmark,
} from "@/lib/benchmark";
import { formatInt, formatPercent, formatSeconds, formatSpeedup } from "@/lib/format";
import type { BenchmarkComparativo } from "@/types/api";

function faixa(erro: [number, number] | null, centro: number | null, fmt: (v: number) => string) {
  if (!erro || centro === null) return null;
  return `${fmt(centro - erro[0])} – ${fmt(centro + erro[1])}`;
}

/**
 * Interpretação gerada a partir dos dados realmente carregados no banco.
 * O ponto ótimo de workers varia por máquina/campanha, então nada aqui pode
 * ser fixo no código — senão o texto contradiz os gráficos ao lado.
 */
function Interpretacao({
  data,
  series,
  agregado,
  melhor,
}: {
  data: BenchmarkComparativo;
  series: SerieBenchmark[];
  agregado: boolean;
  melhor: SerieBenchmark | null;
}) {
  const paralelos = series.filter((s) => s.modo === "paralelo");
  if (melhor === null || paralelos.length === 0) {
    return (
      <p className="mt-1">
        Nenhuma execução paralela carregada — sem base para comparar contra o
        baseline sequencial.
      </p>
    );
  }

  const ordens = ordensPresentes(series);
  const workersOrdenados = Array.from(new Set(paralelos.map((s) => s.num_workers))).sort(
    (a, b) => a - b,
  );
  const maxWorkers = workersOrdenados[workersOrdenados.length - 1];
  const escalouAteOFim = melhor.num_workers === maxWorkers;
  const fisicos = data.maquina?.cpu_fisicos ?? null;
  const acimaDosFisicos = fisicos !== null && maxWorkers > fisicos;

  return (
    <>
      <p className="mt-1">
        A melhor configuração desta {agregado ? "campanha" : "rodada"} foi{" "}
        <strong>
          {melhor.num_workers} workers
          {melhor.ordem_submissao ? ` (submissão ${ROTULO_ORDEM[melhor.ordem_submissao]})` : ""}
        </strong>
        {melhor.execucao_id !== null ? ` (execução #${melhor.execucao_id})` : ""}, com speedup{" "}
        {agregado ? "mediano " : ""}de <strong>{formatSpeedup(melhor.speedup)}</strong>
        {faixa(melhor.speedup_erro, melhor.speedup, (v) => formatSpeedup(v)) && (
          <> (mín–máx {faixa(melhor.speedup_erro, melhor.speedup, (v) => formatSpeedup(v))})</>
        )}{" "}
        e eficiência de <strong>{formatPercent(melhor.eficiencia)}</strong>
        {agregado ? ` sobre ${melhor.n} suítes` : ""}.
      </p>

      {escalouAteOFim ? (
        <p className="mt-2">
          O ganho ainda crescia no maior número de workers testado ({maxWorkers}
          ), ou seja, <strong>o ponto de saturação não foi atingido</strong>{" "}
          dentro da faixa medida.
          {acimaDosFisicos && (
            <>
              {" "}
              Note que {maxWorkers} workers já ultrapassa os {fisicos} núcleos físicos
              desta máquina — parte dos processos roda em hyperthreads, e o teto de
              granularidade (6 unidades de trabalho) não cresce mais a partir de 6.
            </>
          )}
        </p>
      ) : (
        <p className="mt-2">
          Aumentar para {maxWorkers} workers <strong>não melhorou</strong> o
          resultado.
          {acimaDosFisicos ? (
            <>
              {" "}
              Com {fisicos} núcleos físicos, {maxWorkers} workers competem por
              hyperthreads; somado ao limite de granularidade (são só 6 unidades de
              trabalho), o teto teórico deixa de subir — e a contenção passa a custar.
            </>
          ) : (
            <>
              {" "}
              O overhead de criação de processos, a serialização entre eles e a
              contenção passaram a superar o ganho de CPU — o platô previsto pela{" "}
              <strong>Lei de Amdahl</strong>.
            </>
          )}
        </p>
      )}

      {ordens.length > 1 && (
        <p className="mt-2">
          Duas ordens de submissão foram medidas: <strong>LPT</strong> (anos em ordem
          decrescente de tempo, Graham 1969) e <strong>crescente</strong> (ordem
          histórica do script). O executor entrega cada ano ao primeiro worker livre,
          então a ordem muda o makespan mesmo sem tocar no código dos workers — a
          diferença entre as duas linhas é perda de <em>escalonamento</em>, não de
          contenção.
        </p>
      )}

      <p className="mt-2">
        Eficiência abaixo de 100% indica tempo não paralelizável. Estimativa da{" "}
        <strong>fração sequencial (métrica de Karp–Flatt)</strong> por configuração —
        ela embute granularidade, escalonamento, contenção e overhead, não uma seção
        serial do código:
      </p>
      <ul className="mt-1 list-disc pl-5 space-y-0.5">
        {[...paralelos]
          .sort(
            (a, b) =>
              a.num_workers - b.num_workers ||
              (a.ordem_submissao ?? "").localeCompare(b.ordem_submissao ?? ""),
          )
          .map((s) => {
            const serial = s.speedup !== null ? fracaoSerialKarpFlatt(s.speedup, s.num_workers) : null;
            return (
              <li key={s.chave}>
                <strong>{s.label}</strong> — {formatSeconds(s.tempo)}
                {agregado ? ` (mediana de ${s.n})` : ""}, speedup {formatSpeedup(s.speedup)},
                eficiência {formatPercent(s.eficiencia)}
                {serial !== null && <> · fração sequencial estimada {formatPercent(serial)}</>}
              </li>
            );
          })}
      </ul>
    </>
  );
}

export default function SpdComparativo() {
  const q = useComparativo(true);

  return (
    <QueryBoundary query={q} isEmpty={(d) => d.itens.length === 0}>
      {(data) => {
        const { series, agregado } = seriesDoComparativo(data);
        const melhor = melhorSerie(series);
        const maquina = data.maquina ?? null;

        return (
          <>
            {melhor && (
              <Card className="border-emerald-200 bg-emerald-50">
                <div className="flex items-start gap-3">
                  <Award className="h-6 w-6 text-emerald-600 shrink-0" aria-hidden />
                  <div>
                    <h3 className="text-base font-semibold text-emerald-900">
                      Melhor configuração: {melhor.num_workers} workers
                      {melhor.ordem_submissao ? ` · ${ROTULO_ORDEM[melhor.ordem_submissao]}` : ""}
                      {melhor.execucao_id !== null ? ` (#${melhor.execucao_id})` : ""}
                    </h3>
                    <p className="text-sm text-emerald-800 mt-1 max-w-3xl">
                      Speedup {agregado ? "mediano " : ""}de{" "}
                      <strong>{formatSpeedup(melhor.speedup)}</strong> em relação ao baseline
                      sequencial ({agregado ? "mediana " : ""}
                      {formatSeconds(data.tempo_baseline_seg)}), com eficiência de{" "}
                      <strong>{formatPercent(melhor.eficiencia)}</strong>
                      {agregado && data.n_suites ? ` — ${formatInt(data.n_suites)} suítes` : ""}.
                    </p>
                  </div>
                </div>
              </Card>
            )}

            {(maquina || data.campanha_id) && (
              <Card>
                <div className="flex items-start gap-3 text-sm text-academia-800">
                  <Cpu className="h-5 w-5 text-academia-600 shrink-0 mt-0.5" aria-hidden />
                  <div>
                    <span className="font-semibold text-academia-900">Condições de medição.</span>{" "}
                    {maquina?.cpu_modelo ?? "CPU não identificada"}
                    {maquina?.cpu_fisicos !== null && maquina?.cpu_fisicos !== undefined && (
                      <>
                        {" "}
                        — <strong>{maquina.cpu_fisicos} núcleos físicos</strong> /{" "}
                        {maquina.cpu_logicos ?? "?"} lógicos
                      </>
                    )}
                    {maquina?.cache_quente === true && (
                      <>
                        ; <strong>cache de páginas quente</strong> (passada de aquecimento
                        descartada antes da campanha)
                      </>
                    )}
                    {data.campanha_id && (
                      <>
                        ; campanha <code>{data.campanha_id.slice(0, 8)}</code>
                        {data.n_suites ? `, ${data.n_suites} suítes` : ""}
                      </>
                    )}
                    . Cada execução paralela é comparada com o sequencial da própria suíte
                    (definição única em <code>v_benchmark_metricas</code>).
                  </div>
                </div>
              </Card>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader
                  title="Tempo total de execução"
                  description={
                    agregado
                      ? "Mediana por configuração; barra de erro = mín–máx entre suítes (menor é melhor)."
                      : "Sequencial vs. paralelo (menor é melhor)."
                  }
                />
                <BarTempoExecucao data={series} />
              </Card>

              <Card>
                <CardHeader
                  title="Speedup"
                  description="S(p) = T(1) / T(p), pareado por suíte. Linha vermelha marca o limiar sem ganho (1×)."
                />
                <BarSpeedup data={series} />
              </Card>

              <Card>
                <CardHeader
                  title="Eficiência"
                  description="E(p) = S(p) / p. Linha verde marca o ideal (100%); uma linha por ordem de submissão."
                />
                <LineEficiencia data={series} />
              </Card>

              <Card>
                <CardHeader
                  title="Throughput"
                  description={
                    agregado
                      ? "Linhas processadas por segundo — mediana por configuração (maior é melhor)."
                      : "Linhas processadas por segundo (maior é melhor)."
                  }
                />
                <BarThroughput data={series} />
              </Card>
            </div>

            <Card>
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-academia-600 shrink-0 mt-0.5" aria-hidden />
                <div className="text-sm text-academia-800">
                  <h3 className="font-semibold text-academia-900">
                    Interpretação desta {agregado ? "campanha" : "rodada"}
                  </h3>
                  <Interpretacao data={data} series={series} agregado={agregado} melhor={melhor} />
                </div>
              </div>
            </Card>
          </>
        );
      }}
    </QueryBoundary>
  );
}
