import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ErrorBar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_COLORS } from "@/lib/constants";
import type { SerieBenchmark } from "@/lib/benchmark";
import { formatSeconds } from "@/lib/format";

function corDaSerie(s: SerieBenchmark): string {
  if (s.modo === "sequencial") return CHART_COLORS.seq;
  return s.ordem_submissao === "crescente" ? CHART_COLORS.paralelo2 : CHART_COLORS.paralelo;
}

export function BarTempoExecucao({ data }: { data: SerieBenchmark[] }) {
  const chart = data.map((s) => ({
    label: s.label,
    tempo: s.tempo,
    erro: s.tempo_erro ?? undefined,
    cor: corDaSerie(s),
  }));
  const temErro = chart.some((c) => c.erro !== undefined);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" stroke="#475569" fontSize={12} />
        <YAxis stroke="#475569" fontSize={12} />
        <Tooltip
          formatter={(v: number) => formatSeconds(v)}
          contentStyle={{ borderRadius: 8 }}
        />
        <Bar dataKey="tempo" name={temErro ? "Tempo (mediana; barra = mín–máx)" : "Tempo total"}>
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
