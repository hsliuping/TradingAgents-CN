"""检查 managers_v2/risk_manager_v2 的 live 提示词模板。

默认只输出摘要；加 --show-system-prompt 可打印完整 system_prompt。
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=False)

from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name

_builder_path = PROJECT_ROOT / "scripts" / "template_upgrades"
sys.path.insert(0, str(_builder_path))
from update_research_brief_v2_prompts import PREFERENCE_CONFIG, get_template_name


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 managers_v2/risk_manager_v2 的 live 提示词模板")
    parser.add_argument(
        "--show-system-prompt",
        action="store_true",
        help="打印完整 system_prompt",
    )
    args = parser.parse_args()

    client = MongoClient(build_mongodb_connection_string())
    db = client[get_mongodb_database_name()]
    collection = db.prompt_templates

    templates = list(
        collection.find(
            {
                "agent_type": "managers_v2",
                "agent_name": "risk_manager_v2",
                "status": "active",
            }
        ).sort("preference_type", 1)
    )

    expected_template_names = {
        get_template_name("risk_manager_v2", preference_type) for preference_type in PREFERENCE_CONFIG.keys()
    }
    v2_templates = [item for item in templates if item.get("template_name") in expected_template_names]
    ignored_templates = [item for item in templates if item.get("template_name") not in expected_template_names]

    print(f"找到 {len(templates)} 个 managers_v2/risk_manager_v2 live 模板")
    print(f"其中 v2.0 模板: {len(v2_templates)} 个")
    print(f"忽略非 v2.0 模板: {len(ignored_templates)} 个\n")

    if ignored_templates:
        print("已忽略的非 v2.0 模板：")
        for item in ignored_templates:
            print(f"  - {item.get('template_name', 'N/A')} (preference={item.get('preference_type')})")
        print()

    for idx, template in enumerate(v2_templates, 1):
        _id = template.get("_id")
        preference = template.get("preference_type", "N/A")
        template_name = template.get("template_name", "N/A")
        is_system = template.get("is_system", False)
        status = template.get("status", "N/A")
        version = template.get("version", "N/A")

        content = template.get("content", {}) or {}
        system_prompt = content.get("system_prompt", "")
        output_format = content.get("output_format", "")

        has_json = "json" in output_format.lower() or "```json" in output_format.lower()
        has_trade_action = (
            "买入" in system_prompt
            or "卖出" in system_prompt
            or "buy" in system_prompt.lower()
            or "sell" in system_prompt.lower()
        )
        has_final_decision = "final_trade_decision" in system_prompt.lower()

        print(f"{'=' * 80}")
        print(f"模板 {idx}: {preference} 偏好")
        print(f"  - _id: {_id}")
        print(f"  - template_name: {template_name}")
        print(f"  - version: {version}")
        print(f"  - is_system: {is_system}")
        print(f"  - status: {status}")
        print(f"  - output_format 要求 JSON: {'✅' if has_json else '❌'}")
        print(f"  - system_prompt 含交易动作词: {'✅' if has_trade_action else '❌'}")
        print(f"  - system_prompt 含 final_trade_decision: {'✅' if has_final_decision else '❌'}")

        if args.show_system_prompt:
            print("\n系统提示词:")
            print(f"{'-' * 80}")
            print(system_prompt)
            print()

    print(f"\n{'=' * 80}")
    print("按偏好分组:")
    print(f"{'=' * 80}\n")

    by_preference = defaultdict(list)
    for item in v2_templates:
        by_preference[item.get("preference_type", "N/A")].append(item)

    for preference, items in by_preference.items():
        print(f"{preference}: {len(items)} 个模板")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

