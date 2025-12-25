# -*- coding: utf-8 -*-
"""调试复盘分析中的交易计划传递"""
from pymongo import MongoClient
from urllib.parse import quote_plus
from bson import ObjectId
import json

username = quote_plus("admin")
password = quote_plus("tradingagents123")
client = MongoClient(f"mongodb://{username}:{password}@localhost:27017/")
db = client["tradingagents"]

# 1. 查询最新的复盘报告
print("=" * 80)
print("查询最新的复盘报告")
print("=" * 80)

# 先查看有哪些复盘报告
all_reviews = list(db["trade_reviews"].find({}, {"review_id": 1, "code": 1, "created_at": 1}).sort("created_at", -1).limit(5))
print(f"\n最近的 {len(all_reviews)} 条复盘报告:")
for r in all_reviews:
    print(f"  - {r.get('code', 'N/A')}: {r.get('review_id')} ({r.get('created_at')})")

latest_review = db["trade_reviews"].find_one(
    {},
    sort=[("created_at", -1)]
)

if not latest_review:
    print("❌ 未找到复盘报告")
    exit(1)

print(f"\n复盘ID: {latest_review.get('review_id')}")
print(f"股票代码: {latest_review.get('code')}")
print(f"股票名称: {latest_review.get('name')}")
print(f"创建时间: {latest_review.get('created_at')}")
print(f"关联交易计划ID: {latest_review.get('trading_system_id', '无')}")
print(f"关联交易计划名称: {latest_review.get('trading_system_name', '无')}")

# 2. 检查 AI 分析结果
print("\n" + "=" * 80)
print("AI 分析结果")
print("=" * 80)

ai_review = latest_review.get("ai_review", {})
if not ai_review:
    print("❌ 未找到 AI 分析结果")
else:
    print(f"\n综合评分: {ai_review.get('overall_score', 'N/A')}")
    print(f"时机评分: {ai_review.get('timing_score', 'N/A')}")
    print(f"仓位评分: {ai_review.get('position_score', 'N/A')}")
    print(f"纪律评分: {ai_review.get('discipline_score', 'N/A')}")
    
    # 检查是否有交易计划相关字段
    print(f"\n计划执行情况: {ai_review.get('plan_adherence', '❌ 缺失')}")
    print(f"计划偏离说明: {ai_review.get('plan_deviation', '❌ 缺失')}")
    
    # 检查总结内容是否提到交易计划
    summary = ai_review.get('summary', '')
    if '交易计划' in summary or '计划' in summary:
        print(f"\n✅ 总结中提到了交易计划")
    else:
        print(f"\n❌ 总结中未提到交易计划")

# 3. 如果关联了交易计划，查询交易计划详情
trading_system_id = latest_review.get('trading_system_id')
if trading_system_id:
    print("\n" + "=" * 80)
    print("关联的交易计划详情")
    print("=" * 80)
    
    try:
        trading_system = db["trading_systems"].find_one({"_id": ObjectId(trading_system_id)})
        if trading_system:
            print(f"\n计划名称: {trading_system.get('name')}")
            print(f"计划风格: {trading_system.get('style')}")
            print(f"系统ID: {trading_system.get('system_id')}")
            
            # 显示规则概要
            stock_rules = trading_system.get('stock_selection_rules', {})
            timing_rules = trading_system.get('timing_rules', {})
            position_rules = trading_system.get('position_rules', {})
            
            print(f"\n选股规则:")
            print(f"  - 必须满足: {len(stock_rules.get('must_meet', []))} 条")
            print(f"  - 排除条件: {len(stock_rules.get('exclude', []))} 条")
            
            print(f"\n择时规则:")
            print(f"  - 入场信号: {len(timing_rules.get('entry_signals', []))} 条")
            print(f"  - 出场信号: {len(timing_rules.get('exit_signals', []))} 条")
            
            print(f"\n仓位规则:")
            print(f"  - 单只股票上限: {position_rules.get('single_stock_limit', 'N/A')}")
            print(f"  - 最大持股数: {position_rules.get('max_stocks', 'N/A')}")
        else:
            print(f"❌ 未找到交易计划: {trading_system_id}")
    except Exception as e:
        print(f"❌ 查询交易计划失败: {e}")

# 4. 检查评分数据类型
print("\n" + "=" * 80)
print("评分数据类型检查")
print("=" * 80)

for score_field in ['overall_score', 'timing_score', 'position_score', 'discipline_score']:
    score_value = ai_review.get(score_field)
    print(f"{score_field}: {score_value} (类型: {type(score_value).__name__})")

client.close()

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)

