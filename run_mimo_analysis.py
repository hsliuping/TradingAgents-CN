"""使用 MiMo 模型进行金融分析"""
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# 配置 MiMo 模型
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "custom_openai"
config["backend_url"] = "https://token-plan-cn.xiaomimimo.com/v1"
config["deep_think_llm"] = "mimo-v2.5-pro"
config["quick_think_llm"] = "mimo-v2.5-pro"
config["max_debate_rounds"] = 1
config["online_tools"] = True

print("=" * 60)
print("TradingAgents-CN MiMo 金融分析")
print("=" * 60)
print(f"模型: mimo-v2.5-pro")
print(f"API: https://token-plan-cn.xiaomimimo.com/v1")
print("=" * 60)

# 初始化交易代理图
ta = TradingAgentsGraph(debug=True, config=config)

# 分析股票 - 示例：分析贵州茅台 (600519.SH)
# 日期格式: YYYY-MM-DD
stock_code = "600519"  # 贵州茅台
analysis_date = "2025-01-15"

print(f"\n开始分析股票: {stock_code}")
print(f"分析日期: {analysis_date}")
print("-" * 60)

try:
    _, decision = ta.propagate(stock_code, analysis_date)
    print("\n" + "=" * 60)
    print("分析结果:")
    print("=" * 60)
    print(decision)
except Exception as e:
    print(f"\n分析出错: {e}")
    print("\n请确保:")
    print("1. 已配置 .env 文件中的 CUSTOM_OPENAI_API_KEY")
    print("2. MongoDB 和 Redis 服务已启动")
    print("3. 股票数据已同步")
