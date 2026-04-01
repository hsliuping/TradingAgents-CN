from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.factor_registry_service import get_factor_registry_service


def main() -> int:
    service = get_factor_registry_service()

    technical_screening_registry = service.list_registry(
        governance_scope="technical",
        screening_only=True,
    )
    screening_fields_markdown = service.build_screening_fields_markdown(public_only=True)
    ma60 = service.get_registry_item("ma60")
    ma20 = service.get_registry_item("ma20")

    failures: list[str] = []
    if technical_screening_registry["total"] < 8:
        failures.append("technical screening registry 数量小于 8")
    if not ma20 or ma20["governance_scope"] != "technical":
        failures.append("ma20 未正确标记为 technical 治理范围")
    if not ma20 or not ma20["is_registered_in_screening"]:
        failures.append("ma20 未正确标记为已注册 screening")
    if not ma20 or not ma20["is_public_screening_field"]:
        failures.append("ma20 未正确标记为公开 screening 字段")
    if "- ma20" not in screening_fields_markdown:
        failures.append("公开 screening 字段文档未包含 ma20")
    if not ma60:
        failures.append("ma60 注册表项缺失")
    else:
        if ma60["governance_scope"] != "technical":
            failures.append("ma60 未正确标记为 technical 治理范围")
        if ma60["is_registered_in_screening"]:
            failures.append("ma60 不应标记为已注册 screening")
        if ma60["is_public_screening_field"]:
            failures.append("ma60 不应标记为公开 screening 字段")
        if ma60["schema"]["included_in_screening"]:
            failures.append("ma60 schema 不应标记为 included_in_screening")
    if "- ma60" in screening_fields_markdown:
        failures.append("公开 screening 字段文档不应包含 ma60")

    report = {
        "technical_screening_total": technical_screening_registry["total"],
        "technical_screening_ids": [item["factor_id"] for item in technical_screening_registry["items"]],
        "screening_fields_markdown_preview": screening_fields_markdown.splitlines()[:12],
        "ma20": {
            "governance_scope": ma20["governance_scope"] if ma20 else None,
            "is_registered_in_screening": ma20["is_registered_in_screening"] if ma20 else None,
            "is_public_screening_field": ma20["is_public_screening_field"] if ma20 else None,
        },
        "ma60": {
            "governance_scope": ma60["governance_scope"] if ma60 else None,
            "is_registered_in_screening": ma60["is_registered_in_screening"] if ma60 else None,
            "is_public_screening_field": ma60["is_public_screening_field"] if ma60 else None,
            "included_in_screening": ma60["schema"]["included_in_screening"] if ma60 else None,
        },
        "failures": failures,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())