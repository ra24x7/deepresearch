import re

# Sections that are bibliographic apparatus, not retrievable content. Their text
# still lives in Postgres — the arXiv-id entity miner reads it to build the
# citation graph; only the searchable index drops it.
# Word-bounded so "ACMReference Format" is not mistaken for a bibliography.
_BIBLIOGRAPHIC = re.compile(r"^\W*\d*\W*(references?|bibliography)\W*$", re.IGNORECASE)
_TITLE_SEPARATOR = " + "


def is_indexable_section(section_title: str) -> bool:
    # Small sections merge forward into the next one, so a title like
    # "Conclusion + References" carries real content: exclude only when every
    # merged component is bibliographic.
    components = [part.strip() for part in section_title.split(_TITLE_SEPARATOR) if part.strip()]
    if not components:
        return True
    return not all(_is_bibliographic(component) for component in components)


def _is_bibliographic(component: str) -> bool:
    # Strip a leading section number ("VIII.", "8") before matching.
    without_numbering = re.sub(r"^[\divxlc]+[.)]?\s*", "", component, flags=re.IGNORECASE)
    return bool(_BIBLIOGRAPHIC.match(without_numbering))
