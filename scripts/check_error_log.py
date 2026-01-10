"""检查最近的错误日志"""
import re

log = open('logs/tradingagents.log', encoding='utf-8').read()

# 查找包含 final_trade_decision 的错误
matches = re.findall(r".*'final_trade_decision'.*", log)
print(f"找到 {len(matches)} 条 final_trade_decision 相关日志")
for m in matches[-5:]:
    print(m[:300])
    print("-" * 80)

# 查找 KeyError 或 Traceback
print("\n\n========== 最近的错误 ==========")
error_matches = re.findall(r".*(?:KeyError|Traceback|ERROR).*", log)
print(f"找到 {len(error_matches)} 条错误相关日志")
for m in error_matches[-20:]:
    print(m[:300])
    print("-" * 80)

