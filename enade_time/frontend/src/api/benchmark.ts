import { apiClient } from "./client";
import type {
  BenchmarkComparativo,
  BenchmarkEtapa,
  BenchmarkExecucao,
  BenchmarkMetrica,
} from "@/types/api";

export async function fetchExecucoes(
  apenasValidas: boolean = true,
): Promise<BenchmarkExecucao[]> {
  const { data } = await apiClient.get<BenchmarkExecucao[]>(
    "/api/benchmark/execucoes",
    { params: { apenas_validas: apenasValidas } },
  );
  return data;
}

export async function fetchExecucao(
  id: number,
  apenasValidas: boolean = true,
): Promise<BenchmarkExecucao> {
  const { data } = await apiClient.get<BenchmarkExecucao>(
    `/api/benchmark/execucoes/${id}`,
    { params: { apenas_validas: apenasValidas } },
  );
  return data;
}

export async function fetchEtapas(
  execucaoId: number,
  apenasValidas: boolean = true,
): Promise<BenchmarkEtapa[]> {
  const { data } = await apiClient.get<BenchmarkEtapa[]>(
    `/api/benchmark/etapas/${execucaoId}`,
    { params: { apenas_validas: apenasValidas } },
  );
  return data;
}

export async function fetchMetricas(
  apenasValidas: boolean = true,
): Promise<BenchmarkMetrica[]> {
  const { data } = await apiClient.get<BenchmarkMetrica[]>(
    "/api/benchmark/metricas",
    { params: { apenas_validas: apenasValidas } },
  );
  return data;
}

export async function fetchComparativo(
  apenasValidas: boolean = true,
): Promise<BenchmarkComparativo> {
  const { data } = await apiClient.get<BenchmarkComparativo>(
    "/api/benchmark/comparativo",
    { params: { apenas_validas: apenasValidas } },
  );
  return data;
}
