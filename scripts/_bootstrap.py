"""Put src/ on sys.path. Import first, for the side effect:

    import _bootstrap  # noqa: F401

Scripts run as files rather than as package modules, so src/ is not importable
until something adds it; every script carried its own copy of that line.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
