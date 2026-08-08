"""Read-only corpus lookups shared by the scripts and evals.

The (id, text) pairs shape is what solvability and the retrieval metrics take,
so loading them is one call rather than a hand-rolled defaultdict loop per
script.
"""

from collections import defaultdict

from db.models import Chunk, Claim, Paper


def chunks_by_paper(session) -> dict[str, list[tuple[str, str]]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for chunk in session.query(Chunk).all():
        grouped[chunk.arxiv_id].append((chunk.chunk_id, chunk.text))
    return grouped


def claims_by_paper(session) -> dict[str, list[tuple[str, str]]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for claim in session.query(Claim).all():
        grouped[claim.arxiv_id].append((claim.claim_hash, claim.claim_text))
    return grouped


def raw_text_by_paper(session) -> dict[str, str]:
    return {paper.arxiv_id: paper.raw_text for paper in session.query(Paper).all()}


def arxiv_ids_in_corpus(session, corpus: str) -> list[str]:
    return [row[0] for row in session.query(Paper.arxiv_id).filter_by(corpus=corpus).order_by(Paper.arxiv_id)]
