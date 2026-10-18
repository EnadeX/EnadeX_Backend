import { useState } from "react";

import { RankingIES } from "@/components/tables/RankingIES";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { useResumoIES } from "@/hooks/useAnalises";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";

export default function EnadePorIES() {
  const { filtros } = useFiltrosUrl();
  const [limit, setLimit] = useState(20);
  const [minCursos, setMinCursos] = useState(1);

  const q = useResumoIES(filtros, limit, minCursos);

  return (
    <Card>
      <CardHeader
        title="Ranking de IES"
        description="IES ordenadas por Nota Geral (NT GER), com filtro mínimo de cursos para reduzir ruído de amostras pequenas."
        action={
          <div className="flex items-end gap-3">
            <label className="text-xs text-academia-700">
              Top N
              <select
                className="select mt-1"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              >
                {[10, 20, 50, 100].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-academia-700">
              Mín. cursos
              <select
                className="select mt-1"
                value={minCursos}
                onChange={(e) => setMinCursos(Number(e.target.value))}
              >
                {[1, 2, 5, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
        }
      />
      <QueryBoundary query={q} isEmpty={(d) => d.length === 0}>
        {(rows) => <RankingIES items={rows} />}
      </QueryBoundary>
    </Card>
  );
}
