import { apiClient } from "./client";
import type {
  Ano,
  CategoriaAdm,
  Grupo,
  Modalidade,
  OrganizacaoAcademica,
  Regiao,
  UF,
} from "@/types/api";

export async function fetchRegioes(): Promise<Regiao[]> {
  const { data } = await apiClient.get<Regiao[]>("/api/dim/regioes");
  return data;
}

export async function fetchUFs(co_regiao?: number): Promise<UF[]> {
  const { data } = await apiClient.get<UF[]>("/api/dim/ufs", {
    params: co_regiao !== undefined ? { co_regiao } : undefined,
  });
  return data;
}

export async function fetchAnos(): Promise<Ano[]> {
  const { data } = await apiClient.get<Ano[]>("/api/dim/anos");
  return data;
}

export async function fetchGrupos(): Promise<Grupo[]> {
  const { data } = await apiClient.get<Grupo[]>("/api/dim/grupos");
  return data;
}

export async function fetchModalidades(): Promise<Modalidade[]> {
  const { data } = await apiClient.get<Modalidade[]>("/api/dim/modalidades");
  return data;
}

export async function fetchCategoriasAdm(): Promise<CategoriaAdm[]> {
  const { data } = await apiClient.get<CategoriaAdm[]>("/api/dim/categorias-adm");
  return data;
}

export async function fetchOrganizacoesAcademicas(): Promise<OrganizacaoAcademica[]> {
  const { data } = await apiClient.get<OrganizacaoAcademica[]>(
    "/api/dim/organizacoes-academicas",
  );
  return data;
}
