from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrozenSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, env_nested_delimiter="__")


class ArxivSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="ARXIV__")

    base_url: str = "https://export.arxiv.org/api/query"
    rate_limit_seconds: float = 3.0
    max_retries: int = 3
    timeout_seconds: float = 30.0
    pdf_cache_dir: str = "data/papers"


class ParserSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="PARSER__")

    max_pages: int = 50
    max_file_size_mb: int = 20
    do_ocr: bool = False
    do_table_structure: bool = True


class ChunkingSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="CHUNKING__")

    min_words: int = 100
    max_words: int = 800
    split_size: int = 600
    overlap: int = 100

    @model_validator(mode="after")
    def _overlap_must_advance(self):
        # overlap >= split_size makes the split loop's step non-positive: infinite loop.
        if self.overlap >= self.split_size:
            raise ValueError(f"overlap ({self.overlap}) must be < split_size ({self.split_size})")
        return self


class OpenSearchSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="OPENSEARCH__")

    host: str = "localhost:9200"


class PostgresSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES__")

    dsn: str = "postgresql://deepresearch:deepresearch@localhost:5433/deepresearch"

    @field_validator("dsn")
    @classmethod
    def _dsn_must_be_postgres(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("dsn must start with 'postgresql://' or 'postgresql+psycopg2://'")
        return value


class BedrockSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="BEDROCK__")

    region: str = "ap-south-1"


class EmbeddingSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDING__")

    provider: str = "cohere_bedrock"
    model_id: str = "global.cohere.embed-v4:0"
    dimension: int = 1024
