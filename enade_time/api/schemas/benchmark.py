from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BenchmarkExecucao(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp_inicio: datetime
    modo: str
    num_workers: int
    tempo_total_seg: float
    linhas_processadas: int
    throughput_lps: float
    cpu_count_maquina: int
    cpu_modelo: str | None = None
    memoria_pico_mb: float | None = None
    observacoes: str | None = None
    # v2 — campanha / suíte / ordem de submissão / instrumentação (aditivo)
    campanha_id: str | None = None
    suite_id: str | None = None
    oficial: bool = False
    ordem_submissao: str | None = None
    cpu_fisicos: int | None = None
    cpu_logicos: int | None = None
    cpu_percent_medio: float | None = None
    disco_bytes_lidos: int | None = None
    cache_quente: bool | None = None
    aquecimento: bool = False


class BenchmarkEtapa(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execucao_id: int
    ano: int
    tempo_seg: float
    linhas_arq3: int
    worker_pid: int | None = None
    timestamp_inicio: datetime
    timestamp_fim: datetime


class BenchmarkMetrica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execucao_id: int
    timestamp_inicio: datetime
    num_workers: int
    tempo_sequencial: float | None = None
    tempo_paralelo: float | None = None
    speedup: float | None = None
    eficiencia: float | None = None
    throughput_sequencial: float | None = None
    throughput_paralelo: float | None = None
    cpu_count_maquina: int
    # v2
    ordem_submissao: str | None = None
    suite_id: str | None = None
    campanha_id: str | None = None
    oficial: bool = False
    baseline_execucao_id: int | None = None
    pareamento: str | None = None  # 'suite' | 'temporal'


class Campanha(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campanha_id: str
    inicio: datetime
    fim: datetime
    n_execucoes: int
    n_suites: int
    oficial: bool
    cpu_fisicos: int | None = None
    cpu_logicos: int | None = None
    cpu_modelo: str | None = None
    observacoes: str | None = None


class ComparativoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execucao_id: int
    modo: str
    num_workers: int
    tempo_total_seg: float
    throughput_lps: float
    speedup: float | None = None
    eficiencia: float | None = None
    # v2
    suite_id: str | None = None
    campanha_id: str | None = None
    ordem_submissao: str | None = None
    oficial: bool = False
    baseline_execucao_id: int | None = None
    pareamento: str | None = None


class ResumoConfiguracao(BaseModel):
    """Uma configuração (workers × ordem) agregada sobre as suítes da campanha."""
    model_config = ConfigDict(from_attributes=True)

    modo: str
    num_workers: int
    ordem_submissao: str | None = None
    n: int
    tempo_mediana: float
    tempo_min: float
    tempo_max: float
    tempo_iqr: float
    throughput_mediana: float
    speedup_mediana: float | None = None
    speedup_min: float | None = None
    speedup_max: float | None = None
    eficiencia_mediana: float | None = None
    eficiencia_min: float | None = None
    eficiencia_max: float | None = None
    oficial: bool | None = None
    cpu_fisicos: int | None = None
    cpu_logicos: int | None = None
    cache_quente: bool | None = None


class MaquinaCampanha(BaseModel):
    cpu_fisicos: int | None = None
    cpu_logicos: int | None = None
    cpu_modelo: str | None = None
    cache_quente: bool | None = None


class BenchmarkComparativo(BaseModel):
    baseline_sequencial_id: int | None = None
    tempo_baseline_seg: float | None = None
    throughput_baseline_lps: float | None = None
    cpu_count_maquina: int | None = None
    # v2 (aditivo)
    campanha_id: str | None = None
    suite_id: str | None = None
    n_suites: int | None = None
    maquina: MaquinaCampanha | None = None
    itens: list[ComparativoItem]
    resumo: list[ResumoConfiguracao] = []


class ResumoCarga(BaseModel):
    """Custo de publicação de uma estratégia de carga (v_enade_time_benchmark_carga_resumo)."""

    model_config = ConfigDict(from_attributes=True)

    estrategia: str
    n: int
    tempo_mediana: float
    tempo_min: float
    tempo_max: float
    tempo_iqr: float
    throughput_mediana: float
    rtt_mediana_ms: float | None = None
    bytes_payload: int | None = None
    linhas_destino: int
    md5_confere: bool
    host_destino: str | None = None
    rede: str | None = None
    inicio: datetime
    fim: datetime


class RepeticaoCarga(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    estrategia: str
    repeticao: int
    tempo_seg: float
    rtt_ms: float | None = None


class CargaResposta(BaseModel):
    """Eixo de carga (D17): custo de PUBLICAR a base, local × nuvem. Não é speedup."""

    carga_id: str | None = None
    resumo: list[ResumoCarga] = []
    repeticoes: list[RepeticaoCarga] = []
    # medianas da rodada imediatamente anterior (estratégia -> segundos): mostra o quanto a rede faz variar
    anterior: dict[str, float] = {}
