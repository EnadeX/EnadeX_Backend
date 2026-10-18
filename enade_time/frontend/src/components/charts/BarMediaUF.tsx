import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import { formatDecimal } from "@/lib/format";
import type { ResumoUF } from "@/types/api";

export function BarMediaUF({ data }: { data: ResumoUF[] }) {
  const sorted = [...data].sort(
    (a, b) => (b.media_geral_ger ?? 0) - (a.media_geral_ger ?? 0),
  );

  return (
    <ResponsiveContainer width="100%" height={Math.max(280, sorted.length * 28)}>
      <BarChart
        data={sorted}
        layout="vertical"
        margin={{ top: 8, right: 16, bottom: 0, left: 12 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis type="number" domain={[0, 100]} stroke="#475569" fontSize={12} />
        <YAxis
          type="category"
          dataKey="sigla"
          stroke="#475569"
          fontSize={12}
          width={50}
        />
        <Tooltip
          formatter={(v: number) => formatDecimal(v, 2)}
          labelFormatter={(l, payload) =>
            payload?.[0]?.payload?.nome ?? String(l)
          }
          contentStyle={{ borderRadius: 8 }}
        />
        <Bar
          dataKey="media_geral_ger"
          name="Média NT GER"
          fill={CHART_COLORS.paralelo}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
