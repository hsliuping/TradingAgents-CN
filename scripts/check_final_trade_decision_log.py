"""检查最近的 final_trade_decision 日志"""
import re

log = open('logs/tradingagents.log', encoding='utf-8').read()
matches = re.findall(r'.*final_trade_decision.*', log)
print(f"找到 {len(matches)} 条相关日志")
print("\n最近 15 条:")
for m in matches[-15:]:
    print(m[:200])
    print("-" * 80)

