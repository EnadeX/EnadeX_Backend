import { apiClient } from "./client";
import type {
  FiltrosAnalise,
  PaginatedResponse,
  Registro,
  ResumoAnual,
  ResumoIES,
  ResumoRegiao,
  ResumoUF,
} from "@/types/api";

function cleanParams<T extends object>(obj: T): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined && v !== null && v !== "") {
      out[k] = v;
    }
  }
  return out;
}

export async function fetchResumoAnual(
  filtros: FiltrosAnalise,
): Promise<ResumoAnual[]> {
  const { data } = await apiClient.get<ResumoAnual[]>(
    "/api/analises/resumo-anual",
    { params: cleanParams(filtros) },
  );
  return data;
}

export async function fetchResumoRegiao(
  filtros: FiltrosAnalise,
): Promise<ResumoRegiao[]> {
  const { data } = await apiClient.get<ResumoRegiao[]>(
    "/api/analises/resumo-regiao",
    { params: cleanParams(filtros) },
  );
  return data;
}

export async function fetchResumoUF(
  filtros: FiltrosAnalise,
): Promise<ResumoUF[]> {
  const { data } = await apiClient.get<ResumoUF[]>(
    "/api/analises/resumo-uf",
    { params: cleanParams(filtros) },
  );
  return data;
}

export async function fetchResumoIES(
  filtros: FiltrosAnalise,
  limit: number = 20,
  minCursos: number = 1,
): Promise<ResumoIES[]> {
  const { data } = await apiClient.get<ResumoIES[]>(
    "/api/analises/resumo-ies",
    { params: cleanParams({ ...filtros, limit, min_cursos: minCursos }) },
  );
  return data;
}

export async function fetchRegistros(
  filtros: FiltrosAnalise,
  page: number,
  pageSize: number,
): Promise<PaginatedResponse<Registro>> {
  const { data } = await apiClient.get<PaginatedResponse<Registro>>(
    "/api/analises/registros",
    { params: cleanParams({ ...filtros, page, page_size: pageSize }) },
  );
  return data;
}
