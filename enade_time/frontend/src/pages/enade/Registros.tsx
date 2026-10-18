import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { RegistrosTable } from "@/components/tables/RegistrosTable";
import { QueryBoundary } from "@/components/feedback/QueryBoundary";
import { Card, CardHeader } from "@/components/ui/Card";
import { useRegistros } from "@/hooks/useAnalises";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";
import { PAGE_SIZE_OPTIONS } from "@/lib/constants";
import { formatInt } from "@/lib/format";

export default function EnadeRegistros() {
  const { filtros } = useFiltrosUrl();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);

  const q = useRegistros(filtros, page, pageSize);

  return (
    <Card>
      <CardHeader
        title="Registros (paginados)"
        description="Listagem bruta do fato_enade com paginação server-side. Combine com os filtros acima."
        action={
          <label className="text-xs text-academia-700">
            Itens por página
            <select
              className="select mt-1"
              value={pageSize}
              onChange={(e) => {
                setPage(1);
                setPageSize(Number(e.target.value));
              }}
            >
              {PAGE_SIZE_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        }
      />
      <QueryBoundary
        query={q}
        isEmpty={(d) => d.items.length === 0}
        loadingLabel="Carregando registros…"
      >
        {(data) => (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3 text-sm text-academia-700">
              <div>
                Mostrando{" "}
                <strong>
                  {formatInt((data.page - 1) * data.page_size + 1)}–
                  {formatInt(Math.min(data.page * data.page_size, data.total))}
                </strong>{" "}
                de <strong>{formatInt(data.total)}</strong> registros (
                {formatInt(data.total_pages)} página{data.total_pages !== 1 ? "s" : ""})
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className="btn-secondary px-2 py-1"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  aria-label="Página anterior"
                >
                  <ChevronLeft className="h-4 w-4" aria-hidden />
                </button>
                <span className="text-xs px-2">
                  Página {data.page} / {data.total_pages || 1}
                </span>
                <button
                  type="button"
                  className="btn-secondary px-2 py-1"
                  onClick={() =>
                    setPage((p) => (data.total_pages ? Math.min(data.total_pages, p + 1) : p + 1))
                  }
                  disabled={data.total_pages ? page >= data.total_pages : false}
                  aria-label="Próxima página"
                >
                  <ChevronRight className="h-4 w-4" aria-hidden />
                </button>
              </div>
            </div>
            <RegistrosTable items={data.items} />
          </>
        )}
      </QueryBoundary>
    </Card>
  );
}
