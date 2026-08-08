from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

Channel = Literal["bm25", "dense_chunks", "dense_claims", "entities"]
Route = Literal["computable", "semantic", "entity_anchored", "out_of_domain"]

# Every channel, in fan-out order. Derived from the type so a new channel cannot
# be added to one list and forgotten in another.
CHANNEL_NAMES: tuple[Channel, ...] = get_args(Channel)


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
