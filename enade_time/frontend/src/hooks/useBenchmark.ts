import { useQuery } from "@tanstack/react-query";

import {
  fetchComparativo,
  fetchEtapas,
  fetchExecucao,
  fetchExecucoes,
  fetchMetricas,
} from "@/api/benchmark";

const STALE = 5 * 60_000;

export function useExecucoes(apenasValidas: boolean) {
  return useQuery({
    queryKey: ["benchmark", "execucoes", apenasValidas],
    queryFn: () => fetchExecucoes(apenasValidas),
    staleTime: STALE,
  });
}

export function useExecucao(id: number | null, apenasValidas: boolean) {
  return useQuery({
    queryKey: ["benchmark", "execucao", id, apenasValidas],
    queryFn: () => fetchExecucao(id as number, apenasValidas),
    enabled: id !== null,
    staleTime: STALE,
  });
}

export function useEtapas(execucaoId: number | null, apenasValidas: boolean) {
  return useQuery({
    queryKey: ["benchmark", "etapas", execucaoId, apenasValidas],
    queryFn: () => fetchEtapas(execucaoId as number, apenasValidas),
    enabled: execucaoId !== null,
    staleTime: STALE,
  });
}

export function useMetricas(apenasValidas: boolean) {
  return useQuery({
    queryKey: ["benchmark", "metricas", apenasValidas],
    queryFn: () => fetchMetricas(apenasValidas),
    staleTime: STALE,
  });
}

export function useComparativo(apenasValidas: boolean) {
  return useQuery({
    queryKey: ["benchmark", "comparativo", apenasValidas],
    queryFn: () => fetchComparativo(apenasValidas),
    staleTime: STALE,
  });
}
