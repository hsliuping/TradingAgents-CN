"""
检查管理者和交易员 agents
"""
import sys
sys.path.insert(0, '.')

from core.agents import get_registry

registry = get_registry()

print("=" * 80)
print("检查 manager 和 trader 类别的 agents")
print("=" * 80)

managers_traders = [
    m for m in registry.list_all()
    if getattr(m.category, 'value', str(m.category)) in ['manager', 'trader']
]

print(f"\n找到 {len(managers_traders)} 个 manager/trader agents:\n")
for m in managers_traders:
    category = getattr(m.category, 'value', str(m.category))
    print(f"  - ID: {m.id}")
    print(f"    名称: {m.name}")
    print(f"    类别: {category}")
    print(f"    版本: {m.version}")
    print()

print("=" * 80)

