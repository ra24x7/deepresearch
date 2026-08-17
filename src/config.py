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
    max_retries: int = 6


class RetrievalSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="RETRIEVAL__")

    top_k: int = 10
    # Coarse retrieval over-fetches because the reranker can only reorder what
    # stage one found; a missed chunk is unrecoverable downstream.
    over_fetch_multiplier: int = 4
    min_candidates: int = 60
    entity_damping: float = 1.0
    # Measured on the golden set: 0.1 beats disabling the channel (0.966 vs
    # 0.931 recall@10) while 0.25+ destroys it. Entity matches break ties among
    # candidates the semantic channels already found; they do not get a vote.
    entity_weight: float = 0.1


class RerankSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="RERANK__")

    provider: str = "cohere_bedrock"
    model_id: str = "cohere.rerank-v3-5:0"
    # Rerank is not offered in ap-south-1, so it runs cross-region from the rest.
    region: str = "eu-central-1"
    max_documents: int = 100
    max_retries: int = 6


class EnrichmentSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="ENRICHMENT__")

    model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout_seconds: float = 60.0
    max_retries: int = 3
    prompt_max_chars: int = 12000


class GenerationSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="GENERATION__")

    model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    max_tokens: int = 1024
    temperature: float = 0.0
    max_retries: int = 3
    # Ten reranked chunks of 100-800 words fit well inside this; the cap exists
    # so a pathological chunk cannot push the instructions out of the prompt.
    prompt_max_chars: int = 24000


class JudgeSettings(FrozenSettings):
    model_config = SettingsConfigDict(env_prefix="JUDGE__")

    model_id: str = "global.anthropic.claude-sonnet-4-6"
    # Phase 1 calibrated at 200, but every answer it graded was a uniform
    # abstention with short reasoning. On a substantive multi-part answer the
    # judge reasons at length and 200 truncates it before the JSON is emitted,
    # which killed a 150-question run at question 34.
    max_tokens: int = 1024
    temperature: float = 0.0
    max_retries: int = 3
