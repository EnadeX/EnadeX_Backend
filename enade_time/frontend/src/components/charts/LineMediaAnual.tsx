import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import { formatDecimal } from "@/lib/format";
import type { ResumoAnual } from "@/types/api";

export function LineMediaAnual({ data }: { data: ResumoAnual[] }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="nu_ano" stroke="#475569" fontSize={12} />
        <YAxis stroke="#475569" fontSize={12} domain={[0, 100]} />
        <Tooltip
          formatter={(v: number) => formatDecimal(v, 2)}
          labelFormatter={(l) => `Ano ${l}`}
          contentStyle={{ borderRadius: 8 }}
        />
        <Line
          type="monotone"
          dataKey="media_geral_ger"
          name="Média NT GER"
          stroke={CHART_COLORS.paralelo}
          strokeWidth={2.5}
          dot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
