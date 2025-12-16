"""
Agent基类使用示例

展示如何使用基于5种基类实现的Agent
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_openai import ChatOpenAI
from core.agents.adapters import (
    MarketAnalystV2,
    BullResearcherV2,
    ResearchManagerV2,
    TraderV2
)


def example_market_analyst():
    """示例1: 使用市场分析师V2"""
    print("\n" + "="*60)
    print("示例1: 市场分析师V2")
    print("="*60)
    
    # 创建LLM
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # 创建Agent
    agent = MarketAnalystV2(llm=llm)
    
    # 执行分析
    state = {
        "ticker": "AAPL",
        "analysis_date": "2024-12-15"
    }
    
    print(f"\n输入: {state}")
    print(f"\nAgent类型: {agent.analyst_type}")
    print(f"输出字段: {agent.output_field}")
    
    # 注意：实际执行需要配置工具和LLM
    # result = agent.execute(state)
    # print(f"\n输出: {result.get('market_report', 'N/A')}")


def example_bull_researcher():
    """示例2: 使用看涨研究员V2"""
    print("\n" + "="*60)
    print("示例2: 看涨研究员V2")
    print("="*60)
    
    # 创建LLM
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # 创建Agent
    agent = BullResearcherV2(llm=llm)
    
    # 执行分析
    state = {
        "ticker": "AAPL",
        "analysis_date": "2024-12-15",
        "market_report": "价格上涨，技术指标看涨",
        "news_report": "公司发布利好消息",
        "fundamentals_report": "业绩增长强劲"
    }
    
    print(f"\n输入: ticker={state['ticker']}, 包含3个报告")
    print(f"\nAgent类型: {agent.researcher_type}")
    print(f"研究立场: {agent.stance}")
    print(f"需要的报告: {agent._get_required_reports()}")
    
    # 注意：实际执行需要配置LLM
    # result = agent.execute(state)
    # print(f"\n输出: {result.get('bull_report', 'N/A')}")


def example_research_manager():
    """示例3: 使用研究经理V2"""
    print("\n" + "="*60)
    print("示例3: 研究经理V2")
    print("="*60)
    
    # 创建LLM
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # 创建Agent
    agent = ResearchManagerV2(llm=llm)
    
    # 执行分析
    state = {
        "ticker": "AAPL",
        "analysis_date": "2024-12-15",
        "bull_report": "看涨理由：技术面强劲，基本面良好",
        "bear_report": "看跌理由：估值偏高，市场风险增加"
    }
    
    print(f"\n输入: ticker={state['ticker']}, 包含看涨和看跌报告")
    print(f"\nAgent类型: {agent.manager_type}")
    print(f"是否启用辩论: {agent.enable_debate}")
    print(f"需要的输入: {agent._get_required_inputs()}")
    
    # 注意：实际执行需要配置LLM
    # result = agent.execute(state)
    # print(f"\n输出: {result.get('investment_plan', 'N/A')}")


def example_trader():
    """示例4: 使用交易员V2"""
    print("\n" + "="*60)
    print("示例4: 交易员V2")
    print("="*60)
    
    # 创建LLM
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # 创建Agent
    agent = TraderV2(llm=llm)
    
    # 执行分析
    state = {
        "ticker": "AAPL",
        "analysis_date": "2024-12-15",
        "investment_plan": {
            "recommendation": "买入",
            "confidence": 0.8,
            "reason": "技术面和基本面均支持"
        },
        "market_report": "价格在支撑位附近",
        "risk_assessment": "风险可控"
    }
    
    print(f"\n输入: ticker={state['ticker']}, 投资建议=买入")
    print(f"\nAgent类型: Trader")
    print(f"输出字段: {agent.output_field}")
    
    # 注意：实际执行需要配置LLM
    # result = agent.execute(state)
    # print(f"\n输出: {result.get('trading_plan', 'N/A')}")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("Agent基类使用示例")
    print("="*60)
    
    # 运行示例
    example_market_analyst()
    example_bull_researcher()
    example_research_manager()
    example_trader()
    
    print("\n" + "="*60)
    print("示例完成")
    print("="*60)
    print("\n注意：以上示例仅展示Agent的配置和接口")
    print("实际执行需要：")
    print("1. 配置有效的OpenAI API Key")
    print("2. 配置工具（对于分析师Agent）")
    print("3. 提供完整的输入数据")


if __name__ == "__main__":
    main()

