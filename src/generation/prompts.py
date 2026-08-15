from collections.abc import Sequence

from retrieval.schemas import FusedHit

# The judge maps a refusal to ABSTAINED (rubric rules 4 and 5), so the wording
# has to be stable and unmistakable — a paraphrased refusal reads as an answer.
ABSTENTION_SENTINEL = "I cannot answer this from the provided sources."

_PROMPT_TEMPLATE = """You are answering a research question using only the passages below.

{passages}

QUESTION: {question}

Rules:
- Answer only from the passages above. Do not use outside knowledge.
- If the passages do not contain the answer, reply with exactly this sentence and nothing else: {sentinel}
- Cite the arXiv id of every passage you rely on, in square brackets.
- Answer directly, with no preamble.
"""

_NO_PASSAGES = "(no passages were retrieved)"


def build_answer_prompt(question: str, hits: Sequence[FusedHit], max_chars: int) -> str:
    return _PROMPT_TEMPLATE.format(
        passages=_build_passages(hits, max_chars),
        question=question,
        sentinel=ABSTENTION_SENTINEL,
    )


def _build_passages(hits: Sequence[FusedHit], max_chars: int) -> str:
    if not hits:
        return _NO_PASSAGES

    parts: list[str] = []
    remaining = max_chars
    for index, hit in enumerate(hits, start=1):
        if remaining <= 0:
            break
        block = f"[{index}] arXiv {hit.arxiv_id} — {hit.section_title}{_pages(hit)}\n{hit.text}"
        parts.append(block[:remaining])
        remaining -= len(block)

    return "\n\n".join(parts)


def _pages(hit: FusedHit) -> str:
    if hit.page_start is None:
        return ""
    if hit.page_end is None or hit.page_end == hit.page_start:
        return f" (p{hit.page_start})"
    return f" (p{hit.page_start}-{hit.page_end})"
