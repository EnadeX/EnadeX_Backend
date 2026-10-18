import { formatDateTime, formatInt, formatSeconds } from "@/lib/format";
import type { BenchmarkEtapa } from "@/types/api";

export function EtapasTable({ data }: { data: BenchmarkEtapa[] }) {
  return (
    <div className="overflow-auto card p-0">
      <table className="min-w-full text-sm">
        <thead className="bg-academia-100 text-academia-700">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Ano</th>
            <th className="px-3 py-2 text-right font-medium">Tempo (s)</th>
            <th className="px-3 py-2 text-right font-medium">Linhas (arq3)</th>
            <th className="px-3 py-2 text-right font-medium">Worker PID</th>
            <th className="px-3 py-2 text-left font-medium">Início</th>
            <th className="px-3 py-2 text-left font-medium">Fim</th>
          </tr>
        </thead>
        <tbody>
          {data.map((e) => (
            <tr
              key={e.id}
              className="odd:bg-white even:bg-academia-50/40 border-t border-academia-100"
            >
              <td className="px-3 py-2 font-medium">{e.ano}</td>
              <td className="px-3 py-2 text-right">{formatSeconds(e.tempo_seg)}</td>
              <td className="px-3 py-2 text-right">{formatInt(e.linhas_arq3)}</td>
              <td className="px-3 py-2 text-right">{e.worker_pid ?? "—"}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(e.timestamp_inicio)}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(e.timestamp_fim)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
