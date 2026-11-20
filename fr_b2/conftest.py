"""Make the workspace root importable so ``from fr_b2 import ...`` works offline
without installing the package. Purely test scaffolding.
"""

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
if str(WS) not in sys.path:
    sys.path.insert(0, str(WS))
