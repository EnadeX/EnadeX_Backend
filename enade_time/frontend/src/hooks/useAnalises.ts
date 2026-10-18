import { useQuery } from "@tanstack/react-query";

import {
  fetchRegistros,
  fetchResumoAnual,
  fetchResumoIES,
  fetchResumoRegiao,
  fetchResumoUF,
} from "@/api/analises";
import type { FiltrosAnalise } from "@/types/api";

const STALE = 5 * 60_000;

export function useResumoAnual(filtros: FiltrosAnalise) {
  return useQuery({
    queryKey: ["analises", "resumo-anual", filtros],
    queryFn: () => fetchResumoAnual(filtros),
    staleTime: STALE,
  });
}

export function useResumoRegiao(filtros: FiltrosAnalise) {
  return useQuery({
    queryKey: ["analises", "resumo-regiao", filtros],
    queryFn: () => fetchResumoRegiao(filtros),
    staleTime: STALE,
  });
}

export function useResumoUF(filtros: FiltrosAnalise) {
  return useQuery({
    queryKey: ["analises", "resumo-uf", filtros],
    queryFn: () => fetchResumoUF(filtros),
    staleTime: STALE,
  });
}

export function useResumoIES(
  filtros: FiltrosAnalise,
  limit: number,
  minCursos: number,
) {
  return useQuery({
    queryKey: ["analises", "resumo-ies", filtros, limit, minCursos],
    queryFn: () => fetchResumoIES(filtros, limit, minCursos),
    staleTime: STALE,
  });
}

export function useRegistros(
  filtros: FiltrosAnalise,
  page: number,
  pageSize: number,
) {
  return useQuery({
    queryKey: ["analises", "registros", filtros, page, pageSize],
    queryFn: () => fetchRegistros(filtros, page, pageSize),
    staleTime: STALE,
    placeholderData: (prev) => prev,
  });
}
