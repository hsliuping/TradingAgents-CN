from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.analysts.dynamic_analyst import DynamicAnalystFactory

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('default')


# Create a custom config
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "google"  # Use a different model
config["backend_url"] = "https://generativelanguage.googleapis.com/v1beta"  # Use a different backend
config["deep_think_llm"] = "gemini-2.0-flash"  # Use a different model
config["quick_think_llm"] = "gemini-2.0-flash"  # Use a different model
config["max_debate_rounds"] = 1  # Increase debate rounds
config["online_tools"] = True  # Increase debate rounds

# 阶段1智能体需从配置文件加载，避免硬编码
selected_analysts = [a.get("slug") for a in DynamicAnalystFactory.get_all_agents() if a.get("slug")]
if not selected_analysts:
    raise ValueError("未找到阶段1智能体配置，请先在 phase1_agents_config.yaml 中添加。")

# Initialize with custom config
ta = TradingAgentsGraph(selected_analysts=selected_analysts, debug=True, config=config)

# forward propagate
_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
