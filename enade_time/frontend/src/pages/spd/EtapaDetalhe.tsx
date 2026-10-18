import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { BarEtapasAno } from "@/components/charts/BarEtapasAno";
import { EtapasTable } from "@/components/tables/EtapasTable";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { useEtapas, useExecucao } from "@/hooks/useBenchmark";
import {
  formatDecimal,
  formatInt,
  formatSeconds,
  formatThroughput,
} from "@/lib/format";

export default function SpdEtapaDetalhe() {
  const { execucaoId } = useParams<{ execucaoId: string }>();
  const id = execucaoId ? Number(execucaoId) : null;
  const valido = id !== null && Number.isFinite(id);

  const exec = useExecucao(valido ? id : null, false);
  const etapas = useEtapas(valido ? id : null, false);

  return (
    <div className="space-y-4">
      <Link
        to="/spd/execucoes"
        className="inline-flex items-center gap-1 text-sm text-academia-700 hover:text-academia-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Voltar para execuções
      </Link>

      <QueryBoundary
        query={exec}
        loadingLabel="Carregando execução…"
      >
        {(e) => (
          <Card>
            <CardHeader
              title={`Execução #${e.id} — ${e.modo}${
                e.modo === "paralelo" ? ` (${e.num_workers} workers)` : ""
              }`}
              description={e.observacoes ?? undefined}
            />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <div className="text-xs text-academia-500">Tempo total</div>
                <div className="font-semibold">{formatSeconds(e.tempo_total_seg)}</div>
              </div>
              <div>
                <div className="text-xs text-academia-500">Linhas processadas</div>
                <div className="font-semibold">{formatInt(e.linhas_processadas)}</div>
              </div>
              <div>
                <div className="text-xs text-academia-500">Throughput</div>
                <div className="font-semibold">{formatThroughput(e.throughput_lps)}</div>
              </div>
              <div>
                <div className="text-xs text-academia-500">Memória de pico</div>
                <div className="font-semibold">
                  {e.memoria_pico_mb !== null
                    ? `${formatDecimal(e.memoria_pico_mb, 2)} MB`
                    : "—"}
                </div>
              </div>
            </div>
          </Card>
        )}
      </QueryBoundary>

      <Card>
        <CardHeader
          title="Tempo por ano (etapas)"
          description="Decomposição do tempo total por edição do ENADE. Em execuções paralelas, as cores diferenciam os workers."
        />
        <QueryBoundary
          query={etapas}
          isEmpty={(d) => d.length === 0}
          loadingLabel="Carregando etapas…"
        >
          {(rows) => <BarEtapasAno data={rows} />}
        </QueryBoundary>
      </Card>

      <Card>
        <CardHeader title="Detalhamento das etapas" />
        <QueryBoundary query={etapas} isEmpty={(d) => d.length === 0}>
          {(rows) => <EtapasTable data={rows} />}
        </QueryBoundary>
      </Card>
    </div>
  );
}
