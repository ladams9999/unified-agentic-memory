from __future__ import annotations

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UAM_",
        env_file=("db_stack/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = 3081
    db_user: str = "uam_user"
    db_password: str = "uam_password"
    db_name: str = "uam_db"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "mistral"
    llm_timeout_seconds: int = 300
    embedding_provider: str = "ollama"  # "ollama" | "openai"
    llm_provider: str = "ollama"  # "ollama" | "openai" | "openrouter"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_llm_model: str = "mistralai/mistral-7b-instruct"
    search_cache_ttl_seconds: int = 900
    hook_metrics_window: int = 200
    local_log_dir: Path = Path("logs")
    db_sslmode: str = "prefer"  # "disable" | "allow" | "prefer" | "require" | "verify-ca" | "verify-full"
    disable_graph: bool = False  # set True for Supabase or any AGE-less Postgres

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} password={self.db_password} "
            f"sslmode={self.db_sslmode}"
        )

    @computed_field
    @property
    def postgres_database_url(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname=postgres user={self.db_user} password={self.db_password} "
            f"sslmode={self.db_sslmode}"
        )


settings = Settings()
