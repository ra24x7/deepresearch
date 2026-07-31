import re

from ingestion.enrich.claims import ExtractedEntity
from ingestion.schemas import ArxivMetadata
from textnorm import normalize

_ARXIV_ID_PATTERN = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")


def entities_from_authors(metadata: ArxivMetadata) -> tuple[ExtractedEntity, ...]:
    return tuple(
        ExtractedEntity(entity_key=normalize(author), surface_form=author, entity_type="author")
        for author in metadata.authors
    )


def entities_from_arxiv_ids(sections: list[tuple[str, str]]) -> tuple[ExtractedEntity, ...]:
    found: dict[str, str] = {}
    for _, text in sections:
        for match in _ARXIV_ID_PATTERN.findall(text):
            key = normalize(match)
            if key not in found:
                found[key] = match
    return tuple(
        ExtractedEntity(entity_key=key, surface_form=surface_form, entity_type="paper")
        for key, surface_form in found.items()
    )


def merge_entities(
    llm_entities: tuple[ExtractedEntity, ...],
    metadata: ArxivMetadata,
    sections: list[tuple[str, str]],
) -> tuple[ExtractedEntity, ...]:
    all_entities = entities_from_authors(metadata) + entities_from_arxiv_ids(sections) + llm_entities
    return _dedupe_by_key(all_entities)


def _dedupe_by_key(entities: tuple[ExtractedEntity, ...]) -> tuple[ExtractedEntity, ...]:
    seen: dict[str, ExtractedEntity] = {}
    for entity in entities:
        if entity.entity_key not in seen:
            seen[entity.entity_key] = entity
    return tuple(seen.values())
