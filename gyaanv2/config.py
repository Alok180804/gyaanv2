from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_name: str = 'gyaanv2'
    data_dir: Path = Path('.data')
    sqlite_path: Path = Path('.data/gyaanv2.sqlite3')
    qdrant_path: Path = Path('.data/qdrant')
    qdrant_collection: str = 'gyaanv2_chunks'
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_limit: int = 8
    min_relevance_score: float = 0.25
    google_credentials_file: Path = Path('credentials.json')
    google_token_file: Path = Path('token.json')
    llm_provider: str = 'ollama'
    # llm_model: str | None = None
    # openai_api_key: str | None = None
    # anthropic_api_key: str | None = None
    # google_api_key: str | None = None
    ollama_base_url: str = 'http://localhost:11434'
    llm_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.qdrant_path.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
