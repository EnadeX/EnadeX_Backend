export interface Regiao {
  co_regiao: number;
  nome: string;
}

export interface UF {
  co_uf: number;
  sigla: string;
  nome: string;
  co_regiao: number;
}

export interface Ano {
  co_ano: number;
  edicao: string | null;
}

export interface Grupo {
  co_grupo: number;
  nome: string;
}

export interface Modalidade {
  co_modalidade: number;
  nome: string;
}

export interface CategoriaAdm {
  co_categad: number;
  nome: string;
}

export interface OrganizacaoAcademica {
  co_orgacad: number;
  nome: string;
}

export interface FiltrosAnalise {
  nu_ano?: number;
  co_regiao?: number;
  co_uf?: number;
  co_ies?: number;
  co_grupo?: number;
  co_modalidade?: number;
  co_categad?: number;
  co_orgacad?: number;
}

export interface ResumoAnual {
  nu_ano: number;
  total_registros: number;
  media_geral: number | null;
  media_min: number | null;
  media_max: number | null;
  desvio_padrao: number | null;
  media_geral_ger: number | null;
  media_geral_ce: number | null;
}

export interface ResumoRegiao {
  co_regiao: number;
  nome: string;
  total_registros: number;
  media_geral: number | null;
  media_min: number | null;
  media_max: number | null;
  desvio_padrao: number | null;
  media_geral_ger: number | null;
  media_geral_ce: number | null;
}

export interface ResumoUF {
  co_uf: number;
  sigla: string;
  nome: string;
  co_regiao: number;
  total_registros: number;
  media_geral: number | null;
  media_min: number | null;
  media_max: number | null;
  desvio_padrao: number | null;
  media_geral_ger: number | null;
  media_geral_ce: number | null;
}

export interface ResumoIES {
  co_ies: number;
  co_categad: number;
  co_orgacad: number;
  co_uf_curso: number;
  total_registros: number;
  media_geral: number | null;
  media_geral_ger: number | null;
  media_geral_ce: number | null;
}

export interface Registro {
  id: number;
  nu_ano: number;
  co_curso: number;
  co_ies: number;
  co_categad: number;
  co_orgacad: number;
  co_grupo: number;
  co_modalidade: number | null;
  co_munic_curso: number | null;
  co_uf_curso: number;
  co_regiao_curso: number;
  media_nt_fg: number | null;
  media_nt_ger: number | null;
  media_nt_ce: number | null;
}

export interface PaginatedResponse<T> {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  items: T[];
}

// ---------------------------------------------------------------------------
// Benchmark (v2: campanhas, suítes, ordem de submissão, instrumentação)
// ---------------------------------------------------------------------------

export type OrdemSubmissao = "crescente" | "lpt";
export type Pareamento = "suite" | "temporal";

export interface BenchmarkExecucao {
  id: number;
  timestamp_inicio: string;
  modo: "sequencial" | "paralelo";
  num_workers: number;
  tempo_total_seg: number;
  linhas_processadas: number;
  throughput_lps: number;
  cpu_count_maquina: number;
  cpu_modelo: string | null;
  memoria_pico_mb: number | null;
  observacoes: string | null;
  // v2 (aditivo)
  campanha_id?: string | null;
  suite_id?: string | null;
  oficial?: boolean;
  ordem_submissao?: OrdemSubmissao | null;
  cpu_fisicos?: number | null;
  cpu_logicos?: number | null;
  cpu_percent_medio?: number | null;
  disco_bytes_lidos?: number | null;
  cache_quente?: boolean | null;
  aquecimento?: boolean;
}

export interface BenchmarkEtapa {
  id: number;
  execucao_id: number;
  ano: number;
  tempo_seg: number;
  linhas_arq3: number;
  worker_pid: number | null;
  timestamp_inicio: string;
  timestamp_fim: string;
}

export interface BenchmarkMetrica {
  execucao_id: number;
  timestamp_inicio: string;
  num_workers: number;
  tempo_sequencial: number | null;
  tempo_paralelo: number | null;
  speedup: number | null;
  eficiencia: number | null;
  throughput_sequencial: number | null;
  throughput_paralelo: number | null;
  cpu_count_maquina: number;
  // v2
  ordem_submissao?: OrdemSubmissao | null;
  suite_id?: string | null;
  campanha_id?: string | null;
  oficial?: boolean;
  baseline_execucao_id?: number | null;
  pareamento?: Pareamento | null;
}

export interface Campanha {
  campanha_id: string;
  inicio: string;
  fim: string;
  n_execucoes: number;
  n_suites: number;
  oficial: boolean;
  cpu_fisicos: number | null;
  cpu_logicos: number | null;
  cpu_modelo: string | null;
  observacoes: string | null;
}

export interface ComparativoItem {
  execucao_id: number;
  modo: "sequencial" | "paralelo";
  num_workers: number;
  tempo_total_seg: number;
  throughput_lps: number;
  speedup: number | null;
  eficiencia: number | null;
  // v2
  suite_id?: string | null;
  campanha_id?: string | null;
  ordem_submissao?: OrdemSubmissao | null;
  oficial?: boolean;
  baseline_execucao_id?: number | null;
  pareamento?: Pareamento | null;
}

/** Uma configuração (workers × ordem) agregada sobre as suítes da campanha. */
export interface ResumoConfiguracao {
  modo: "sequencial" | "paralelo";
  num_workers: number;
  ordem_submissao: OrdemSubmissao | null;
  n: number;
  tempo_mediana: number;
  tempo_min: number;
  tempo_max: number;
  tempo_iqr: number;
  throughput_mediana: number;
  speedup_mediana: number | null;
  speedup_min: number | null;
  speedup_max: number | null;
  eficiencia_mediana: number | null;
  eficiencia_min: number | null;
  eficiencia_max: number | null;
  oficial: boolean | null;
  cpu_fisicos: number | null;
  cpu_logicos: number | null;
  cache_quente: boolean | null;
}

export interface MaquinaCampanha {
  cpu_fisicos: number | null;
  cpu_logicos: number | null;
  cpu_modelo: string | null;
  cache_quente: boolean | null;
}

export interface BenchmarkComparativo {
  baseline_sequencial_id: number | null;
  tempo_baseline_seg: number | null;
  throughput_baseline_lps: number | null;
  cpu_count_maquina: number | null;
  // v2 (aditivo)
  campanha_id?: string | null;
  suite_id?: string | null;
  n_suites?: number | null;
  maquina?: MaquinaCampanha | null;
  itens: ComparativoItem[];
  resumo?: ResumoConfiguracao[];
}

export interface HealthStatus {
  status: string;
  database: string;
  version: string;
}
