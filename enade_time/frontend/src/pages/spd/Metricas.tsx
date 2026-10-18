import { useState } from "react";

import { MetricasTable } from "@/components/tables/MetricasTable";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { useMetricas } from "@/hooks/useBenchmark";

export default function SpdMetricas() {
  const [apenasValidas, setApenasValidas] = useState(true);
  const q = useMetricas(apenasValidas);

  return (
    <Card>
      <CardHeader
        title="Métricas detalhadas (view v_benchmark_metricas)"
        description="Uma linha por execução paralela. Speedup e eficiência são calculados na view — definição única do sistema — pareando cada paralela com o sequencial da própria suíte (badge 'mesma suíte'); execuções antigas, anteriores ao conceito de suíte, usam o sequencial imediatamente anterior no tempo (badge 'temporal'). A coluna Baseline mostra qual execução sequencial foi usada."
        action={
          <label className="flex items-center gap-2 text-xs text-academia-700">
            <input
              type="checkbox"
              checked={!apenasValidas}
              onChange={(e) => setApenasValidas(!e.target.checked)}
            />
            Mostrar execuções ocultas
          </label>
        }
      />
      <QueryBoundary query={q} isEmpty={(d) => d.length === 0}>
        {(rows) => <MetricasTable data={rows} />}
      </QueryBoundary>
    </Card>
  );
}
