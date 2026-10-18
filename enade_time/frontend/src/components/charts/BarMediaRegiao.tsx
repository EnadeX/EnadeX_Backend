import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import { formatDecimal, formatInt } from "@/lib/format";
import type { ResumoRegiao } from "@/types/api";

export function BarMediaRegiao({ data }: { data: ResumoRegiao[] }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="nome" stroke="#475569" fontSize={12} />
        <YAxis yAxisId="left" stroke="#475569" fontSize={12} domain={[0, 100]} />
        <YAxis
          yAxisId="right"
          orientation="right"
          stroke="#94a3b8"
          fontSize={12}
        />
        <Tooltip
          formatter={(v: number, name) =>
            name === "Total de registros"
              ? formatInt(v)
              : formatDecimal(v, 2)
          }
          contentStyle={{ borderRadius: 8 }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar
          yAxisId="left"
          dataKey="media_geral_ger"
          name="Média NT GER"
          fill={CHART_COLORS.paralelo}
        />
        <Bar
          yAxisId="right"
          dataKey="total_registros"
          name="Total de registros"
          fill={CHART_COLORS.neutral}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
