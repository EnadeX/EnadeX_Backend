import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { ROTULO_ORDEM } from "@/lib/benchmark";
import {
  formatDateTime,
  formatDecimal,
  formatInt,
  formatSeconds,
  formatThroughput,
} from "@/lib/format";
import type { BenchmarkExecucao } from "@/types/api";

function curto(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : "—";
}

function mb(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  return `${formatDecimal(bytes / 1_000_000, 2)} MB`;
}

export function ExecucoesTable({ data }: { data: BenchmarkExecucao[] }) {
  return (
    <div className="overflow-auto card p-0">
      <table className="min-w-full text-sm">
        <thead className="bg-academia-100 text-academia-700">
          <tr>
            <th className="px-3 py-2 text-left font-medium">ID</th>
            <th className="px-3 py-2 text-left font-medium">Início</th>
            <th className="px-3 py-2 text-left font-medium">Modo</th>
            <th className="px-3 py-2 text-right font-medium">Workers</th>
            <th className="px-3 py-2 text-left font-medium">Ordem</th>
            <th className="px-3 py-2 text-right font-medium">Tempo</th>
            <th className="px-3 py-2 text-right font-medium">Linhas</th>
            <th className="px-3 py-2 text-right font-medium">Throughput</th>
            <th className="px-3 py-2 text-right font-medium">CPU méd.</th>
            <th className="px-3 py-2 text-right font-medium">Disco lido</th>
            <th className="px-3 py-2 text-left font-medium">Cache</th>
            <th className="px-3 py-2 text-left font-medium">Campanha</th>
            <th className="px-3 py-2 text-left font-medium">Suíte</th>
            <th className="px-3 py-2 text-right font-medium">Mem. pico</th>
            <th className="px-3 py-2 text-left font-medium">Observações</th>
            <th className="px-3 py-2 text-left font-medium">Etapas</th>
          </tr>
        </thead>
        <tbody>
          {data.map((e) => (
            <tr
              key={e.id}
              className="odd:bg-white even:bg-academia-50/40 border-t border-academia-100"
            >
              <td className="px-3 py-2 font-medium">{e.id}</td>
              <td className="px-3 py-2 whitespace-nowrap">
                {formatDateTime(e.timestamp_inicio)}
              </td>
              <td className="px-3 py-2 whitespace-nowrap">
                <Badge tone={e.modo === "sequencial" ? "neutral" : "info"}>
                  {e.modo}
                </Badge>
                {e.aquecimento && (
                  <>
                    {" "}
                    <Badge tone="warning">aquecimento</Badge>
                  </>
                )}
              </td>
              <td className="px-3 py-2 text-right">{e.num_workers}</td>
              <td className="px-3 py-2">{e.ordem_submissao ? ROTULO_ORDEM[e.ordem_submissao] : "—"}</td>
              <td className="px-3 py-2 text-right">{formatSeconds(e.tempo_total_seg)}</td>
              <td className="px-3 py-2 text-right">{formatInt(e.linhas_processadas)}</td>
              <td className="px-3 py-2 text-right">{formatThroughput(e.throughput_lps)}</td>
              <td className="px-3 py-2 text-right">
                {e.cpu_percent_medio !== null && e.cpu_percent_medio !== undefined
                  ? `${formatDecimal(e.cpu_percent_medio, 2)} %`
                  : "—"}
              </td>
              <td className="px-3 py-2 text-right">{mb(e.disco_bytes_lidos)}</td>
              <td className="px-3 py-2">
                {e.cache_quente === true ? "quente" : e.cache_quente === false ? "frio" : "—"}
              </td>
              <td className="px-3 py-2 whitespace-nowrap font-mono text-xs" title={e.campanha_id ?? ""}>
                {curto(e.campanha_id)}
                {e.oficial && (
                  <>
                    {" "}
                    <Badge tone="success">oficial</Badge>
                  </>
                )}
              </td>
              <td className="px-3 py-2 font-mono text-xs text-academia-600" title={e.suite_id ?? ""}>
                {curto(e.suite_id)}
              </td>
              <td className="px-3 py-2 text-right">
                {e.memoria_pico_mb !== null
                  ? `${formatDecimal(e.memoria_pico_mb, 2)} MB`
                  : "—"}
              </td>
              <td className="px-3 py-2 text-academia-600 max-w-[300px] truncate" title={e.observacoes ?? ""}>
                {e.observacoes ?? "—"}
              </td>
              <td className="px-3 py-2">
                <Link
                  to={`/spd/etapas/${e.id}`}
                  className="text-academia-700 underline hover:text-academia-900"
                >
                  ver etapas
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
