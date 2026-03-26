from __future__ import annotations

import sys
from pathlib import Path


ACTION_SRC = Path(__file__).resolve().parents[2] / ".github/actions/ai-pr-review/src"
if str(ACTION_SRC) not in sys.path:
    sys.path.insert(0, str(ACTION_SRC))
