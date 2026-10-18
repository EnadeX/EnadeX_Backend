import { KpiGrid } from "@/components/cards/KpiGrid";
import { MetricCard } from "@/components/cards/MetricCard";
import { LineMediaAnual } from "@/components/charts/LineMediaAnual";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { useResumoAnual } from "@/hooks/useAnalises";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";
import { formatDecimal, formatInt } from "@/lib/format";

export default function EnadeAnual() {
  const { filtros } = useFiltrosUrl();
  const q = useResumoAnual(filtros);

  return (
    <>
      <QueryBoundary
        query={q}
        isEmpty={(d) => d.length === 0}
        emptyTitle="Nenhum registro para os filtros aplicados."
      >
        {(rows) => {
          const total = rows.reduce((acc, r) => acc + r.total_registros, 0);
          const mediaGeral =
            rows.length === 0
              ? null
              : rows.reduce((acc, r) => acc + (r.media_geral_ger ?? 0), 0) /
                rows.filter((r) => r.media_geral_ger !== null).length;
          const melhor = rows.reduce<typeof rows[number] | null>(
            (b, r) =>
              r.media_geral_ger !== null &&
              (b === null || (r.media_geral_ger ?? 0) > (b.media_geral_ger ?? 0))
                ? r
                : b,
            null,
          );
          const pior = rows.reduce<typeof rows[number] | null>(
            (b, r) =>
              r.media_geral_ger !== null &&
              (b === null || (r.media_geral_ger ?? 100) < (b.media_geral_ger ?? 100))
                ? r
                : b,
            null,
          );

          return (
            <>
              <KpiGrid>
                <MetricCard label="Registros (filtrado)" value={formatInt(total)} />
                <MetricCard
                  label="Anos no recorte"
                  value={formatInt(rows.length)}
                />
                <MetricCard
                  label="Média NT GER"
                  value={formatDecimal(mediaGeral, 2)}
                />
                <MetricCard
                  label="Melhor ano"
                  value={melhor ? String(melhor.nu_ano) : "—"}
                  hint={
                    melhor ? `Média ${formatDecimal(melhor.media_geral_ger, 2)}` : undefined
                  }
                />
              </KpiGrid>
              <Card>
                <CardHeader
                  title="Média Nota Geral (NT GER) por ano"
                  description="Variação longitudinal das médias da Nota Geral (NT GER) ao longo das edições."
                />
                <LineMediaAnual data={rows} />
                {pior && (
                  <p className="text-xs text-academia-500 mt-2">
                    Menor média observada: {pior.nu_ano} ({formatDecimal(pior.media_geral_ger, 2)}).
                  </p>
                )}
              </Card>
            </>
          );
        }}
      </QueryBoundary>
    </>
  );
}
