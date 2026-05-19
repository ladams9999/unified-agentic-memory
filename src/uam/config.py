import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


@dataclass
class Settings:
    db_host: str = "localhost"
    db_port: int = 3081
    db_user: str = "uam_user"
    db_password: str = "uam_password"
    db_name: str = "uam_db"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "smollm3"
    search_cache_ttl_seconds: int = 900
    hook_metrics_window: int = 200
    local_log_dir: Path = field(default_factory=lambda: Path("logs"))

    def __post_init__(self) -> None:
        env = {}
        env.update(_load_env_file(Path("db_stack/.env")))
        env.update(_load_env_file(Path(".env")))
        env.update(os.environ)

        self.db_host = env.get("UAM_DB_HOST", self.db_host)
        self.db_port = int(env.get("UAM_DB_PORT", str(self.db_port)))
        self.db_user = env.get("UAM_DB_USER", env.get("PG_USER", self.db_user))
        self.db_password = env.get("UAM_DB_PASSWORD", env.get("PG_PASSWORD", self.db_password))
        self.db_name = env.get("UAM_DB_NAME", env.get("PG_DB", self.db_name))
        self.ollama_url = env.get("UAM_OLLAMA_URL", self.ollama_url)
        self.embedding_model = env.get("UAM_EMBEDDING_MODEL", self.embedding_model)
        self.llm_model = env.get("UAM_LLM_MODEL", self.llm_model)
        self.search_cache_ttl_seconds = int(
            env.get("UAM_SEARCH_CACHE_TTL_SECONDS", str(self.search_cache_ttl_seconds))
        )
        self.hook_metrics_window = int(env.get("UAM_HOOK_METRICS_WINDOW", str(self.hook_metrics_window)))
        self.local_log_dir = Path(env.get("UAM_LOCAL_LOG_DIR", str(self.local_log_dir)))

    @property
    def database_url(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname={self.db_name} user={self.db_user} password={self.db_password}"
        )

    @property
    def postgres_database_url(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} "
            f"dbname=postgres user={self.db_user} password={self.db_password}"
        )


settings = Settings()
