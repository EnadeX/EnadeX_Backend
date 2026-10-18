import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import { ROTULO_ORDEM, type SerieBenchmark } from "@/lib/benchmark";
import { formatPercent } from "@/lib/format";
import type { OrdemSubmissao } from "@/types/api";

/**
 * Eficiência por número de workers. Uma linha por ordem de submissão
 * (LPT × crescente) quando a campanha mediu as duas; no banco legado todas as
 * paralelas são `crescente` (única ordem que o script 09 conhecia).
 */
export function LineEficiencia({ data }: { data: SerieBenchmark[] }) {
  const paralelos = data.filter((s) => s.modo === "paralelo" && s.eficiencia !== null);
  const ordens = (["lpt", "crescente"] as OrdemSubmissao[]).filter((o) =>
    paralelos.some((s) => (s.ordem_submissao ?? "crescente") === o),
  );
  const workers = Array.from(new Set(paralelos.map((s) => s.num_workers))).sort((a, b) => a - b);

  // Uma linha por (workers); colunas = eficiência de cada ordem.
  const chart = workers.map((w) => {
    const row: Record<string, number | null> = { workers: w };
    for (const o of ordens) {
      const s = paralelos.find((p) => p.num_workers === w && (p.ordem_submissao ?? "crescente") === o);
      row[o] = s?.eficiencia ?? null;
    }
    return row;
  });

  const cor: Record<OrdemSubmissao, string> = {
    lpt: CHART_COLORS.paralelo,
    crescente: CHART_COLORS.paralelo2,
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="workers"
          type="number"
          domain={["dataMin", "dataMax"]}
          ticks={workers}
          stroke="#475569"
          fontSize={12}
          label={{
            value: "Número de workers",
            position: "insideBottom",
            offset: -2,
            fontSize: 11,
            fill: "#64748b",
          }}
        />
        <YAxis
          stroke="#475569"
          fontSize={12}
          domain={[0, 1.1]}
          tickFormatter={(v) => formatPercent(v)}
        />
        <Tooltip
          formatter={(v: number) => formatPercent(v)}
          contentStyle={{ borderRadius: 8 }}
        />
        {ordens.length > 1 && <Legend />}
        <ReferenceLine
          y={1}
          stroke={CHART_COLORS.ideal}
          strokeDasharray="4 4"
          label={{
            value: "ideal (100%)",
            position: "right",
            fontSize: 10,
            fill: CHART_COLORS.ideal,
          }}
        />
        {ordens.map((o) => (
          <Line
            key={o}
            type="monotone"
            dataKey={o}
            name={`Eficiência (${ROTULO_ORDEM[o]})`}
            stroke={cor[o]}
            strokeWidth={2.5}
            dot={{ r: 5 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
