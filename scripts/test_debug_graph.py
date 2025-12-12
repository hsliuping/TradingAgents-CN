"""
测试调试接口的图结构
模拟 templates_debug.py 中的单节点图执行
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents import create_sector_analyst
from tradingagents.agents.utils.agent_states import AgentState
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("test_debug_graph")

def test_debug_graph():
    """测试调试图的执行流程"""
    
    print("=" * 80)
    print("🔍 测试调试接口的图结构")
    print("=" * 80)
    
    # 创建配置
    cfg = DEFAULT_CONFIG.copy()
    cfg["llm_provider"] = "dashscope"
    cfg["backend_url"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    cfg["quick_think_llm"] = "qwen-plus-latest"
    cfg["deep_think_llm"] = "qwen-plus-latest"
    
    # 创建 TradingAgentsGraph 以初始化 LLM 和 Toolkit
    logger.info("📝 创建 TradingAgentsGraph...")
    graph_full = TradingAgentsGraph(selected_analysts=["sector_analyst"], config=cfg)
    
    # 创建 Agent 节点
    logger.info("📝 创建 sector_analyst 节点...")
    agent_node = create_sector_analyst(llm=graph_full.quick_thinking_llm, toolkit=graph_full.toolkit)
    
    # 获取工具节点
    logger.info("📝 获取 sector_analyst 工具节点...")
    tool_nodes = graph_full._create_tool_nodes()
    tool_node = tool_nodes.get("sector_analyst")
    
    # 创建单节点图
    logger.info("📝 创建单节点图...")
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # 添加边
    workflow.add_edge(START, "agent")
    workflow.add_edge("tools", "agent")
    
    # 跟踪调用次数
    call_count = [0]
    
    # 添加条件边
    def should_continue(state):
        call_count[0] += 1
        logger.info(f"🔍 [should_continue] 调用次数: {call_count[0]}")
        
        messages = state.get("messages", [])
        logger.info(f"🔍 [should_continue] messages 数量: {len(messages)}")
        
        if messages:
            last_message = messages[-1]
            logger.info(f"🔍 [should_continue] 最后消息类型: {type(last_message).__name__}")
            
            if hasattr(last_message, 'tool_calls'):
                logger.info(f"🔍 [should_continue] tool_calls: {last_message.tool_calls}")
                if last_message.tool_calls:
                    logger.info(f"🔍 [should_continue] 返回 'tools'")
                    return "tools"
            else:
                logger.info(f"🔍 [should_continue] 无 tool_calls 属性")
        
        logger.info(f"🔍 [should_continue] 返回 END")
        return END
    
    workflow.add_conditional_edges("agent", should_continue)
    
    # 编译图
    single_agent_graph = workflow.compile()
    
    # 创建初始状态
    initial_state = AgentState(
        messages=[],
        company_of_interest="000002.SZ",
        trade_date="2025-12-11",
        sender="debug",
        market_report="",
        sentiment_report="",
        news_report="",
        fundamentals_report="",
        index_report="",
        sector_report="",
        market_tool_call_count=0,
        news_tool_call_count=0,
        sentiment_tool_call_count=0,
        fundamentals_tool_call_count=0,
        index_tool_call_count=0,
        sector_tool_call_count=0,
        agent_context={}
    )
    
    # 执行图
    logger.info("📝 执行单节点图...")
    logger.info(f"📝 初始状态消息数: {len(initial_state.get('messages', []))}")
    
    try:
        state = single_agent_graph.invoke(
            initial_state,
            config={"recursion_limit": 10}  # 限制迭代次数
        )
        
        logger.info("✅ 图执行完成")
        logger.info(f"📝 最终状态消息数: {len(state.get('messages', []))}")
        logger.info(f"📝 sector_report 长度: {len(state.get('sector_report', ''))}")
        
        if state.get('messages'):
            for i, msg in enumerate(state['messages']):
                logger.info(f"📝 消息[{i}]: 类型={type(msg).__name__}, 内容长度={len(getattr(msg, 'content', ''))}")
                if hasattr(msg, 'tool_calls'):
                    logger.info(f"📝 消息[{i}]: tool_calls={msg.tool_calls}")
        
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_debug_graph()

