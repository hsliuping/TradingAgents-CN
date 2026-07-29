#!/usr/bin/env python3
"""Start the isolated AlphaGuard frontend acceptance API.

The command defaults to a read-only configuration preview. ``--execute`` is
required because the demo persists one fixture document in a dedicated local
database. It never imports the production FastAPI application.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_DATABASE = "alphaguard_ui_demo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="start the isolated demo API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    return parser.parse_args()


def configure_environment() -> None:
    os.environ["ALPHAGUARD_UI_DEMO"] = "true"
    os.environ["MONGODB_DATABASE"] = DEMO_DATABASE
    os.environ["MONGODB_DATABASE_NAME"] = DEMO_DATABASE
    os.environ["MONGODB_DATABASE_SCOPE"] = "explicit"
    # The legacy ConfigManager is imported indirectly by timezone helpers. It
    # must not open its separate token-usage connection in the UI demo.
    os.environ["USE_MONGODB_STORAGE"] = "false"
    os.environ["QUOTES_BACKFILL_ON_STARTUP"] = "false"
    os.environ["QUOTES_INGEST_ENABLED"] = "false"
    os.environ["TUSHARE_UNIFIED_ENABLED"] = "false"
    os.environ["AKSHARE_UNIFIED_ENABLED"] = "false"
    os.environ["BAOSTOCK_UNIFIED_ENABLED"] = "false"
    os.environ["NEWS_SYNC_ENABLED"] = "false"
    os.environ["LIVE_TRADING_ENABLED"] = "false"


def main() -> int:
    args = parse_args()
    print(f"mode={'execute' if args.execute else 'dry-run'}")
    print(f"database={DEMO_DATABASE}")
    print("scheduler=false workers=false backfill=false live=false")
    print(f"api=http://{args.host}:{args.port}")
    if not args.execute:
        print("No database write or server start performed. Add --execute to continue.")
        return 0
    configure_environment()
    sys.path.insert(0, str(ROOT))
    import uvicorn

    uvicorn.run(
        "app.demo.alphaguard_ui_demo:app",
        host=args.host,
        port=args.port,
        reload=False,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
