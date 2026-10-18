from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "enade_db"
    postgres_user: str = "enade_user"
    postgres_password: str = "enade_password"

    # DSN completo (ex.: o Supabase pelo papel somente-leitura enade_time_reader). Quando
    # definido, tem precedência sobre POSTGRES_*: é assim que a mesma API lê do banco local
    # (o instrumento do experimento) ou da nuvem (onde os resultados são publicados).
    enade_time_db_url: str | None = None
    # DSN do Supabase gravado pelo script 12 (papel leitor). Inativo por padrão: só vira
    # ENADE_TIME_DB_URL quando a API sobe com `--fonte supabase`.
    enade_time_db_url_supabase: str | None = None

    api_port: int = 8000

    # Execuções de benchmark a ocultar por padrão (`?apenas_validas=true`).
    # Vazio por padrão: os ids são um BIGSERIAL e voltam a 1 a cada
    # `05_criar_schema_postgres.py --reset`, então uma lista fixa acaba
    # escondendo justamente as execuções válidas da rodada atual.
    # Para ocultar execuções inválidas de uma rodada específica, defina a
    # variável de ambiente BENCHMARK_IDS_EXCLUIR (JSON), ex.: '[1,2,3]'.
    benchmark_ids_excluir: list[int] = Field(default_factory=list)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
        ]
    )

    pool_minconn: int = 1
    pool_maxconn: int = 10
    db_connect_timeout: int = 5

    model_config = SettingsConfigDict(
        # enade_time/.env (local do subprojeto) e depois EnadeX/.env (raiz do
        # grupo); valores do primeiro vencem. Caminhos absolutos: funcionam de
        # qualquer CWD.
        env_file=(
            str(Path(__file__).resolve().parents[1] / ".env"),
            str(Path(__file__).resolve().parents[2] / ".env"),
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def fonte_dos_dados(settings: Settings) -> str:
    """'supabase' quando o DSN aponta para o Supabase; 'local' no Postgres do docker-compose."""
    if settings.enade_time_db_url:
        host = (urlparse(settings.enade_time_db_url).hostname or "").lower()
        return "supabase" if "supabase" in host else "externo"
    return "local"
