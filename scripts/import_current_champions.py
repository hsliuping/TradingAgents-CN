#!/usr/bin/env python3
"""Import exact PR-004 current components as PR-008 Champion pointers.

This script does not infer a Champion from the highest version.  It is dry-run
by default and never modifies the source definitions/configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.champion_resolver import (
    assignment_hash,
    champion_slot_id,
)
from app.services.alphaguard.experiment_component_adapters import (
    build_current_component_record,
    current_component_payloads,
)
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import experiment_document
from app.services.alphaguard.promotion_policy_service import PromotionPolicyService
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.experiment_schemas import ChampionAssignment


def _assign(record, *, effective_date: date) -> ChampionAssignment:
    payload = {
        "champion_slot_id": champion_slot_id(
            record.component_type, record.component_key, record.market
        ),
        "component_type": record.component_type,
        "component_key": record.component_key,
        "market": record.market,
        "current_version_ref": record.version_ref,
        "previous_version_ref": None,
        "source_experiment_id": None,
        "source_promotion_request_id": None,
        "effective_from_trade_date": effective_date,
        "assignment_version": 1,
        "status": "ACTIVE",
        "promotion_saga_id": None,
        "updated_by": "scripts/import_current_champions.py",
        "updated_at": datetime.utcnow(),
    }
    payload["assignment_hash"] = assignment_hash(payload)
    return ChampionAssignment.model_validate(payload)


async def main(execute: bool, effective_date: date) -> None:
    records = [
        build_current_component_record(
            descriptor,
            created_by="scripts/import_current_champions.py",
        )
        for descriptor in current_component_payloads()
    ]
    for record in records:
        assignment = _assign(record, effective_date=effective_date)
        print(
            f"slot={assignment.champion_slot_id} "
            f"version={assignment.current_version_ref} "
            f"component_hash={record.payload_hash}"
        )
    if not execute:
        print("dry-run: no versions or Champion pointers written")
        return
    await init_database()
    try:
        db = get_mongo_db()
        registry = ExperimentRegistry(db)
        created = reused = conflicts = 0
        expected_assignments = [
            _assign(record, effective_date=effective_date) for record in records
        ]
        for assignment in expected_assignments:
            existing = clean_document(
                await db["ag_exp_champion_assignments"].find_one(
                    {"champion_slot_id": assignment.champion_slot_id}
                )
            )
            if existing is not None and (
                existing.get("current_version_ref")
                != assignment.current_version_ref
                or existing.get("component_type") != assignment.component_type
                or existing.get("component_key") != assignment.component_key
                or existing.get("market") != assignment.market
                or existing.get("assignment_hash")
                != assignment.assignment_hash
            ):
                conflicts += 1
                print(
                    "conflict "
                    f"slot={assignment.champion_slot_id} "
                    f"existing={existing.get('current_version_ref')} "
                    f"expected={assignment.current_version_ref}"
                )
        if conflicts:
            raise RuntimeError(
                "Champion import conflicts detected; no import writes performed"
            )
        await PromotionPolicyService(db).register_builtin()
        for record, assignment in zip(records, expected_assignments):
            _, was_created = await registry.register_component_version(record)
            created += int(was_created)
            reused += int(not was_created)
            existing = clean_document(
                await db["ag_exp_champion_assignments"].find_one(
                    {"champion_slot_id": assignment.champion_slot_id}
                )
            )
            if existing is None:
                await db["ag_exp_champion_assignments"].insert_one(
                    experiment_document(assignment)
                )
                created += 1
            else:
                reused += 1
        print(
            f"created={created} reused={reused} conflicts={conflicts} failed=0"
        )
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--effective-date",
        type=date.fromisoformat,
        help=(
            "explicit initial Champion effective date (YYYY-MM-DD); "
            "required with --execute"
        ),
    )
    args = parser.parse_args()
    if args.execute and args.effective_date is None:
        parser.error("--effective-date is required with --execute")
    asyncio.run(main(args.execute, args.effective_date or date.today()))
