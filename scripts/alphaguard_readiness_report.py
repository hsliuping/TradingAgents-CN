#!/usr/bin/env python3
"""Read-only AlphaGuard readiness report; never seeds or repairs data."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services.alphaguard.operations_service import AlphaGuardOperationsService  # noqa: E402


def readiness_dimensions(report) -> dict[str, bool | str]:
    service_states = {
        item.status for item in report.service_health if item.required
    }
    if service_states & {"UNHEALTHY", "UNKNOWN", "NOT_CONFIGURED"}:
        runtime_ready: bool | str = False
    elif "DEGRADED" in service_states:
        runtime_ready = "DEGRADED"
    else:
        runtime_ready = True
    required_data = {
        "TRADING_CALENDAR",
        "QFQ_PRICE_DATA",
        "RAW_PRICE_DATA",
        "FINANCIAL_DATA",
        "NEWS_DATA",
        "ANNOUNCEMENT_DATA",
        "MARKET_CONTEXT",
        "INDUSTRY_HISTORY",
        "MODEL_PROVIDER",
        "CHAMPION_ASSIGNMENTS",
    }
    ready_components = {
        item.component
        for item in report.data_readiness
        if item.status == "READY"
    }
    return {
        "CODE_COMPLETE": True,
        "RUNTIME_READY": runtime_ready,
        "DATA_READY": required_data <= ready_components,
        "PAPER_READY": report.paper_execution_ready,
        "EVALUATION_READY": report.evaluation_ready,
        "EXPERIMENT_READY": report.experiment_ready,
        "CHALLENGER_READY": report.challenger_ready,
        "LIVE_READY": False,
    }


async def run(*, as_json: bool) -> int:
    mongo = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        db = mongo[settings.MONGO_DB]
        report = await AlphaGuardOperationsService(
            db, redis_client=redis, scheduler=None
        ).readiness(persist_alerts=False)
        payload = report.model_dump(mode="json")
        dimensions = readiness_dimensions(report)
        if as_json:
            print(
                json.dumps(
                    {
                        "readiness_dimensions": dimensions,
                        "system_readiness_report": payload,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"overall_status={report.overall_status}")
            print(f"system_mode={report.system_mode}")
            print(f"live_trading_enabled={str(report.live_trading_enabled).lower()}")
            for name, value in dimensions.items():
                rendered = str(value).lower() if isinstance(value, bool) else value
                print(f"{name}={rendered}")
            for item in report.data_readiness:
                reasons = ",".join(item.blocking_reasons) or "-"
                print(
                    f"data {item.component}: {item.status} "
                    f"records={item.record_count} blockers={reasons}"
                )
            if report.blocking_items:
                print("blocking_items:")
                for reason in report.blocking_items:
                    print(f"  - {reason}")
        return 0 if report.overall_status != "UNSAFE" else 2
    finally:
        await redis.aclose()
        mongo.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(as_json=args.json)))
