"""检查所有v2.0 agents的输出字段"""
import sys
sys.path.insert(0, '.')

from core.agents import get_registry

registry = get_registry()

# 所有v2.0 agent IDs
v2_agents = [
    # 分析师
    'market_analyst_v2',
    'social_analyst_v2', 
    'news_analyst_v2',
    'fundamentals_analyst_v2',
    'sector_analyst_v2',
    'index_analyst_v2',
    
    # 研究员
    'bull_researcher_v2',
    'bear_researcher_v2',
    
    # 管理者
    'research_manager_v2',
    'risk_manager_v2',
    
    # 交易员
    'trader_v2',
    
    # 风险分析师
    'risky_analyst_v2',
    'safe_analyst_v2',
    'neutral_analyst_v2',
    
    # 复盘分析
    'timing_analyst_v2',
    'position_analyst_v2',
    'emotion_analyst_v2',
    'attribution_analyst_v2',
    'review_manager_v2',
    
    # 持仓分析
    'pa_technical_v2',
    'pa_fundamental_v2',
    'pa_risk_v2',
    'pa_advisor_v2'
]

print("=" * 80)
print("所有v2.0 Agent输出字段检查")
print("=" * 80)

for aid in v2_agents:
    if registry.is_registered(aid):
        metadata = registry.get_metadata(aid)
        output_field = getattr(metadata, 'output_field', 'N/A')
        print(f"{aid:25s} -> {output_field}")
    else:
        print(f"{aid:25s} -> NOT REGISTERED")

print("=" * 80)

# 特别检查用户提到的四个关键agent
print("\n用户提到的四个关键agent检查:")
print("-" * 50)
key_agents = ['research_manager_v2', 'trader_v2', 'risk_manager_v2']
for aid in key_agents:
    if registry.is_registered(aid):
        metadata = registry.get_metadata(aid)
        output_field = getattr(metadata, 'output_field', 'N/A')
        print(f"{aid:25s} -> {output_field}")
    else:
        print(f"{aid:25s} -> NOT REGISTERED")

print("=" * 80)