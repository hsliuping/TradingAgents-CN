from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.technical_indicator_materialization_service import materialize_technical_indicators


def main() -> int:
    materialize_technical_indicators(progress_every=200, progress_logger=print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())