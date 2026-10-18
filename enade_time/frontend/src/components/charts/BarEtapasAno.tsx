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
import { formatSeconds } from "@/lib/format";
import type { BenchmarkEtapa } from "@/types/api";

export function BarEtapasAno({ data }: { data: BenchmarkEtapa[] }) {
  const workersUnicos = Array.from(
    new Set(data.map((d) => d.worker_pid ?? 0)),
  );
  const cores = [CHART_COLORS.paralelo, CHART_COLORS.paralelo2, CHART_COLORS.warn, CHART_COLORS.ideal];

  const sorted = [...data].sort((a, b) => a.ano - b.ano);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={sorted} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="ano" stroke="#475569" fontSize={12} />
        <YAxis stroke="#475569" fontSize={12} />
        <Tooltip
          formatter={(v: number) => formatSeconds(v)}
          labelFormatter={(l, payload) => {
            const pid = payload?.[0]?.payload?.worker_pid;
            return pid ? `Ano ${l} · worker ${pid}` : `Ano ${l}`;
          }}
          contentStyle={{ borderRadius: 8 }}
        />
        <Bar dataKey="tempo_seg" name="Tempo (s)">
          {sorted.map((d, i) => (
            <Cell
              key={i}
              fill={cores[workersUnicos.indexOf(d.worker_pid ?? 0) % cores.length]}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
