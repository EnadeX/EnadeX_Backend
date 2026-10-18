import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import type { SerieBenchmark } from "@/lib/benchmark";
import { formatThroughput } from "@/lib/format";

function corDaSerie(s: SerieBenchmark): string {
  if (s.modo === "sequencial") return CHART_COLORS.seq;
  return s.ordem_submissao === "crescente" ? CHART_COLORS.paralelo2 : CHART_COLORS.paralelo;
}

export function BarThroughput({ data }: { data: SerieBenchmark[] }) {
  const chart = data.map((s) => ({
    label: s.label,
    throughput: s.throughput,
    cor: corDaSerie(s),
  }));
  const agregado = data.some((s) => s.n > 1);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" stroke="#475569" fontSize={12} />
        <YAxis stroke="#475569" fontSize={12} />
        <Tooltip
          formatter={(v: number) => formatThroughput(v)}
          contentStyle={{ borderRadius: 8 }}
        />
        <Bar dataKey="throughput" name={agregado ? "Throughput (mediana)" : "Throughput"}>
          {chart.map((d, i) => (
            <Cell key={i} fill={d.cor} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
