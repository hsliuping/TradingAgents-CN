"""
TradingAgents-CN 演示入口

运行一次完整的单股多智能体分析示例（原版 TradingAgents 的演示脚本）。
安装后可通过 `tradingagents` 命令运行，或 `python main.py`。
"""

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG


def main():
    # Create a custom config
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "google"  # Use a different model
    config["backend_url"] = "https://generativelanguage.googleapis.com/v1beta"  # Use a different backend
    config["deep_think_llm"] = "gemini-2.0-flash"  # Use a different model
    config["quick_think_llm"] = "gemini-2.0-flash"  # Use a different model
    config["max_debate_rounds"] = 1  # Increase debate rounds
    config["online_tools"] = True  # Increase debate rounds

    # Initialize with custom config
    ta = TradingAgentsGraph(debug=True, config=config)

    # forward propagate
    _, decision = ta.propagate("NVDA", "2024-05-10")
    print(decision)

    # Memorize mistakes and reflect
    # ta.reflect_and_remember(1000) # parameter is the position returns


if __name__ == "__main__":
    main()
