import { BarMediaRegiao } from "@/components/charts/BarMediaRegiao";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { useResumoRegiao } from "@/hooks/useAnalises";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";
import { formatDecimal, formatInt } from "@/lib/format";

export default function EnadeRegional() {
  const { filtros } = useFiltrosUrl();
  const q = useResumoRegiao(filtros);

  return (
    <QueryBoundary query={q} isEmpty={(d) => d.length === 0}>
      {(rows) => (
        <>
          <Card>
            <CardHeader
              title="Média Nota Geral por região"
              description="Comparação Norte vs. Nordeste — médias da Nota Geral (NT GER) e volume de registros."
            />
            <BarMediaRegiao data={rows} />
          </Card>
          <Card>
            <CardHeader title="Detalhamento por região" />
            <table className="min-w-full text-sm">
              <thead className="text-academia-700">
                <tr className="text-left">
                  <th className="px-2 py-2">Região</th>
                  <th className="px-2 py-2 text-right">Registros</th>
                  <th className="px-2 py-2 text-right">Média FG</th>
                  <th className="px-2 py-2 text-right">Mínima FG</th>
                  <th className="px-2 py-2 text-right">Máxima FG</th>
                  <th className="px-2 py-2 text-right">Desvio-padrão FG</th>
                  <th className="px-2 py-2 text-right">Média CE</th>
                  <th className="px-2 py-2 text-right">Média GER</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.co_regiao} className="border-t border-academia-100">
                    <td className="px-2 py-2 font-medium">{r.nome}</td>
                    <td className="px-2 py-2 text-right">{formatInt(r.total_registros)}</td>
                    <td className="px-2 py-2 text-right">{formatDecimal(r.media_geral, 2)}</td>
                    <td className="px-2 py-2 text-right">{formatDecimal(r.media_min, 2)}</td>
                    <td className="px-2 py-2 text-right">{formatDecimal(r.media_max, 2)}</td>
                    <td className="px-2 py-2 text-right">{formatDecimal(r.desvio_padrao, 2)}</td>
                    <td className="px-2 py-2 text-right">{formatDecimal(r.media_geral_ce, 2)}</td>
                    <td className="px-2 py-2 text-right">{formatDecimal(r.media_geral_ger, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </QueryBoundary>
  );
}
