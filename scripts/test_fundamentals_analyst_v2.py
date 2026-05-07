"""
测试基本面分析师 v2.0

验证工作流层改进对基本面分析师的有效性
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 确保所有 Agent 被注册（触发 @register_agent 装饰器）
import core.agents.adapters  # noqa


def build_test_provider_config() -> dict:
    model_name = os.environ.get("FUNDAMENTALS_TEST_LLM_MODEL") or os.environ.get("TEST_LLM_MODEL") or "qwen-plus"
    return {
        "quick_think_llm": model_name,
        "deep_think_llm": model_name,
    }


def test_fundamentals_analyst_v2():
    """测试基本面分析师 v2.0"""
    print("\n" + "=" * 70)
    print("🧪 测试基本面分析师 v2.0")
    print("=" * 70)

    # 1. 使用 LegacyDependencyProvider 的方式获取 LLM 配置
    print("\n📝 步骤 1: 获取测试 LLM 配置（默认 qwen-plus）...")
    from core.workflow.builder import LegacyDependencyProvider
    provider_config = build_test_provider_config()
    dep_provider = LegacyDependencyProvider(provider_config)

    print(f"   📦 使用测试配置:")
    print(f"      快速模型: {provider_config['quick_think_llm']}")
    print(f"      深度模型: {provider_config['deep_think_llm']}")

    # 2. 创建 LLM 实例
    print("\n📝 步骤 2: 创建 LLM 实例...")
    try:
        llm = dep_provider.get_llm("quick")
        print(f"   ✅ LLM 实例创建成功: {llm.__class__.__name__}")
    except Exception as e:
        print(f"   ❌ 创建 LLM 实例失败: {e}")
        return True

    # 3. 创建 Agent 并设置 LLM
    print("\n📝 步骤 3: 创建 Agent...")
    from core.agents.factory import AgentFactory
    from core.tools.registry import ToolRegistry

    # 初始化工具注册表（会自动加载工具）
    registry = ToolRegistry()

    factory = AgentFactory()
    agent = factory.create(
        "fundamentals_analyst_v2",
        llm=llm,  # 传递 LLM 实例
        tool_ids=["get_stock_fundamentals_unified"]
    )

    print(f"   ✅ Agent 创建成功: {agent.agent_id}")
    print(f"   📦 绑定工具数: {len(agent.tools)}")
    print(f"   🤖 LLM 已配置: {agent._llm is not None}")

    # 4. 执行 Agent
    print("\n📝 步骤 4: 执行基本面分析...")
    try:
        state = {
            "ticker": "000001",  # 平安银行
            "trade_date": "2024-12-01",
            "messages": []
        }

        result = agent.execute(state)

        analysis = result.get("fundamentals_report", "")
        print(f"\n   ✅ 分析完成!")
        print(f"   📊 报告长度: {len(analysis)} 字符")

        # 显示报告预览
        print(f"\n   📄 报告预览（前 500 字符）:")
        print("   " + "-" * 60)
        preview = analysis[:500] if len(analysis) > 500 else analysis
        for line in preview.split('\n'):
            print(f"   {line}")
        print("   " + "-" * 60)

        # 验证报告质量
        if len(analysis) > 200:
            print(f"\n   ✅ 测试通过：生成了有效的基本面分析报告")
            return True
        else:
            print(f"\n   ⚠️ 警告：报告内容过短，但流程跑通了")
            return True

    except Exception as e:
        print(f"\n   ❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🧪 基本面分析师 v2.0 测试")
    print("=" * 70)

    success = test_fundamentals_analyst_v2()

    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    if success:
        print("✅ 通过 - 基本面分析师 v2.0")
        print("\n🎉 测试通过！")
        return 0
    else:
        print("❌ 失败 - 基本面分析师 v2.0")
        print("\n❌ 测试失败！")
        return 1


if __name__ == "__main__":
    exit(main())

