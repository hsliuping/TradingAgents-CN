"""
测试板块分析功能

测试两种模式：
1. 仅数据获取（不调用 LLM）
2. 完整分析（通过 Agent 节点调用 LLM）
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_data_only():
    """测试仅数据获取（不调用 LLM）"""
    print("=" * 80)
    print("📊 测试1: 仅数据获取（不调用 LLM）")
    print("=" * 80)

    from core.tools.sector_tools import analyze_sector

    try:
        report = await analyze_sector("000002.SZ", "2025-12-11")
        print(report)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


def test_with_llm():
    """测试完整分析（通过 Agent 节点调用 LLM）"""
    print("\n" + "=" * 80)
    print("🤖 测试2: 完整分析（通过 Agent 节点调用 LLM）")
    print("=" * 80)

    try:
        # 导入必要的模块
        from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
        from tradingagents.llm_adapters.dashscope_openai_adapter import create_dashscope_openai_llm
        import os

        # 创建 LLM 实例（使用阿里百炼）
        print("🔄 创建 LLM 实例...")
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            print("❌ 未设置 DASHSCOPE_API_KEY 环境变量")
            return

        llm = create_dashscope_openai_llm(
            model="qwen-plus-latest",
            api_key=api_key,
            temperature=0.1,
            max_tokens=4000
        )
        print(f"✅ LLM 类型: {llm.__class__.__name__}")

        # 创建 sector_analyst 节点
        print("🔄 创建 sector_analyst 节点...")
        sector_analyst_node = create_sector_analyst(llm, None)

        # 准备初始状态
        state = {
            "company_of_interest": "000002.SZ",
            "trade_date": "2025-12-11",
            "messages": [],
            "agent_context": {
                "user_id": None,
                "preference_id": "neutral"
            }
        }

        # 调用 sector_analyst 节点
        print("🔄 调用 sector_analyst 节点...")
        result = sector_analyst_node(state)

        # 输出结果
        print("\n" + "=" * 80)
        print("📋 LLM 分析报告")
        print("=" * 80)
        print(result.get("sector_report", "无报告"))

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    # 测试1: 仅数据获取
    await test_data_only()

    # 测试2: 完整分析（包含 LLM）
    test_with_llm()

    print("\n" + "=" * 80)
    print("✅ 所有测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

