import { Badge } from "@/components/ui/Badge";
import { ROTULO_ORDEM } from "@/lib/benchmark";
import {
  formatDateTime,
  formatPercent,
  formatSeconds,
  formatSpeedup,
  formatThroughput,
} from "@/lib/format";
import type { BenchmarkMetrica } from "@/types/api";

function curto(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : "—";
}

export function MetricasTable({ data }: { data: BenchmarkMetrica[] }) {
  return (
    <div className="overflow-auto card p-0">
      <table className="min-w-full text-sm">
        <thead className="bg-academia-100 text-academia-700">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Exec. ID</th>
            <th className="px-3 py-2 text-left font-medium">Início</th>
            <th className="px-3 py-2 text-right font-medium">Workers</th>
            <th className="px-3 py-2 text-left font-medium">Ordem</th>
            <th className="px-3 py-2 text-left font-medium">Baseline</th>
            <th className="px-3 py-2 text-left font-medium">Pareamento</th>
            <th className="px-3 py-2 text-right font-medium">Tempo Seq.</th>
            <th className="px-3 py-2 text-right font-medium">Tempo Par.</th>
            <th className="px-3 py-2 text-right font-medium">Speedup</th>
            <th className="px-3 py-2 text-right font-medium">Eficiência</th>
            <th className="px-3 py-2 text-right font-medium">Thr. Seq.</th>
            <th className="px-3 py-2 text-right font-medium">Thr. Par.</th>
            <th className="px-3 py-2 text-left font-medium">Suíte</th>
          </tr>
        </thead>
        <tbody>
          {data.map((m) => (
            <tr
              key={m.execucao_id}
              className="odd:bg-white even:bg-academia-50/40 border-t border-academia-100"
            >
              <td className="px-3 py-2 font-medium">{m.execucao_id}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(m.timestamp_inicio)}</td>
              <td className="px-3 py-2 text-right">{m.num_workers}</td>
              <td className="px-3 py-2">
                {m.ordem_submissao ? ROTULO_ORDEM[m.ordem_submissao] : "—"}
              </td>
              <td className="px-3 py-2">
                {m.baseline_execucao_id !== null && m.baseline_execucao_id !== undefined
                  ? `#${m.baseline_execucao_id}`
                  : "—"}
              </td>
              <td className="px-3 py-2">
                {m.pareamento ? (
                  <Badge tone={m.pareamento === "suite" ? "success" : "warning"}>
                    {m.pareamento === "suite" ? "mesma suíte" : "temporal"}
                  </Badge>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-3 py-2 text-right">{formatSeconds(m.tempo_sequencial)}</td>
              <td className="px-3 py-2 text-right">{formatSeconds(m.tempo_paralelo)}</td>
              <td className="px-3 py-2 text-right font-semibold">{formatSpeedup(m.speedup)}</td>
              <td className="px-3 py-2 text-right">{formatPercent(m.eficiencia)}</td>
              <td className="px-3 py-2 text-right">{formatThroughput(m.throughput_sequencial)}</td>
              <td className="px-3 py-2 text-right">{formatThroughput(m.throughput_paralelo)}</td>
              <td className="px-3 py-2 font-mono text-xs text-academia-600" title={m.suite_id ?? ""}>
                {curto(m.suite_id)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
