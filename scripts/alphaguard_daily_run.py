#!/usr/bin/env python3
"""Controlled one-command AlphaGuard daily operation; dry-run by default."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.alphaguard_config import validate_alphaguard_startup_safety  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.alphaguard.daily_jobs import daily_input_version  # noqa: E402
from app.services.alphaguard.daily_run_service import (  # noqa: E402
    AlphaGuardDailyRunService,
    DAILY_STAGE_SPECS,
)
from app.services.alphaguard.daily_stage_executor import (  # noqa: E402
    ProductionDailyStageExecutor,
)


def _reject_live_arguments(argv: list[str]) -> None:
    for argument in argv:
        normalized = argument.strip().lower()
        if normalized == "--live" or normalized.startswith("--live=") or normalized == "live=true":
            raise SystemExit("拒绝启动：AlphaGuard MVP 不接受 live=true 或 --live")


def _print_summary(summary) -> None:
    print(
        f"daily_run_id={summary.daily_run_id} trade_date={summary.trading_date} "
        f"status={summary.status} live=false"
    )
    categories = ["数据同步", "推荐", "候选池", "决策", "模型", "风控", "订单", "评价", "异常"]
    stage_categories = {item.stage_id: item.category for item in DAILY_STAGE_SPECS}
    for category in categories:
        rows = [item for item in summary.stages if stage_categories[item.stage_id] == category]
        if not rows:
            continue
        status = "通过" if all(item.status in {"SUCCESS", "REUSED", "SKIPPED"} for item in rows) else "异常"
        output_count = sum(item.output_count for item in rows)
        details = "；".join(f"{item.stage_name}:{item.status}" for item in rows)
        print(f"{category}: {status}，输出={output_count}，{details}")
    if summary.blocking_reason:
        print(f"阻断原因: {summary.blocking_reason}")


async def run(args) -> int:
    validate_alphaguard_startup_safety()
    input_version = args.input_version or daily_input_version()
    mongo = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await mongo.admin.command("ping")
        db = mongo[settings.MONGO_DB]
        service = AlphaGuardDailyRunService(
            db,
            executor=ProductionDailyStageExecutor(db, redis_client=redis),
        )
        if args.status:
            summary = await service.status(
                trading_date=args.trade_date, input_version=input_version
            )
        else:
            summary = await service.run(
                trading_date=args.trade_date,
                input_version=input_version,
                dry_run=not args.execute,
                resume=args.resume,
                from_stage=args.from_stage,
                to_stage=args.to_stage,
            )
        _print_summary(summary)
        return 0 if summary.status in {"SUCCESS", "DRY_RUN", "NOT_FOUND"} else 2
    finally:
        await redis.aclose()
        mongo.close()


if __name__ == "__main__":
    _reject_live_arguments(sys.argv[1:])
    parser = argparse.ArgumentParser(
        description="AlphaGuard盘后每日运行；默认dry-run，显式--execute才执行写操作"
    )
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="兼容显式预览；默认即为dry-run")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--from-stage", choices=[item.stage_id for item in DAILY_STAGE_SPECS])
    parser.add_argument("--to-stage", choices=[item.stage_id for item in DAILY_STAGE_SPECS])
    parser.add_argument("--input-version")
    parsed = parser.parse_args()
    if parsed.execute and parsed.dry_run:
        parser.error("--execute 与 --dry-run 不能同时使用")
    raise SystemExit(asyncio.run(run(parsed)))
