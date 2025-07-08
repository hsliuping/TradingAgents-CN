from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Create a custom config
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"  # 使用通义千问
config["backend_url"] = "https://dashscope.aliyuncs.com/api/v1"  # 通义千问API地址
config["deep_think_llm"] = "qwen-max"  # 使用通义千问最强大的模型
config["quick_think_llm"] = "qwen-turbo"  # 使用通义千问快速模型
config["max_debate_rounds"] = 1  # 辩论轮数
config["online_tools"] = True  # 启用在线工具

# Initialize with custom config
ta = TradingAgentsGraph(debug=True, config=config)

# forward propagate
_, decision = ta.propagate("NVDA", "2025-07-08")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
