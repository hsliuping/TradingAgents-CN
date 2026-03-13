from __future__ import annotations

import csv
from pathlib import Path
import sys

from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings


def main() -> None:
    output_path = Path("exports") / "tushare_stock_basic_info_industry.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = MongoClient(settings.MONGO_URI)
    try:
        db = client[settings.MONGODB_DATABASE]
        cursor = db.stock_basic_info.find(
            {"source": "tushare"},
            {"_id": 0, "code": 1, "name": 1, "industry": 1},
        ).sort("code", 1)

        rows = list(cursor)

        with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["code", "name", "industry"])
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "code": row.get("code", ""),
                        "name": row.get("name", ""),
                        "industry": row.get("industry", ""),
                    }
                )

        print(f"exported_rows={len(rows)}")
        print(f"output_path={output_path.as_posix()}")
    finally:
        client.close()


if __name__ == "__main__":
    main()