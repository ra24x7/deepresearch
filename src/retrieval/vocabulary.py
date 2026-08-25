"""The entity surface forms the router is allowed to anchor on.

Kept out of `router.py` so the router itself stays a pure function of a string
and a set: it does no IO, and every test can hand it a vocabulary literal.
"""

import json
from collections.abc import Iterable, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from textnorm import normalize

_SELECT_ENTITIES = text("SELECT entity_key, surface_forms FROM entities")


def build_entity_vocabulary(rows: Iterable[tuple[str, Sequence[str] | str]]) -> frozenset[str]:
    forms: set[str] = set()
    for entity_key, surface_forms in rows:
        for form in (entity_key, *_as_list(surface_forms)):
            normalized = normalize(form)
            if normalized:
                forms.add(normalized)
    return frozenset(forms)


def load_entity_vocabulary(engine: Engine) -> frozenset[str]:
    with engine.connect() as connection:
        return build_entity_vocabulary(connection.execute(_SELECT_ENTITIES).all())


def _as_list(surface_forms: Sequence[str] | str) -> Sequence[str]:
    # Postgres hands back a list; SQLite (and a plain JSON column) hands back text.
    return json.loads(surface_forms) if isinstance(surface_forms, str) else surface_forms
