#!/usr/bin/env python3
"""Candidate-scoped Decision Evidence Pack v3 sync; never calls a model."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services.alphaguard.decision_evidence_pack_service import (  # noqa: E402
    DecisionEvidencePackService,
)
from app.services.alphaguard.real_model_validation_service import (  # noqa: E402
    RealModelValidationService,
)


async def run(args) -> int:
    if args.limit < 1 or args.limit > 10:
        raise SystemExit("--limit must be between 1 and 10")
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000,
    )
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB]
        validation = RealModelValidationService(db)
        samples = await validation._historical_samples(
            proposal_id=args.proposal_id,
            user_id=args.user_id,
            limit=args.limit,
        )
        results = []
        for sample in samples:
            proposal = sample["proposal"]
            source_snapshot = sample["wrapper"].evidence_snapshot
            result = await DecisionEvidencePackService(db).build(
                symbol=proposal.symbol,
                decision_time=source_snapshot.announcement_cutoff_at,
                source_trade_date=proposal.trade_date,
                source_snapshot_id=source_snapshot.snapshot_id,
                execute=args.execute,
            )
            manifest = result["manifest"]
            results.append(
                {
                    "symbol": proposal.symbol,
                    "trade_date": proposal.trade_date.isoformat(),
                    "source_proposal_id": proposal.proposal_id,
                    "source_snapshot_id": source_snapshot.snapshot_id,
                    "manifest_id": manifest["manifest_id"],
                    "status": result["status"],
                    "action": result["action"],
                    "matrix": manifest["evidence_completeness_matrix"],
                    "missing_fields": {
                        category: manifest[category]["missing_fields"]
                        for category in (
                            "financial_evidence",
                            "cashflow_evidence",
                            "dividend_evidence",
                            "announcement_evidence",
                        )
                    },
                    "source_statuses": {
                        category: manifest[category]["source_status"]
                        for category in (
                            "financial_evidence",
                            "cashflow_evidence",
                            "dividend_evidence",
                            "announcement_evidence",
                        )
                    },
                    "completeness_score": manifest["completeness_score"],
                    "source_writes": result["source_writes"],
                }
            )
        print(
            json.dumps(
                {
                    "mode": "EXECUTE" if args.execute else "DRY_RUN",
                    "model_calls": 0,
                    "sample_count": len(results),
                    "results": results,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if results else 2
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--proposal-id")
    parser.add_argument("--user-id")
    parser.add_argument("--limit", type=int, default=4)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
