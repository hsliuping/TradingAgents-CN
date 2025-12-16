"""检查v2.0 agents的输出字段"""
import sys
sys.path.insert(0, '.')

from core.agents import get_registry

registry = get_registry()

v2_analysts = [
    'market_analyst_v2',
    'social_analyst_v2', 
    'news_analyst_v2',
    'fundamentals_analyst_v2',
    'sector_analyst_v2',
    'index_analyst_v2'
]

print("=" * 60)
print("v2.0 分析师输出字段检查")
print("=" * 60)

for aid in v2_analysts:
    if registry.is_registered(aid):
        metadata = registry.get_metadata(aid)
        print(f"{aid:30s} -> {metadata.output_field}")
    else:
        print(f"{aid:30s} -> NOT REGISTERED")

print("=" * 60)

