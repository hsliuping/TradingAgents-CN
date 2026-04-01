from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import get_mongo_db_sync
from core.skill_runtime.data_access import expand_financial_document_to_periods


def _unique_key(record: Dict[str, object]) -> Tuple[str, str, str, str]:
    return (
        str(record.get("symbol") or record.get("code") or ""),
        str(record.get("source") or record.get("data_source") or ""),
        str(record.get("report_period") or record.get("report_date") or ""),
        str(record.get("ann_date") or ""),
    )


def _iter_source_documents(collection) -> Iterable[Dict[str, object]]:
    cursor = collection.find({}, {"_id": 0}).batch_size(100)
    for document in cursor:
        yield document


def main() -> int:
    db = get_mongo_db_sync()
    source_collection = db["stock_financial_data"]
    target_collection = db["stock_financial_periods"]

    processed_docs = 0
    written_records = 0

    for document in _iter_source_documents(source_collection):
        processed_docs += 1
        for record in expand_financial_document_to_periods(document):
            symbol, source, report_period, ann_date = _unique_key(record)
            if not symbol or not source or not report_period:
                continue
            target_collection.update_one(
                {
                    "symbol": symbol,
                    "source": source,
                    "report_period": report_period,
                    "ann_date": ann_date,
                },
                {"$set": record},
                upsert=True,
            )
            written_records += 1

        if processed_docs % 100 == 0:
            print(f"processed={processed_docs} written={written_records}")

    print(f"done processed={processed_docs} written={written_records}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())