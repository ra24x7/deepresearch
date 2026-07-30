from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArxivSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARXIV__", env_nested_delimiter="__")

    base_url: str = "https://export.arxiv.org/api/query"
    rate_limit_seconds: float = 3.0
    max_retries: int = 3
    timeout_seconds: float = 30.0
    pdf_cache_dir: str = "data/papers"


class ParserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PARSER__", env_nested_delimiter="__")

    max_pages: int = 50


class ChunkingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHUNKING__", env_nested_delimiter="__")

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


class OpenSearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENSEARCH__", env_nested_delimiter="__")

    host: str = "localhost:9200"


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES__", env_nested_delimiter="__")

    dsn: str = "postgresql://deepresearch:deepresearch@localhost:5433/deepresearch"


class BedrockSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BEDROCK__", env_nested_delimiter="__")

    region: str = "ap-south-1"


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDING__", env_nested_delimiter="__")

    provider: str = "cohere_bedrock"
    model_id: str = "global.cohere.embed-v4:0"
    dimension: int = 1024
