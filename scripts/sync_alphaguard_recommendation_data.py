#!/usr/bin/env python3
"""Probe or activate the versioned full-market recommendation data contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import (
    close_database,
    connect_database,
    get_mongo_db,
    init_database,
)
from app.services.alphaguard.candidate_recommendation_policy import (
    CandidateRecommendationPolicyRegistry,
)
from app.services.alphaguard.candidate_recommendation_service import (
    CandidateRecommendationService,
)
from app.services.alphaguard.recommendation_data_service import (
    BaoStockRecommendationProvider,
    RecommendationDataService,
)


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(type(value).__name__)


def _print(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default))


async def _probe(
    provider: BaoStockRecommendationProvider,
    *,
    trade_date: date,
) -> None:
    master = await asyncio.to_thread(provider.fetch_master)
    selected = {
        str(row.get("code") or "").split(".")[-1]: str(row.get("code") or "")
        for row in master.rows
        if str(row.get("code") or "").split(".")[-1]
        in {"000001", "300750", "600519"}
    }
    start = date.fromordinal(trade_date.toordinal() - 120)
    prices = await asyncio.to_thread(
        provider.fetch_prices,
        selected,
        start=start,
        end=trade_date,
        max_attempts=1,
    )
    benchmark = await asyncio.to_thread(
        provider.fetch_benchmark, start=start, end=trade_date
    )
    _print(
        {
            "mode": "PROVIDER_PROBE",
            "write": False,
            "trade_date": trade_date,
            "provider": master.provider,
            "provider_version": master.provider_version,
            "master_equity_count": len(master.rows),
            "sample_counts": {
                symbol: len(rows) for symbol, rows in prices.rows_by_symbol.items()
            },
            "benchmark_count": len(benchmark.rows_by_symbol.get("000300", ())),
            "failure_count": len(prices.failures) + len(benchmark.failures),
        }
    )


async def main(args: argparse.Namespace) -> None:
    if args.execute:
        await init_database()
    else:
        await connect_database()
    try:
        db = get_mongo_db()
        recommendation = CandidateRecommendationService(db)
        trade_date = (
            date.fromisoformat(args.trade_date)
            if args.trade_date
            else await recommendation.resolve_latest_trade_date()
        )
        if args.probe:
            await _probe(BaoStockRecommendationProvider(), trade_date=trade_date)
            return
        if not args.execute:
            _print(
                {
                    "mode": "DRY_RUN",
                    "write": False,
                    "trade_date": trade_date,
                    "next_action": "pass --probe or --execute",
                }
            )
            return
        now = datetime.utcnow()
        policy = await CandidateRecommendationPolicyRegistry(db).get_active()
        universe = await recommendation.build_universe_manifest(
            universe_date=trade_date,
            policy=policy,
            now=now,
        )
        data_service = RecommendationDataService(db)
        sync = await data_service.sync_full_market(
            universe=universe,
            trade_date=trade_date,
            execute=True,
            now=now,
        )
        universe = await recommendation.build_universe_manifest(
            universe_date=trade_date,
            policy=policy,
            now=now,
        )
        securities = {
            str(row.get("code") or row.get("symbol")): row
            for row in await recommendation._load_universe_rows()
        }
        coverage = await data_service.prepare_coverage(
            universe=universe,
            securities=securities,
            policy=policy,
            trade_date=trade_date,
            execute=True,
            now=now,
            sync_summary=sync,
        )
        output = {
            "mode": "EXECUTE",
            "write": True,
            "sync": {
                key: value
                for key, value in sync.items()
                if key not in {"failed_symbols", "batch_metrics"}
            },
            "failure_count": len(sync["failed_symbols"]),
            "coverage": coverage.model_dump(mode="json"),
        }
        if args.scan_user_id:
            run, created = await recommendation.run(
                user_id=args.scan_user_id,
                trade_date=trade_date,
            )
            output["scan"] = {
                "recommendation_run_id": run.recommendation_run_id,
                "run_action": "CREATED" if created else "REUSED",
                "eligible_securities": run.eligible_securities,
                "scored_securities": run.scored_securities,
                "recommended_securities": run.recommended_securities,
                "failed_symbol_count": len(run.failed_symbols),
                "duration_ms": run.duration_ms,
            }
        _print(output)
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--scan-user-id")
    args = parser.parse_args()
    if args.probe and args.execute:
        parser.error("--probe and --execute are mutually exclusive")
    if args.scan_user_id and not args.execute:
        parser.error("--scan-user-id requires --execute")
    asyncio.run(main(args))
