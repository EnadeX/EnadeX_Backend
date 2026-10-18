import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ErrorBar,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import type { SerieBenchmark } from "@/lib/benchmark";
import { formatSpeedup } from "@/lib/format";

export function BarSpeedup({ data }: { data: SerieBenchmark[] }) {
  const paralelos = data.filter((s) => s.modo === "paralelo" && s.speedup !== null);
  const chart = paralelos.map((s) => ({
    label: s.label,
    speedup: s.speedup ?? 0,
    erro: s.speedup_erro ?? undefined,
    workers: s.num_workers,
    cor: s.ordem_submissao === "crescente" ? CHART_COLORS.paralelo2 : CHART_COLORS.paralelo,
  }));
  const temErro = chart.some((c) => c.erro !== undefined);
  const maxIdeal = Math.max(...chart.map((c) => c.workers), 1);
  const maxObs = Math.max(...chart.map((c) => c.speedup + (c.erro?.[1] ?? 0)), 1);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" stroke="#475569" fontSize={12} />
        <YAxis
          stroke="#475569"
          fontSize={12}
          domain={[0, Math.max(Math.min(maxIdeal, 8) + 0.5, maxObs + 0.5, 2)]}
        />
        <Tooltip
          formatter={(v: number) => formatSpeedup(v)}
          contentStyle={{ borderRadius: 8 }}
        />
        <ReferenceLine
          y={1}
          stroke={CHART_COLORS.alert}
          strokeDasharray="4 4"
          label={{ value: "sem ganho (1×)", position: "right", fontSize: 10, fill: CHART_COLORS.alert }}
        />
        <Bar dataKey="speedup" name={temErro ? "Speedup (mediana; barra = mín–máx)" : "Speedup"}>
          {chart.map((d, i) => (
            <Cell key={i} fill={d.cor} />
          ))}
          {temErro && (
            <ErrorBar dataKey="erro" width={6} strokeWidth={1.5} stroke="#0f172a" direction="y" />
          )}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
