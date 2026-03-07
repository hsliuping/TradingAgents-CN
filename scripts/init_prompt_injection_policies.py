#!/usr/bin/env python3
"""
初始化 Prompt 注入策略

为所有 v2.0 Agent（从 prompt_templates 中提取）生成默认策略：
- 统一 summary 模式
- 继承行业画像（个股场景）
- 包含能力块、外部缺口提醒、可比公司

使用方法:
    python scripts/init_prompt_injection_policies.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import db_manager
from app.services.prompt_injection_policy_service import PromptInjectionPolicyService

# 设置全局 mongo_db，供 get_mongo_db() 使用
import app.core.database as db_module


async def main():
    print("=" * 60)
    print("初始化 Prompt 注入策略")
    print("=" * 60)
    print()

    try:
        # 初始化数据库连接
        print("🔌 正在连接数据库...")
        await db_manager.init_mongodb()
        db_module.mongo_db = db_manager.mongo_db
        print("✅ 数据库连接成功")
        print()

        from app.core.database import get_mongo_db
        db = get_mongo_db()

        # 从 prompt_templates 聚合获取所有 (agent_type, agent_name)
        pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {
                "_id": {"agent_type": "$agent_type", "agent_name": "$agent_name"},
                "agent_type": {"$first": "$agent_type"},
                "agent_name": {"$first": "$agent_name"},
            }},
            {"$sort": {"agent_type": 1, "agent_name": 1}},
        ]
        cursor = db["prompt_templates"].aggregate(pipeline)
        agents = []
        async for doc in cursor:
            if doc.get("agent_type") and doc.get("agent_name"):
                agents.append((doc["agent_type"], doc["agent_name"]))

        if not agents:
            print("⚠️ 未找到任何 Agent 模板，请先初始化 prompt_templates")
            sys.exit(0)

        print(f"📋 找到 {len(agents)} 个 Agent，将为每个创建 general / industry / stock 三种场景策略")
        print()

        svc = PromptInjectionPolicyService()
        created = 0

        for agent_type, agent_name in agents:
            for scope in ("general", "industry", "stock"):
                data = {
                    "agent_type": agent_type,
                    "agent_name": agent_name,
                    "scope": scope,
                    "enabled": True,
                    "injection_mode": "summary",
                    "inherit_industry_for_stock": True,
                    "include_capability_block": True,
                    "include_external_gap_notice": True,
                    "include_comparable_companies": True,
                    "inject_position": "analysis_requirements",
                }
                try:
                    result = await svc.upsert_policy(data)
                    # upsert 返回的 result 包含更新后的数据，无法简单区分 create/update
                    # 这里统一计为 created，实际 upsert 会覆盖已存在的
                    created += 1
                    print(f"  ✓ {agent_type}/{agent_name} scope={scope}")
                except Exception as e:
                    print(f"  ✗ {agent_type}/{agent_name} scope={scope}: {e}")

        print()
        print(f"✅ 完成！共处理 {created} 条策略")
        print()
        print("可在 设置 → 注入策略管理 中查看和编辑")
        print("=" * 60)

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            await db_manager.close()
            print("🔌 数据库连接已关闭")
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
