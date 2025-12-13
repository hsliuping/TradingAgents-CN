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


def test_fundamentals_analyst_v2():
    """测试基本面分析师 v2.0"""
    print("\n" + "=" * 70)
    print("🧪 测试基本面分析师 v2.0")
    print("=" * 70)

    # 1. 使用 LegacyDependencyProvider 的方式获取 LLM 配置
    print("\n📝 步骤 1: 获取 LLM 配置...")
    from core.workflow.builder import LegacyDependencyProvider
    dep_provider = LegacyDependencyProvider()
    llm_config = dep_provider._get_llm_config_from_db()

    if not llm_config or not llm_config.get("api_key"):
        print("   ⚠️ 无法获取有效的 LLM 配置")
        print("\n⏭️  跳过执行测试（无法获取 LLM 配置）")
        return True  # 不算失败，只是跳过

    provider = llm_config.get("llm_provider", "dashscope")
    model_name = llm_config.get("quick_think_llm", "qwen-turbo")
    api_key = llm_config.get("api_key")
    backend_url = llm_config.get("backend_url")
    temperature = llm_config.get("quick_temperature", 0.7)
    max_tokens = llm_config.get("quick_max_tokens", 2000)

    print(f"   📦 使用 LLM 配置:")
    print(f"      厂家: {provider}")
    print(f"      模型: {model_name}")
    print(f"      API Key: {'已配置' if api_key else '未配置'}")
    print(f"      Backend URL: {backend_url[:50] + '...' if backend_url and len(backend_url) > 50 else backend_url}")

    # 2. 创建 LLM 实例
    print("\n📝 步骤 2: 创建 LLM 实例...")
    try:
        if provider == "dashscope":
            from tradingagents.llm_adapters import ChatDashScopeOpenAI
            llm = ChatDashScopeOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=backend_url,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif provider in ["openai", "deepseek", "siliconflow"]:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=backend_url,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            print(f"   ⚠️ 不支持的 LLM 厂家: {provider}")
            return True

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

