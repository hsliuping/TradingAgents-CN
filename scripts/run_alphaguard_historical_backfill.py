#!/usr/bin/env python3
"""Plan, execute, resume, or report isolated historical research backfill."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.alphaguard.historical_backfill_service import (
    HistoricalBackfillService,
)
from tradingagents.alphaguard.instruments import normalize_instrument


async def _admin_user(db, args: argparse.Namespace) -> dict:
    clauses: list[dict] = []
    if args.user_id:
        clauses.extend([{"_id": args.user_id}, {"id": args.user_id}])
        if ObjectId.is_valid(args.user_id):
            clauses.append({"_id": ObjectId(args.user_id)})
    if args.username:
        clauses.append({"username": args.username})
    if not clauses:
        raise SystemExit("--user-id or --username is required")
    user = await db["users"].find_one({"$or": clauses})
    if (
        user is None
        or user.get("is_admin") is not True
        or user.get("is_active") is False
    ):
        raise SystemExit("historical backfill requires an active administrator")
    return user


def _user_id(user: dict) -> str:
    return str(user.get("id") or user.get("_id"))


async def main(args: argparse.Namespace) -> None:
    if args.as_of_trade_date > date.today():
        raise SystemExit("--as-of-trade-date cannot be in the future")
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB]
        service = HistoricalBackfillService(db)
        if args.report_only:
            report = await service.build_report(args.report_only)
            print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
            return

        if args.resume:
            user = await _admin_user(db, args)
            existing = await db["ag_research_backfill_runs"].find_one(
                {"backfill_run_id": args.resume}
            )
            if existing is None:
                raise SystemExit("--resume backfill_run_id does not exist")
            if str(existing.get("user_id")) != _user_id(user):
                raise SystemExit("administrator does not own the requested backfill run")
            if not args.execute:
                print(
                    json.dumps(
                        {
                            "write": False,
                            "resume_backfill_run_id": args.resume,
                            "status": existing.get("status"),
                            "completed_samples": existing.get("completed_samples", 0),
                            "skipped_samples": existing.get("skipped_samples", 0),
                            "failed_samples": existing.get("failed_samples", 0),
                        },
                        ensure_ascii=False,
                        default=str,
                        indent=2,
                    )
                )
                print("dry-run: no research or evaluation writes performed")
                return
            run, report = await service.run(
                backfill_run_id=args.resume,
                as_of_trade_date=args.as_of_trade_date,
                model_replay=False,
            )
            print(
                json.dumps(
                    {"run": run.model_dump(mode="json"), "report": report.model_dump(mode="json")},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        user = await _admin_user(db, args)
        symbols = sorted(
            {
                normalize_instrument(symbol, "CN")[1]
                for symbol in (args.symbol or [])
            }
        )
        if not symbols:
            raise SystemExit("at least one explicit --symbol is required")
        selected = await service.select_trade_dates(
            start_trade_date=args.start,
            end_trade_date=args.end,
            sampling_method=args.sampling_method,
        )
        plan = {
            "write": args.execute,
            "user_id": _user_id(user),
            "symbols": symbols,
            "start_trade_date": args.start,
            "end_trade_date": args.end,
            "sampling_method": args.sampling_method,
            "selected_trade_dates": selected,
            "planned_sample_count": len(symbols) * len(selected),
            "run_mode": "RESEARCH_BACKFILL",
            "research_only": True,
            "automated_execution_allowed": False,
            "model_replay": False,
        }
        print(json.dumps(plan, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no research or evaluation writes performed")
            return
        run, _ = await service.create_run(
            user_id=_user_id(user),
            symbols=symbols,
            start_trade_date=args.start,
            end_trade_date=args.end,
            sampling_method=args.sampling_method,
        )
        completed, report = await service.run(
            backfill_run_id=run.backfill_run_id,
            as_of_trade_date=args.as_of_trade_date,
            model_replay=False,
        )
        print(
            json.dumps(
                {
                    "run": completed.model_dump(mode="json"),
                    "report": report.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id")
    parser.add_argument("--username")
    parser.add_argument("--symbol", action="append")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 6, 30))
    parser.add_argument(
        "--sampling-method",
        choices=["WEEKLY_LAST_SESSION", "DAILY"],
        default="WEEKLY_LAST_SESSION",
    )
    parser.add_argument(
        "--as-of-trade-date", type=date.fromisoformat, default=date.today()
    )
    parser.add_argument("--resume")
    parser.add_argument("--report-only")
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
