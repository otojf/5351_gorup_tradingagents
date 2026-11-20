"""Make the package's parent (``src/``) importable so ``from fr_b2 import ...``
works without installing the package. Purely test scaffolding.

Under the D8 ``src/`` layout ``parents[1]`` is ``src/`` (the directory that
contains the ``fr_b2`` package), which is what must be on ``sys.path``.
"""

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))
