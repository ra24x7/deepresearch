from typing import Literal

from pydantic import BaseModel, ConfigDict

Channel = Literal["bm25", "dense_chunks", "dense_claims", "entities"]
Route = Literal["computable", "semantic", "entity_anchored", "out_of_domain"]


class RetrievalHit(BaseModel):
    """One result from one channel, before fusion."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    arxiv_id: str
    channel: Channel
    score: float
    text: str
    section_title: str = ""
    page_start: int | None = None
    page_end: int | None = None


class FusedHit(BaseModel):
    """A hit after fusion, carrying which channels found it."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    arxiv_id: str
    score: float
    text: str
    channels: tuple[Channel, ...]
    section_title: str = ""
    page_start: int | None = None
    page_end: int | None = None
