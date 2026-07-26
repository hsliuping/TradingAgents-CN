"""Automatic paper-account lifecycle and daily account snapshots."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
)
from tradingagents.alphaguard.paper_schemas import (
    DailyAccountSnapshot,
    PaperAccount,
    PaperPosition,
    PositionLot,
    paper_canonical_hash,
)


def _account_id(user_id: str, account_type: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"alphaguard:paper:{user_id}:{account_type}:CN"))


class PaperAccountConflictError(ValueError):
    pass


class PaperAccountService:
    def __init__(self, db):
        self.db = db
        self.accounts = db["ag_paper_accounts"]
        self.positions = db["ag_paper_positions"]
        self.lots = db["ag_paper_position_lots"]
        self.snapshots = db["ag_paper_account_snapshots"]
        self.audit = PaperAuditService(db)
        self.policies = PaperPolicyRegistry(db)

    async def initialize_user_accounts(
        self,
        user_id: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, PaperAccount]:
        policy = await self.policies.account_policy()
        now = now or datetime.utcnow()
        result: dict[str, PaperAccount] = {}
        for account_type in policy.account_types:
            identity = {
                "user_id": str(user_id),
                "account_type": account_type,
                "market": "CN",
            }
            existing = clean_document(await self.accounts.find_one(identity))
            if existing is not None:
                account = PaperAccount.model_validate(existing)
                if (
                    account.account_id != _account_id(str(user_id), account_type)
                    or account.currency != policy.currency
                ):
                    raise PaperAccountConflictError(
                        f"existing {account_type} account identity conflicts"
                    )
                result[account_type] = account
                await self.audit.record(
                    "PAPER_ACCOUNT_REUSED",
                    "existing automatic paper account reused without resetting balances",
                    user_id=str(user_id),
                    account_id=account.account_id,
                    account_type=account.account_type,
                    now=now,
                )
                continue
            account = PaperAccount(
                account_id=_account_id(str(user_id), account_type),
                user_id=str(user_id),
                account_type=account_type,
                market="CN",
                currency="CNY",
                status="ACTIVE",
                initial_cash=policy.initial_cash,
                cash_available=policy.initial_cash,
                cash_reserved=Decimal("0"),
                realized_pnl=Decimal("0"),
                total_fees=Decimal("0"),
                created_at=now,
                updated_at=now,
                account_config_version=policy.version,
            )
            await self.accounts.insert_one(model_document(account))
            result[account_type] = account
            await self.audit.record(
                "PAPER_ACCOUNT_CREATED",
                "automatic paper account created from versioned account policy",
                user_id=str(user_id),
                account_id=account.account_id,
                account_type=account.account_type,
                now=now,
            )
        return result

    async def get_account(
        self,
        account_id: str,
        *,
        user_id: str | None = None,
    ) -> PaperAccount | None:
        query = {"account_id": account_id}
        if user_id is not None:
            query["user_id"] = str(user_id)
        document = clean_document(await self.accounts.find_one(query))
        return PaperAccount.model_validate(document) if document else None

    async def get_user_account(
        self,
        user_id: str,
        account_type: str,
    ) -> PaperAccount | None:
        document = clean_document(
            await self.accounts.find_one(
                {
                    "user_id": str(user_id),
                    "account_type": account_type,
                    "market": "CN",
                }
            )
        )
        return PaperAccount.model_validate(document) if document else None

    async def list_accounts(self, user_id: str) -> list[PaperAccount]:
        documents = await self.accounts.find({"user_id": str(user_id)}).to_list(
            length=None
        )
        return [
            PaperAccount.model_validate(clean_document(document))
            for document in documents
        ]

    async def account_state_hash(self, account_id: str) -> str:
        account = await self.get_account(account_id)
        if account is None:
            raise LookupError("automatic paper account not found")
        positions = [
            clean_document(document)
            for document in await self.positions.find(
                {"account_id": account_id}
            ).to_list(length=None)
        ]
        lots = [
            clean_document(document)
            for document in await self.lots.find(
                {"account_id": account_id, "status": {"$in": ["OPEN", "PARTIALLY_CLOSED"]}}
            ).to_list(length=None)
        ]
        positions.sort(key=lambda item: (item["market"], item["symbol"]))
        lots.sort(key=lambda item: item["lot_id"])
        return paper_canonical_hash(
            {
                "account": account,
                "positions": positions,
                "lots": lots,
            },
            exclude={"updated_at", "account_version"},
        )

    async def roll_lot_availability(
        self,
        trade_date: date,
        *,
        now: datetime | None = None,
    ) -> int:
        now = now or datetime.utcnow()
        documents = await self.lots.find(
            {"status": {"$in": ["OPEN", "PARTIALLY_CLOSED"]}}
        ).to_list(length=None)
        affected_accounts: set[tuple[str, str]] = set()
        changed = 0
        for raw in documents:
            lot = PositionLot.model_validate(clean_document(raw))
            if lot.available_from_date > trade_date:
                continue
            marker = f"availability:{trade_date.isoformat()}"
            if marker in lot.applied_settlement_ids:
                continue
            lot = PositionLot.model_validate(
                lot.model_copy(
                    update={
                        "applied_settlement_ids": [
                            *lot.applied_settlement_ids,
                            marker,
                        ],
                        "updated_at": now,
                    }
                ).model_dump(mode="python")
            )
            await self.lots.replace_one({"lot_id": lot.lot_id}, model_document(lot))
            affected_accounts.add((lot.account_id, lot.symbol))
            changed += 1
            await self.audit.record(
                "POSITION_AVAILABILITY_ROLLED",
                "position lot reached its persisted next trading date",
                account_id=lot.account_id,
                symbol=lot.symbol,
                trade_date=trade_date,
                now=now,
            )
        for account_id, symbol in affected_accounts:
            await self.rebuild_position(
                account_id,
                symbol,
                as_of_date=trade_date,
                now=now,
            )
        return changed

    async def rebuild_position(
        self,
        account_id: str,
        symbol: str,
        *,
        as_of_date: date | None = None,
        now: datetime | None = None,
    ) -> PaperPosition:
        now = now or datetime.utcnow()
        as_of_date = as_of_date or now.date()
        raw_lots = await self.lots.find(
            {
                "account_id": account_id,
                "symbol": symbol,
                "status": {"$in": ["OPEN", "PARTIALLY_CLOSED"]},
            }
        ).to_list(length=None)
        lots = [
            PositionLot.model_validate(clean_document(document))
            for document in raw_lots
        ]
        quantity = sum(lot.remaining_quantity for lot in lots)
        reserved = sum(lot.reserved_quantity for lot in lots)
        available = sum(
            lot.remaining_quantity - lot.reserved_quantity
            for lot in lots
            if lot.available_from_date <= as_of_date
        )
        total_cost = sum(
            (lot.unit_cost * lot.remaining_quantity for lot in lots),
            Decimal("0"),
        )
        average = total_cost / quantity if quantity else Decimal("0")
        existing = clean_document(
            await self.positions.find_one(
                {"account_id": account_id, "market": "CN", "symbol": symbol}
            )
        )
        realized = Decimal(str(existing.get("realized_pnl", "0"))) if existing else Decimal("0")
        fees = Decimal(str(existing.get("total_fees", "0"))) if existing else Decimal("0")
        applied = list(existing.get("applied_settlement_ids", [])) if existing else []
        position = PaperPosition(
            position_id=(
                existing.get("position_id")
                if existing
                else str(uuid5(NAMESPACE_URL, f"alphaguard:position:{account_id}:CN:{symbol}"))
            ),
            account_id=account_id,
            symbol=symbol,
            market="CN",
            currency="CNY",
            quantity=quantity,
            available_quantity=available,
            reserved_quantity=reserved,
            average_cost=average,
            total_cost=total_cost,
            realized_pnl=realized,
            total_fees=fees,
            applied_settlement_ids=applied,
            updated_at=now,
        )
        await self.positions.replace_one(
            {"account_id": account_id, "market": "CN", "symbol": symbol},
            model_document(position),
            upsert=True,
        )
        return position

    async def create_daily_snapshot(
        self,
        account_id: str,
        trade_date: date,
        *,
        now: datetime | None = None,
    ) -> DailyAccountSnapshot:
        existing = clean_document(
            await self.snapshots.find_one(
                {"account_id": account_id, "trade_date": trade_date}
            )
        )
        if existing:
            return DailyAccountSnapshot.model_validate(existing)
        account = await self.get_account(account_id)
        if account is None:
            raise LookupError("automatic paper account not found")
        positions = [
            PaperPosition.model_validate(clean_document(document))
            for document in await self.positions.find(
                {"account_id": account_id, "quantity": {"$gt": 0}}
            ).to_list(length=None)
        ]
        market_value = Decimal("0")
        price_refs: list[str] = []
        missing: list[str] = []
        for position in positions:
            raw = clean_document(
                await self.db["ag_execution_market_snapshots"].find_one(
                    {
                        "symbol": position.symbol,
                        "market": "CN",
                        "trade_date": trade_date,
                    }
                )
            )
            if raw is None:
                missing.append(position.symbol)
                continue
            market_value += Decimal(str(raw["close"])) * position.quantity
            price_refs.append(str(raw["execution_snapshot_id"]))
        total_cost = sum((position.total_cost for position in positions), Decimal("0"))
        unrealized = market_value - total_cost
        equity = account.cash_available + account.cash_reserved + market_value
        gross = float(market_value / equity) if equity > 0 else 0.0
        now = now or datetime.utcnow()
        payload = {
            "account_id": account_id,
            "trade_date": trade_date,
            "cash_available": account.cash_available,
            "cash_reserved": account.cash_reserved,
            "position_market_value": market_value,
            "total_equity": equity,
            "realized_pnl": account.realized_pnl,
            "unrealized_pnl": unrealized,
            "total_fees": account.total_fees,
            "gross_exposure_pct": gross,
            "position_count": len(positions),
            "price_refs": sorted(price_refs),
            "valuation_complete": not missing,
            "missing_price_symbols": sorted(missing),
        }
        snapshot = DailyAccountSnapshot(
            account_snapshot_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:account-snapshot:{account_id}:{trade_date.isoformat()}",
                )
            ),
            **payload,
            input_hash=paper_canonical_hash(payload),
            created_at=now,
        )
        await self.snapshots.insert_one(model_document(snapshot))
        await self.audit.record(
            "ACCOUNT_SNAPSHOT_CREATED",
            (
                "daily account snapshot created"
                if snapshot.valuation_complete
                else "daily account snapshot created with explicit missing prices"
            ),
            user_id=account.user_id,
            account_id=account_id,
            account_type=account.account_type,
            trade_date=trade_date,
            now=now,
        )
        return snapshot
