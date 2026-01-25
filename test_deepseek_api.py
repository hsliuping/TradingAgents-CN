from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import os

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('default')

# Create a custom config
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "custom_openai"  # 使用自定义厂家
config["backend_url"] = "https://api.302.ai/v1"  # 302AI平台端点
config["deep_think_llm"] = "deepseek-v3.2-exp-thinking"  # DeepSeek模型
config["quick_think_llm"] = "deepseek-v3.2-exp-thinking"  # DeepSeek模型
config["max_debate_rounds"] = 1  # 辩论轮次
config["online_tools"] = True  # 启用在线工具

# 检查环境变量
print("检查环境变量:")
print(f"DEEPSEEK_API_KEY: {'已设置' if os.getenv('DEEPSEEK_API_KEY') else '未设置'}")
print(f"AI302_API_KEY: {'已设置' if os.getenv('AI302_API_KEY') else '未设置'}")
print(f"后端URL: {config['backend_url']}")
print(f"深度模型: {config['deep_think_llm']}")
print(f"快速模型: {config['quick_think_llm']}")

# Initialize with custom config
try:
    print("\n初始化TradingAgentsGraph...")
    ta = TradingAgentsGraph(debug=True, config=config)
    print("\n✅ TradingAgentsGraph初始化成功!")
    
    # 测试LLM实例类型
    print(f"\n深度思考LLM类型: {type(ta.deep_thinking_llm)}")
    print(f"快速思考LLM类型: {type(ta.quick_thinking_llm)}")
    
    # 测试简单的LLM调用
    print("\n测试LLM调用...")
    from langchain_core.messages import HumanMessage
    
    # 测试深度思考LLM
    try:
        response = ta.deep_thinking_llm.invoke([HumanMessage(content="你是谁？")])
        print("✅ 深度思考LLM调用成功!")
        print(f"响应: {response.content}")
    except Exception as e:
        print(f"❌ 深度思考LLM调用失败: {e}")
    
    # 测试快速思考LLM
    try:
        response = ta.quick_thinking_llm.invoke([HumanMessage(content="你是谁？")])
        print("✅ 快速思考LLM调用成功!")
        print(f"响应: {response.content}")
    except Exception as e:
        print(f"❌ 快速思考LLM调用失败: {e}")
    
    print("\n测试完成!")
    
except Exception as e:
    print(f"\n❌ 初始化失败: {e}")
    import traceback
    traceback.print_exc()
