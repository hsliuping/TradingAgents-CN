"""
测试基本面分析师修复

验证 bind_tools([]) 是否能解决 qwen-flash 持续调用工具的问题
"""

import sys
import os
import asyncio

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agents.adapters.fundamentals_analyst_v2 import FundamentalsAnalystAgentV2
from tradingagents.llm_adapters.dashscope_openai_adapter import ChatDashScopeOpenAI


async def test_fundamentals_analyst():
    """测试基本面分析师"""
    print("\n" + "=" * 60)
    print("测试基本面分析师 v2.0 - 工具调用修复")
    print("=" * 60)

    # 创建 LLM（使用 DashScope qwen-flash）
    llm = ChatDashScopeOpenAI(
        model="qwen-flash",
        temperature=0.7,
        max_tokens=4000
    )
    
    # 创建基本面分析师
    agent = FundamentalsAnalystAgentV2(llm=llm)
    
    # 执行分析
    print("\n开始执行基本面分析...")
    result = agent.execute({
        "ticker": "000001",
        "analysis_date": "2026-01-11"
    })
    
    print("\n" + "=" * 60)
    print("📊 测试结果")
    print("=" * 60)
    
    report = result.get("fundamentals_report", "")
    print(f"报告长度: {len(report)} 字符")
    
    if len(report) > 100:
        print("✅ 报告生成成功！")
        print(f"\n报告前500字符:\n{report[:500]}...")
    else:
        print("❌ 报告生成失败！")
        print(f"报告内容: {report}")
        return False
    
    return True


if __name__ == "__main__":
    print("\n🧪 开始测试基本面分析师修复\n")
    
    success = asyncio.run(test_fundamentals_analyst())
    
    if success:
        print("\n🎉 测试通过！修复成功！")
    else:
        print("\n❌ 测试失败，请检查代码")
        sys.exit(1)

