import hashlib
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from config import EnrichmentSettings
from ingestion.enrich.prompts import build_enrichment_prompt
from ingestion.schemas import ArxivMetadata
from llm.bedrock import Usage
from textnorm import normalize

_MIN_CLAIMS = 5
_MAX_CLAIMS = 15


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_hash: str
    arxiv_id: str
    claim_text: str
    section_title: str


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_key: str
    surface_form: str
    entity_type: str


class EnrichmentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    claims: tuple[ExtractedClaim, ...]
    entities: tuple[ExtractedEntity, ...]
    usage: Usage
    warning: str | None = None


def extract_claims_and_entities(
    metadata: ArxivMetadata,
    sections: list[tuple[str, str]],
    llm_invoke_json: Callable[[str], tuple[dict, Usage]],
    settings: EnrichmentSettings,
) -> EnrichmentResult:
    prompt = build_enrichment_prompt(metadata.title, metadata.abstract, sections, settings.prompt_max_chars)
    data, usage = llm_invoke_json(prompt)

    claims, warning = _build_claims(data.get("claims", []), metadata.arxiv_id)
    entities = _build_entities(data.get("entities", []))

    return EnrichmentResult(claims=claims, entities=entities, usage=usage, warning=warning)


def _build_claims(raw_claims: list[dict], arxiv_id: str) -> tuple[tuple[ExtractedClaim, ...], str | None]:
    valid = [c for c in raw_claims if c.get("text") and c.get("section_title")]

    warning = None
    if len(valid) > _MAX_CLAIMS:
        warning = f"model returned {len(valid)} claims, truncated to {_MAX_CLAIMS}"
        valid = valid[:_MAX_CLAIMS]
    elif len(valid) < _MIN_CLAIMS:
        warning = f"model returned only {len(valid)} claims, expected at least {_MIN_CLAIMS}"

    claims = tuple(
        ExtractedClaim(
            claim_hash=hashlib.sha256(normalize(c["text"]).encode()).hexdigest(),
            arxiv_id=arxiv_id,
            claim_text=c["text"],
            section_title=c["section_title"],
        )
        for c in valid
    )
    return claims, warning


def _build_entities(raw_entities: list[dict]) -> tuple[ExtractedEntity, ...]:
    seen: dict[str, ExtractedEntity] = {}
    for entity in raw_entities:
        surface_form = entity.get("surface_form")
        entity_type = entity.get("entity_type")
        if not surface_form or not entity_type:
            continue
        key = normalize(surface_form)
        if key not in seen:
            seen[key] = ExtractedEntity(entity_key=key, surface_form=surface_form, entity_type=entity_type)
    return tuple(seen.values())
