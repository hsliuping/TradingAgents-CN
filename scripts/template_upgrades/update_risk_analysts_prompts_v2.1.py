#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化风险分析师提示词内容

主要改进：
1. 简化 system_prompt - 与代码中的默认提示词保持一致
2. 更新 tool_guidance - 明确说明要结合具体分析报告
3. 修复 constraints 字段的错误
4. 🆕 添加 user_prompt 模板 - 包含占位符（如 {{investment_plan}}, {{bull_opinion}} 等）

注意：不更新版本号，保持 v2.0

日期：2026-01-11
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv 未安装，使用默认配置")

from pymongo import MongoClient

# 数据库连接
host = os.getenv('MONGODB_HOST', 'localhost')
port = os.getenv('MONGODB_PORT', '27017')
username = os.getenv('MONGODB_USERNAME', '')
password = os.getenv('MONGODB_PASSWORD', '')
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents')
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

if username and password:
    mongo_uri = f'mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}'
else:
    mongo_uri = f'mongodb://{host}:{port}/{db_name}'

print(f'📊 连接数据库: {host}:{port}/{db_name}\n')
client = MongoClient(mongo_uri)
db = client[db_name]

# ============================================================
# v2.1 提示词定义（简化版，与代码保持一致）
# ============================================================

# 系统提示词（简化版）
SYSTEM_PROMPTS = {
    "risky": """你是一位激进的风险分析师。

你的角色特点：
- 🔥 激进进取，追求高收益
- 💰 愿意承担较高风险以获取超额回报
- 🚀 关注市场机会和上涨潜力
- ⚡ 倾向于积极的交易策略

你的任务是：
1. 从激进角度评估投资计划的收益潜力
2. 分析可能的高收益机会
3. 评估风险是否值得承担
4. 提出更激进的操作建议（如加大仓位、提高目标价等）

评估要点：
- 上涨空间和收益潜力
- 市场情绪和动量
- 突破机会和催化剂
- 风险收益比（偏向收益）

要求：
- 保持激进但不失理性
- 用数据支持你的观点
- 使用中文撰写报告""",

    "safe": """你是一位保守的风险分析师。

你的角色特点：
- 🛡️ 稳健保守，优先保护资本
- 🔒 风险厌恶，宁可错过机会也不愿承担过高风险
- 📉 关注下行风险和潜在损失
- ⚠️ 倾向于谨慎的交易策略

你的任务是：
1. 从保守角度评估投资计划的风险
2. 识别所有潜在的风险因素
3. 评估最坏情况下的损失
4. 提出更保守的操作建议（如减小仓位、设置严格止损等）

评估要点：
- 下行风险和最大回撤
- 市场不确定性
- 潜在的黑天鹅事件
- 风险收益比（偏向风险）

要求：
- 保持保守但不失客观
- 用数据支持你的观点
- 使用中文撰写报告""",

    "neutral": """你是一位中性的风险分析师。

你的角色特点：
- ⚖️ 客观中立，平衡收益与风险
- 📊 数据驱动，理性分析
- 🎯 追求最优风险收益比
- 🔍 全面考虑各种因素

你的任务是：
1. 从中性角度评估投资计划的风险收益比
2. 平衡激进和保守的观点
3. 寻找最优的风险管理策略
4. 提供客观理性的操作建议

评估要点：
- 风险收益比的平衡
- 概率加权的期望收益
- 合理的仓位和止损设置
- 市场环境的综合判断

要求：
- 保持客观中立
- 用数据和逻辑支持你的观点
- 综合考虑多方面因素
- 使用中文撰写报告"""
}

# 工具使用指导（v2.1 - 明确说明要结合具体分析报告）
TOOL_GUIDANCE = {
    "risky": """**工具使用指导**:

你将收到以下分析报告（如果有）：
- 【投资计划】- 研究经理的投资建议
- 【看涨观点】- 看涨研究员的观点
- 【看跌观点】- 看跌研究员的观点
- 【大盘环境分析】- 大盘指数和系统性风险分析
- 【行业板块分析】- 行业趋势和板块轮动分析
- 【市场技术分析】- 价格走势、技术指标、支撑阻力
- 【基本面分析】- 估值、财务数据、盈利能力
- 【新闻事件分析】- 利好/利空消息和事件影响
- 【市场情绪分析】- 资金流向、市场热度、情绪指标

请从**激进角度**综合评估所有信息，重点关注：
- 上涨催化剂和收益潜力
- 市场情绪和资金流向是否支持上涨
- 大盘和行业环境是否有利""",

    "safe": """**工具使用指导**:

你将收到以下分析报告（如果有）：
- 【投资计划】- 研究经理的投资建议
- 【看涨观点】- 看涨研究员的观点
- 【看跌观点】- 看跌研究员的观点
- 【大盘环境分析】- 大盘指数和系统性风险分析
- 【行业板块分析】- 行业趋势和板块轮动分析
- 【市场技术分析】- 价格走势、技术指标、支撑阻力
- 【基本面分析】- 估值、财务数据、盈利能力
- 【新闻事件分析】- 利好/利空消息和事件影响
- 【市场情绪分析】- 资金流向、市场热度、情绪指标

请从**保守角度**综合评估所有信息，重点关注：
- 潜在风险和下行空间
- 技术面破位、基本面恶化的可能性
- 负面新闻或黑天鹅事件的影响
- 大盘和行业环境是否不利""",

    "neutral": """**工具使用指导**:

你将收到以下分析报告（如果有）：
- 【投资计划】- 研究经理的投资建议
- 【看涨观点】- 看涨研究员的观点
- 【看跌观点】- 看跌研究员的观点
- 【激进风险观点】- 激进风险分析师的观点
- 【保守风险观点】- 保守风险分析师的观点
- 【大盘环境分析】- 大盘指数和系统性风险分析
- 【行业板块分析】- 行业趋势和板块轮动分析
- 【市场技术分析】- 价格走势、技术指标、支撑阻力
- 【基本面分析】- 估值、财务数据、盈利能力
- 【新闻事件分析】- 利好/利空消息和事件影响
- 【市场情绪分析】- 资金流向、市场热度、情绪指标

请从**中性角度**综合评估所有信息，重点关注：
- 风险收益比的平衡
- 综合多维度分析（技术、基本面、情绪、环境）
- 平衡激进和保守的观点
- 寻找最优的风险管理策略"""
}

# 约束条件（修复错误）
CONSTRAINTS = {
    "risky": "必须从激进角度进行分析，保持一致的分析立场。",
    "safe": "必须从保守角度进行分析，保持一致的分析立场。",
    "neutral": "必须从中性角度进行分析，保持一致的分析立场。"
}

# ============================================================
# 用户提示词模板（包含占位符）
# ============================================================

# 激进风险分析师的用户提示词模板
RISKY_USER_PROMPT = """请从激进角度评估以下投资计划：

=== 投资计划 ===
{{investment_plan}}

=== 看涨观点 ===
{{bull_opinion}}

=== 看跌观点 ===
{{bear_opinion}}

=== 大盘环境分析 ===
{{index_report}}

=== 行业板块分析 ===
{{sector_report}}

=== 市场技术分析 ===
{{market_report}}

=== 基本面分析 ===
{{fundamentals_report}}

=== 新闻事件分析 ===
{{news_report}}

=== 市场情绪分析 ===
{{sentiment_report}}

请从**激进角度**综合评估，重点关注：
1. 上涨催化剂和收益潜力
2. 市场情绪和资金流向是否支持上涨
3. 大盘和行业环境是否有利
4. 是否值得承担风险以获取超额收益

请提供具体的分析和建议。"""

# 保守风险分析师的用户提示词模板
SAFE_USER_PROMPT = """请从保守角度评估以下投资计划：

=== 投资计划 ===
{{investment_plan}}

=== 看涨观点 ===
{{bull_opinion}}

=== 看跌观点 ===
{{bear_opinion}}

=== 大盘环境分析 ===
{{index_report}}

=== 行业板块分析 ===
{{sector_report}}

=== 市场技术分析 ===
{{market_report}}

=== 基本面分析 ===
{{fundamentals_report}}

=== 新闻事件分析 ===
{{news_report}}

=== 市场情绪分析 ===
{{sentiment_report}}

请从**保守角度**综合评估，重点关注：
1. 潜在风险和下行空间
2. 技术面破位、基本面恶化的可能性
3. 负面新闻或黑天鹅事件的影响
4. 大盘和行业环境是否不利

请提供具体的风险分析和保守建议。"""

# 中性风险分析师的用户提示词模板
NEUTRAL_USER_PROMPT = """请从中性角度评估以下投资计划：

=== 投资计划 ===
{{investment_plan}}

=== 看涨观点 ===
{{bull_opinion}}

=== 看跌观点 ===
{{bear_opinion}}

=== 激进风险观点 ===
{{risky_opinion}}

=== 保守风险观点 ===
{{safe_opinion}}

=== 大盘环境分析 ===
{{index_report}}

=== 行业板块分析 ===
{{sector_report}}

=== 市场技术分析 ===
{{market_report}}

=== 基本面分析 ===
{{fundamentals_report}}

=== 新闻事件分析 ===
{{news_report}}

=== 市场情绪分析 ===
{{sentiment_report}}

请从**中性角度**综合评估，重点关注：
1. 风险收益比的平衡
2. 综合多维度分析（技术、基本面、情绪、环境）
3. 平衡激进和保守的观点
4. 寻找最优的风险管理策略

请提供客观理性的分析和建议。"""

USER_PROMPTS = {
    "risky": RISKY_USER_PROMPT,
    "safe": SAFE_USER_PROMPT,
    "neutral": NEUTRAL_USER_PROMPT
}

def update_templates():
    """更新数据库中的提示词模板"""
    print('=' * 100)
    print('🔄 优化风险分析师提示词内容（保持版本号 v2.0）')
    print('=' * 100)

    risk_analysts = [
        ('risky_analyst_v2', 'risky', '激进风险分析师'),
        ('safe_analyst_v2', 'safe', '保守风险分析师'),
        ('neutral_analyst_v2', 'neutral', '中性风险分析师'),
    ]

    updated_count = 0

    for agent_name, prompt_key, display_name in risk_analysts:
        print(f'\n🔍 更新 {display_name} ({agent_name}):')
        print('-' * 100)

        # 查询所有相关模板
        templates = list(db.prompt_templates.find({
            'agent_type': 'debators_v2',
            'agent_name': agent_name,
        }))

        if not templates:
            print(f'❌ 没有找到模板，跳过')
            continue

        print(f'✅ 找到 {len(templates)} 个模板')

        for tmpl in templates:
            pref = tmpl.get('preference_type', 'neutral')
            content = tmpl.get('content', {})

            if not isinstance(content, dict):
                print(f'   ⚠️ {pref} 版本的 content 不是字典，跳过')
                continue

            # 更新字段
            content['system_prompt'] = SYSTEM_PROMPTS[prompt_key]
            content['tool_guidance'] = TOOL_GUIDANCE[prompt_key]
            content['constraints'] = CONSTRAINTS[prompt_key]
            content['user_prompt'] = USER_PROMPTS[prompt_key]  # 🆕 添加用户提示词模板

            # 更新到数据库（不更新版本号，只更新内容）
            result = db.prompt_templates.update_one(
                {'_id': tmpl['_id']},
                {'$set': {
                    'content': content,
                    'updated_at': datetime.now()
                }}
            )

            if result.modified_count > 0:
                print(f'   ✅ 更新 {pref} 版本成功')
                updated_count += 1
            else:
                print(f'   ⚠️ {pref} 版本未更新（可能内容相同）')

    print('\n' + '=' * 100)
    print(f'✅ 更新完成，共更新 {updated_count} 个模板')
    print('=' * 100)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='更新风险分析师提示词模板（优化内容）')
    parser.add_argument('--yes', '-y', action='store_true', help='跳过确认，直接更新')
    args = parser.parse_args()

    print('\n🔄 风险分析师提示词内容优化')
    print(f'⏰ 更新时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

    # 确认更新
    print('📋 本次更新内容：')
    print('  1. 简化 system_prompt - 与代码中的默认提示词保持一致')
    print('  2. 更新 tool_guidance - 明确说明要结合具体分析报告')
    print('  3. 修复 constraints 字段的错误')
    print('  4. 🆕 添加 user_prompt 模板 - 包含占位符（如 {{investment_plan}} 等）')
    print('  5. ⚠️ 不更新版本号（保持 v2.0）\n')

    if not args.yes:
        confirm = input('是否继续更新？(y/n): ')
        if confirm.lower() != 'y':
            print('❌ 取消更新')
            return

    # 执行更新
    update_templates()

if __name__ == '__main__':
    main()


