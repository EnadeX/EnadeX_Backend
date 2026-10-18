import { useQuery } from "@tanstack/react-query";

import {
  fetchAnos,
  fetchCategoriasAdm,
  fetchGrupos,
  fetchModalidades,
  fetchOrganizacoesAcademicas,
  fetchRegioes,
  fetchUFs,
} from "@/api/dimensoes";

const LONG_STALE = 24 * 60 * 60_000;

export function useRegioes() {
  return useQuery({
    queryKey: ["dim", "regioes"],
    queryFn: fetchRegioes,
    staleTime: LONG_STALE,
  });
}

export function useUFs(co_regiao?: number) {
  return useQuery({
    queryKey: ["dim", "ufs", co_regiao ?? null],
    queryFn: () => fetchUFs(co_regiao),
    staleTime: LONG_STALE,
  });
}

export function useAnos() {
  return useQuery({
    queryKey: ["dim", "anos"],
    queryFn: fetchAnos,
    staleTime: LONG_STALE,
  });
}

export function useGrupos() {
  return useQuery({
    queryKey: ["dim", "grupos"],
    queryFn: fetchGrupos,
    staleTime: LONG_STALE,
  });
}

export function useModalidades() {
  return useQuery({
    queryKey: ["dim", "modalidades"],
    queryFn: fetchModalidades,
    staleTime: LONG_STALE,
  });
}

export function useCategoriasAdm() {
  return useQuery({
    queryKey: ["dim", "categorias-adm"],
    queryFn: fetchCategoriasAdm,
    staleTime: LONG_STALE,
  });
}

export function useOrganizacoesAcademicas() {
  return useQuery({
    queryKey: ["dim", "organizacoes-academicas"],
    queryFn: fetchOrganizacoesAcademicas,
    staleTime: LONG_STALE,
  });
}
