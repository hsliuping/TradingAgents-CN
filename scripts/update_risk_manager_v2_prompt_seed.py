"""更新 risk_manager_v2 系统种子提示词的 output_format / constraints 字段。

目的：
    将 risk_manager_v2 的输出格式从"请使用结构化的方式输出分析报告"更新为
    包含合规要求的 JSON schema 契约提示，配合
    core/agents/adapters/risk_manager_v2.py 中的 RISK_ASSESSMENT_SCHEMA_PROMPT
    前置契约和 pydantic schema 校验。

合规要求：
    - action / investment_adjustment 只能取值 "乐观"/"审慎"/"中性"
    - 禁止使用 "看涨/看跌/买入/卖出" 等交易指令或市场观点术语

⚠️ 仅更新系统种子模板（is_system=True 或 remark 包含 system_seed），
   不影响用户自定义模板（user_id 非空）和工作流专属模板（workflow_id 非空）。

用法：
    env\\Scripts\\python.exe scripts\\update_risk_manager_v2_prompt_seed.py          # 预览模式
    env\\Scripts\\python.exe scripts\\update_risk_manager_v2_prompt_seed.py --apply  # 执行写库

⚠️ 确保连接的是 v3.0 数据库（MongoDB 端口 27019）。
   参考 .env 中的 MONGODB_PORT 配置（main 分支对应 v3.0）。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=False)

from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name

# 新的 output_format / constraints 值
# 必须与 app/services/system_prompt_seed_service.py 中 risk_manager_v2 的种子保持一致
NEW_OUTPUT_FORMAT = (
    "必须输出 JSON 对象，包含 risk_level/risk_score/reasoning/key_risks/risk_control/"
    "investment_adjustment/final_trade_decision 字段。investment_adjustment 与 action "
    '只能取值"乐观"/"审慎"/"中性"，禁止使用"看涨"/"看跌"/"买入"/"卖出"等交易指令'
    "或市场观点术语。只输出 JSON，不要 markdown 代码块包裹。"
)

NEW_CONSTRAINTS = (
    "禁止输出买卖、加减仓、目标价、价格区间、止损止盈或执行节奏；"
    '禁止使用"看涨/看跌/买入/卖出"等术语，统一使用"乐观/审慎/中性"表达研究结论倾向。'
)

# 合规术语约束追加段落（用于在已有 constraints 末尾追加，保留原有风格内容）
COMPLIANCE_CONSTRAINTS_SUFFIX = (
    '\n\n【合规术语约束】investment_adjustment 与 final_trade_decision.action 只能取值'
    '"乐观"/"审慎"/"中性"，禁止使用"看涨/看跌/买入/卖出/加仓/减仓/持有/清仓"等'
    "交易指令或市场观点术语。"
)

REMARK_SUFFIX = "[2026-07-28] risk_manager_v2 schema 契约+合规术语：output_format 改为 JSON schema，action/investment_adjustment 统一为乐观/审慎/中性"


def _merge_constraints(current: str) -> str:
    """在已有 constraints 末尾追加合规术语约束，保留原有风格内容。

    若已有 constraints 包含合规术语关键词（"乐观"或"审慎"），则视为已更新，不重复追加。
    """
    current = (current or "").rstrip()
    if "乐观" in current or "审慎" in current:
        return current
    return current + COMPLIANCE_CONSTRAINTS_SUFFIX


def main() -> int:
    parser = argparse.ArgumentParser(description="更新 risk_manager_v2 系统种子提示词的 output_format / constraints")
    parser.add_argument("--apply", action="store_true", help="执行实际写库更新（不加则为预览模式）")
    args = parser.parse_args()

    conn_str = build_mongodb_connection_string()
    db_name = get_mongodb_database_name()
    print(f"📡 MongoDB 数据库：{db_name}")
    print(f"   ⚠️ 请确认连接端口为 27019（v3.0），参考 .env 中 MONGODB_PORT 配置\n")

    client = MongoClient(conn_str)
    db = client[db_name]
    collection = db.prompt_templates

    # 查询 risk_manager_v2 的所有模板
    query = {
        "agent_type": "managers_v2",
        "agent_name": "risk_manager_v2",
    }
    docs = list(collection.find(query))

    if not docs:
        print("⚠️ 未找到 risk_manager_v2 的任何模板，请检查数据库。")
        client.close()
        return 1

    print(f"找到 {len(docs)} 条 risk_manager_v2 模板")

    # 筛选系统种子模板（is_system=True 或 remark 包含 system_seed，且 user_id 为空）
    system_seed_docs: list[dict] = []
    skipped_docs: list[dict] = []
    for doc in docs:
        is_system = doc.get("is_system", False)
        remark = doc.get("remark") or ""
        user_id = doc.get("user_id")
        workflow_id = doc.get("workflow_id")
        is_seed = is_system or "system_seed" in remark
        if is_seed and not user_id and not workflow_id:
            system_seed_docs.append(doc)
        else:
            skipped_docs.append(doc)

    if skipped_docs:
        print(f"  （跳过 {len(skipped_docs)} 条用户自定义/工作流专属模板，仅更新系统种子）")

    if not system_seed_docs:
        print("⚠️ 未找到系统种子模板（is_system=True 或 remark 含 system_seed 且无 user_id/workflow_id）。")
        client.close()
        return 1

    print(f"\n将更新 {len(system_seed_docs)} 条系统种子模板：\n")
    for doc in system_seed_docs:
        template_name = doc.get("template_name", "")
        content = doc.get("content") or {}
        current_output_format = content.get("output_format", "")
        current_constraints = content.get("constraints", "")
        version = doc.get("version", 1)
        print(f"  [{template_name}] version={version}")
        print(f"    旧 output_format: {current_output_format[:100]}")
        print(f"    旧 constraints:   {current_constraints[:100] if current_constraints else '(空)'}")
        merged_constraints = _merge_constraints(current_constraints)
        print(f"    新 output_format: {NEW_OUTPUT_FORMAT[:100]}")
        print(f"    新 constraints:   {merged_constraints[:100]}")
        if len(merged_constraints) > len(current_constraints.rstrip()):
            print(f"    （constraints 采用追加策略，保留原有风格内容）")
        print()

    if not args.apply:
        print("当前为预览模式，未写入数据库。使用 --apply 执行更新。")
        client.close()
        return 0

    updated = 0
    for doc in system_seed_docs:
        content = doc.get("content") or {}
        content["output_format"] = NEW_OUTPUT_FORMAT
        content["constraints"] = _merge_constraints(content.get("constraints", ""))

        current_version = int(doc.get("version") or 1)
        remark = (doc.get("remark") or "").strip()
        if REMARK_SUFFIX not in remark:
            remark = f"{remark}\n{REMARK_SUFFIX}".strip()

        collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "content": content,
                    "version": current_version + 1,
                    "updated_at": datetime.now(timezone.utc),
                    "remark": remark,
                }
            },
        )
        print(f"  [OK] {doc.get('template_name', '')} version {current_version} -> {current_version + 1}")
        updated += 1

    print(f"\n✅ 已写入数据库：{updated} 条系统种子模板")
    print("💡 提示：重启后端后生效（.\\start_dev.ps1 backend 3.0）")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
