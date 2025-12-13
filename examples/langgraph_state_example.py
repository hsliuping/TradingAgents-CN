"""
LangGraph 状态传递示例

演示如何使用自动生成的状态类创建 LangGraph 工作流
"""

import sys
import os
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.state.builder import StateSchemaBuilder
from core.state.models import StateFieldDefinition, FieldType
from langgraph.graph import StateGraph, END


def create_simple_workflow():
    """创建简单的分析工作流"""
    print("\n" + "=" * 70)
    print("创建简单的 LangGraph 工作流")
    print("=" * 70)
    
    # 1. 使用 StateSchemaBuilder 生成状态类
    builder = StateSchemaBuilder()
    
    input_fields = [
        StateFieldDefinition(
            name="ticker",
            type=FieldType.STRING,
            description="股票代码",
            required=True
        ),
        StateFieldDefinition(
            name="technical_analysis",
            type=FieldType.STRING,
            description="技术分析结果",
            required=False
        ),
        StateFieldDefinition(
            name="fundamental_analysis",
            type=FieldType.STRING,
            description="基本面分析结果",
            required=False
        ),
        StateFieldDefinition(
            name="final_recommendation",
            type=FieldType.STRING,
            description="最终建议",
            required=False
        )
    ]
    
    schema = builder.build_from_agents(
        workflow_id="simple_analysis",
        agent_ids=[],  # 不使用预定义 Agent
        input_fields=input_fields
    )
    
    # 生成 TypedDict 类
    State = builder.generate_typed_dict(schema)
    
    print(f"\n✅ 状态类生成成功: {State.__name__}")
    print(f"   字段: {list(State.__annotations__.keys())}")
    
    # 2. 定义节点函数
    def technical_analyst(state: dict) -> dict:
        """技术分析师节点"""
        ticker = state.get("ticker", "UNKNOWN")
        print(f"\n📊 技术分析师正在分析 {ticker}...")
        
        analysis = f"{ticker} 技术分析：价格突破阻力位，MACD金叉，建议关注"
        
        return {
            "technical_analysis": analysis,
            "messages": state.get("messages", []) + [
                AIMessage(content=f"技术分析完成: {analysis}")
            ]
        }
    
    def fundamental_analyst(state: dict) -> dict:
        """基本面分析师节点"""
        ticker = state.get("ticker", "UNKNOWN")
        print(f"\n📈 基本面分析师正在分析 {ticker}...")
        
        analysis = f"{ticker} 基本面分析：ROE稳定，估值合理，财务健康"
        
        return {
            "fundamental_analysis": analysis,
            "messages": state.get("messages", []) + [
                AIMessage(content=f"基本面分析完成: {analysis}")
            ]
        }
    
    def advisor(state: dict) -> dict:
        """综合建议师节点"""
        ticker = state.get("ticker", "UNKNOWN")
        tech = state.get("technical_analysis", "无")
        fund = state.get("fundamental_analysis", "无")
        
        print(f"\n💡 综合建议师正在生成建议...")
        print(f"   技术分析: {tech}")
        print(f"   基本面分析: {fund}")
        
        recommendation = f"{ticker} 综合建议：技术面和基本面均看好，建议适度买入"
        
        return {
            "final_recommendation": recommendation,
            "messages": state.get("messages", []) + [
                AIMessage(content=f"最终建议: {recommendation}")
            ]
        }
    
    # 3. 构建工作流图
    workflow = StateGraph(State)
    
    # 添加节点
    workflow.add_node("technical_analyst", technical_analyst)
    workflow.add_node("fundamental_analyst", fundamental_analyst)
    workflow.add_node("advisor", advisor)
    
    # 添加边
    workflow.set_entry_point("technical_analyst")
    workflow.add_edge("technical_analyst", "fundamental_analyst")
    workflow.add_edge("fundamental_analyst", "advisor")
    workflow.add_edge("advisor", END)
    
    # 编译
    app = workflow.compile()
    
    print(f"\n✅ 工作流编译成功")
    print(f"   节点: technical_analyst -> fundamental_analyst -> advisor")
    
    return app, State


def run_workflow_example():
    """运行工作流示例"""
    print("\n" + "=" * 70)
    print("运行工作流")
    print("=" * 70)
    
    # 创建工作流
    app, State = create_simple_workflow()
    
    # 准备初始状态
    initial_state = {
        "ticker": "AAPL",
        "messages": [HumanMessage(content="请分析 AAPL 股票")]
    }
    
    print(f"\n📝 初始状态:")
    print(f"   ticker: {initial_state['ticker']}")
    print(f"   messages: {len(initial_state['messages'])} 条")
    
    # 执行工作流
    print(f"\n🚀 开始执行工作流...")
    result = app.invoke(initial_state)
    
    # 打印结果
    print(f"\n" + "=" * 70)
    print("执行结果")
    print("=" * 70)
    print(f"\n✅ 工作流执行完成")
    print(f"\n最终状态:")
    print(f"  ticker: {result.get('ticker')}")
    print(f"  technical_analysis: {result.get('technical_analysis')}")
    print(f"  fundamental_analysis: {result.get('fundamental_analysis')}")
    print(f"  final_recommendation: {result.get('final_recommendation')}")
    print(f"  messages: {len(result.get('messages', []))} 条")
    
    print(f"\n消息历史:")
    for i, msg in enumerate(result.get('messages', []), 1):
        print(f"  {i}. [{msg.__class__.__name__}] {msg.content}")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🎯 LangGraph 状态传递示例")
    print("=" * 70)
    
    run_workflow_example()
    
    print("\n" + "=" * 70)
    print("✅ 示例运行完成")
    print("=" * 70)
    print("\n💡 关键要点:")
    print("  1. 使用 StateSchemaBuilder 自动生成 TypedDict 状态类")
    print("  2. 状态在节点之间自动传递和合并")
    print("  3. 每个节点只需返回需要更新的字段")
    print("  4. messages 字段自动累积（使用 add_messages reducer）")


if __name__ == "__main__":
    main()

