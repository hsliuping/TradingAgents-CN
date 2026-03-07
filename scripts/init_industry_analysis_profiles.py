"""
初始化行业分析配置（示例）

预置 1 个银行业示例，演示数据结构。
用户可通过前端「AI 生成」功能自助创建更多行业配置。

集合: industry_analysis_profiles

用法:
    python scripts/init_industry_analysis_profiles.py
    python scripts/init_industry_analysis_profiles.py --force  # 覆盖已有配置
"""

import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 仅保留 1 个示例，其余由用户通过 AI 生成功能自助创建
EXAMPLE_PROFILES = [
    {
        "industry": "银行",
        "display_name": "银行业",
        "analysis_dimensions": [
            {"name": "净息差(NIM)", "description": "银行核心盈利能力指标，反映资产端收益率与负债端成本之差", "importance": "critical", "data_source": "fundamentals"},
            {"name": "不良贷款率", "description": "银行资产质量核心指标，不良率上升意味着信用风险增大", "importance": "critical", "data_source": "fundamentals"},
            {"name": "拨备覆盖率", "description": "银行风险缓冲能力指标，越高越安全", "importance": "high", "data_source": "fundamentals"},
            {"name": "资本充足率", "description": "监管核心指标，决定银行扩张能力", "importance": "high", "data_source": "fundamentals"},
            {"name": "ROE", "description": "净资产收益率，衡量银行股东回报", "importance": "high", "data_source": "fundamentals"},
            {"name": "信贷投放增速", "description": "反映银行业务扩张速度和宏观经济信贷需求", "importance": "medium", "data_source": "news"},
        ],
        "analysis_focus": "银行业分析应重点关注利率环境变化对NIM的影响、信贷投放节奏、资产质量变化趋势，以及监管政策对资本金和业务结构的约束。",
        "key_metrics": ["NIM", "不良率", "拨备覆盖率", "ROE", "资本充足率", "信贷增速"],
        "comparable_companies": ["招商银行", "兴业银行", "平安银行", "宁波银行"],
    },
]


def main():
    parser = argparse.ArgumentParser(description="初始化行业分析配置（示例）")
    parser.add_argument("--force", action="store_true", help="覆盖已有的同名行业配置")
    args = parser.parse_args()

    from pymongo import MongoClient
    from app.core.config import settings

    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    collection = db["industry_analysis_profiles"]

    now = datetime.utcnow()
    created, skipped = 0, 0

    for profile in EXAMPLE_PROFILES:
        existing = collection.find_one({"industry": profile["industry"]})
        if existing and not args.force:
            print(f"⏭️  跳过已存在: {profile['industry']}（使用 --force 覆盖）")
            skipped += 1
            continue

        doc = {**profile, "is_active": True, "created_at": now, "updated_at": now}
        if existing and args.force:
            collection.replace_one({"_id": existing["_id"]}, doc)
            print(f"🔄 覆盖更新: {profile['industry']}")
        else:
            collection.insert_one(doc)
            print(f"✅ 创建: {profile['industry']}")
        created += 1

    client.close()

    print(f"\n📊 完成: 创建/更新 {created} 个, 跳过 {skipped} 个")
    print(f"💡 提示: 更多行业配置可通过前端「行业配置 → AI 生成」功能创建")


if __name__ == "__main__":
    main()

