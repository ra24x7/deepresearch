_PRIORITY_TITLE_KEYWORDS = ("introduction", "method", "result", "conclusion")

_PROMPT_TEMPLATE = """You are extracting verifiable claims and named entities from an academic paper.

Paper title: {title}

{body}

Return STRICT JSON only, with this exact shape:
{{"claims": [{{"text": "...", "section_title": "..."}}], "entities": [{{"surface_form": "...", "entity_type": "..."}}]}}

Rules:
- claims: 5 to 15 atomic, verifiable statements of the paper's contributions.
- entity_type must be one of: method, dataset, metric, task.
- Output valid JSON with no markdown fences, no commentary, no trailing text.
"""


def build_enrichment_prompt(title: str, abstract: str, sections: list[tuple[str, str]], max_chars: int) -> str:
    body = _build_body(abstract, sections, max_chars)
    return _PROMPT_TEMPLATE.format(title=title, body=body)


def _build_body(abstract: str, sections: list[tuple[str, str]], max_chars: int) -> str:
    parts = [f"Abstract: {abstract}"]
    remaining = max_chars - len(parts[0])

    for section_title, text in _prioritize(sections):
        if remaining <= 0:
            break
        chunk = f"\n\n## {section_title}\n{text}"
        if len(chunk) > remaining:
            chunk = chunk[:remaining]
        parts.append(chunk)
        remaining -= len(chunk)

    return "".join(parts)


def _prioritize(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return sorted(sections, key=_section_priority)


def _section_priority(section: tuple[str, str]) -> int:
    title = section[0].lower()
    for rank, keyword in enumerate(_PRIORITY_TITLE_KEYWORDS):
        if keyword in title:
            return rank
    return len(_PRIORITY_TITLE_KEYWORDS)
