#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证所有 v2.0 Agent 代码中使用的 agent_type/agent_name 与数据库模板是否匹配
"""

import os
from pymongo import MongoClient

# 带认证的连接
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
collection = db["prompt_templates"]

print("=" * 100)
print("验证所有 v2.0 Agent 代码与数据库模板的匹配情况")
print("=" * 100)

# 定义所有 v2.0 Agent 代码中使用的参数
# 格式: (文件名, agent_type, agent_name, preference_ids)
agent_configs = [
    # 研究员
    ("bull_researcher_v2.py", "researchers", "bull_researcher", ["neutral", "aggressive", "conservative"]),
    ("bear_researcher_v2.py", "researchers", "bear_researcher", ["neutral", "aggressive", "conservative"]),
    
    # 管理员
    ("research_manager_v2.py", "managers", "research_manager", ["neutral", "aggressive", "conservative"]),
    ("risk_manager_v2.py", "managers", "risk_manager", ["neutral", "aggressive", "conservative"]),
    
    # 交易员
    ("trader_v2.py", "trader", "trader", ["neutral", "aggressive", "conservative"]),
    
    # 风险分析师 (debators)
    ("risky_analyst_v2.py", "debators", "risky_analyst", ["aggressive"]),
    ("safe_analyst_v2.py", "debators", "safe_analyst", ["conservative"]),
    ("neutral_analyst_v2.py", "debators", "neutral_analyst", ["neutral"]),
    
    # 复盘分析师
    ("timing_analyst_v2.py", "reviewers", "timing_analyst", ["neutral", "aggressive", "conservative"]),
    ("position_analyst_v2.py", "reviewers", "position_analyst", ["neutral", "aggressive", "conservative"]),
    ("emotion_analyst_v2.py", "reviewers", "emotion_analyst", ["neutral", "aggressive", "conservative"]),
    ("attribution_analyst_v2.py", "reviewers", "attribution_analyst", ["neutral", "aggressive", "conservative"]),
    ("review_manager_v2.py", "reviewers", "review_manager", ["neutral", "aggressive", "conservative"]),
    
    # 持仓分析
    ("technical_analyst_v2.py", "position_analysis_v2", "pa_technical_v2", 
     ["neutral", "aggressive", "conservative", 
      "with_cache_aggressive", "with_cache_neutral", "with_cache_conservative",
      "without_cache_aggressive", "without_cache_neutral", "without_cache_conservative"]),
    ("fundamental_analyst_v2.py", "position_analysis_v2", "pa_fundamental_v2",
     ["neutral", "aggressive", "conservative",
      "with_cache_aggressive", "with_cache_neutral", "with_cache_conservative",
      "without_cache_aggressive", "without_cache_neutral", "without_cache_conservative"]),
    ("risk_assessor_v2.py", "position_analysis_v2", "pa_risk_v2", ["neutral", "aggressive", "conservative"]),
    ("action_advisor_v2.py", "position_analysis_v2", "pa_advisor_v2", ["neutral", "aggressive", "conservative"]),
]

total_checks = 0
passed_checks = 0
failed_checks = []
mismatches = []

for file, agent_type, agent_name, preference_ids in agent_configs:
    print(f"\n📄 {file}")
    print(f"   代码中使用: agent_type='{agent_type}', agent_name='{agent_name}'")
    
    # 检查数据库中是否有对应的模板（可能有 _v2 后缀）
    possible_types = [agent_type, f"{agent_type}_v2"]
    possible_names = [agent_name, f"{agent_name}_v2"]
    
    found_type = None
    found_name = None
    
    for pref_id in preference_ids:
        total_checks += 1
        template_found = False
        
        # 尝试所有可能的组合
        for pt in possible_types:
            for pn in possible_names:
                template = collection.find_one({
                    "agent_type": pt,
                    "agent_name": pn,
                    "preference_type": pref_id,
                    "is_system": True
                })
                
                if template:
                    if found_type is None:
                        found_type = pt
                        found_name = pn
                    
                    if pt != agent_type or pn != agent_name:
                        # 找到了模板，但是类型/名称不匹配
                        if (file, agent_type, agent_name, pt, pn) not in [(m[0], m[1], m[2], m[3], m[4]) for m in mismatches]:
                            mismatches.append((file, agent_type, agent_name, pt, pn))
                    
                    print(f"   ✅ {pref_id:30s} - 找到 ({pt}/{pn})")
                    passed_checks += 1
                    template_found = True
                    break
            if template_found:
                break
        
        if not template_found:
            print(f"   ❌ {pref_id:30s} - 缺失")
            failed_checks.append({
                "file": file,
                "agent_type": agent_type,
                "agent_name": agent_name,
                "preference_id": pref_id
            })

print("\n" + "=" * 100)
print(f"📊 检查结果: {passed_checks}/{total_checks} 通过")

if mismatches:
    print(f"\n⚠️ 发现 {len(mismatches)} 个类型/名称不匹配:")
    for file, code_type, code_name, db_type, db_name in mismatches:
        print(f"   - {file}:")
        print(f"     代码中: agent_type='{code_type}', agent_name='{code_name}'")
        print(f"     数据库: agent_type='{db_type}', agent_name='{db_name}'")
        print(f"     ⚠️ 需要修改代码或数据库以保持一致！")

if failed_checks:
    print(f"\n❌ 发现 {len(failed_checks)} 个缺失的模板:")
    for fail in failed_checks:
        print(f"   - {fail['file']}: {fail['agent_name']}/{fail['preference_id']}")

if not mismatches and not failed_checks:
    print("\n✅ 所有检查通过！Agent 代码与数据库模板完全匹配")

print("\n" + "=" * 100)

