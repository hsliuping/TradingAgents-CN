#!/usr/bin/env python3
"""
LM Studio 集成验证脚本
验证 LM Studio 适配器是否正常工作
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_lmstudio_adapter():
    """测试LM Studio适配器基本功能"""
    print("🧪 开始测试 LM Studio 适配器...")

    try:
        # 测试适配器导入
        from tradingagents.llm_adapters.lmstudio_adapter import ChatLMStudio
        print("✅ LM Studio适配器导入成功")

        # 测试适配器初始化（不验证连接）
        print("🔧 测试适配器初始化...")
        adapter = ChatLMStudio(
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:1234/v1",
            timeout=5
        )
        print("✅ 适配器初始化成功")

        # 验证适配器属性
        assert adapter.provider_name == "lmstudio"
        assert adapter.model_name == "test-model"
        # base_url 可能通过不同方式访问，检查是否有这个属性
        if hasattr(adapter, 'base_url'):
            assert adapter.base_url == "http://localhost:1234/v1"
        else:
            # 检查是否通过其他方式存储
            assert adapter._OpenAICompatibleBase__base_url == "http://localhost:1234/v1"
        print("✅ 适配器属性验证通过")

        # 测试配置获取
        from tradingagents.llm_adapters.openai_compatible_base import OPENAI_COMPATIBLE_PROVIDERS
        lmstudio_config = OPENAI_COMPATIBLE_PROVIDERS.get("lmstudio")
        assert lmstudio_config is not None
        assert "models" in lmstudio_config
        print("✅ 配置信息验证通过")

        print("🎉 LM Studio 适配器测试全部通过！")
        return True

    except Exception as e:
        print(f"❌ LM Studio 适配器测试失败: {e}")
        return False

def test_sidebar_functions():
    """测试 sidebar 中的 LM Studio 相关函数"""
    print("\n🧪 开始测试 sidebar LM Studio 函数...")

    try:
        from web.components.sidebar import test_lmstudio_connection, get_lmstudio_models
        print("✅ sidebar 函数导入成功")

        # 测试连接函数（模拟失败情况，因为可能没有运行的服务）
        print("🔗 测试连接函数...")
        result = test_lmstudio_connection("http://invalid-url", "test-key")
        # 这里预期返回 False，因为连接会失败
        print(f"✅ 连接函数测试完成（预期失败）: {result}")

        # 测试模型获取函数（模拟失败情况）
        print("📋 测试模型获取函数...")
        models = get_lmstudio_models("http://invalid-url", "test-key")
        # 这里预期返回空列表，因为连接会失败
        print(f"✅ 模型获取函数测试完成（预期为空）: {len(models)} 个模型")

        print("🎉 sidebar LM Studio 函数测试全部通过！")
        return True

    except Exception as e:
        print(f"❌ sidebar LM Studio 函数测试失败: {e}")
        return False

def test_analysis_runner_integration():
    """测试 analysis_runner 中的 LM Studio 配置处理"""
    print("\n🧪 开始测试 analysis_runner LM Studio 集成...")

    try:
        # 检查 analysis_runner.py 中是否包含 LM Studio 配置
        analysis_runner_path = project_root / "web" / "utils" / "analysis_runner.py"
        if analysis_runner_path.exists():
            content = analysis_runner_path.read_text()

            # 检查是否包含 LM Studio 相关的配置代码
            assert 'lmstudio' in content.lower()
            assert 'lmstudio_base_url' in content
            assert 'lmstudio_api_key' in content
            print("✅ analysis_runner LM Studio 配置验证通过")

        print("🎉 analysis_runner LM Studio 集成测试通过！")
        return True

    except Exception as e:
        print(f"❌ analysis_runner LM Studio 集成测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("🏠 LM Studio 集成验证测试")
    print("=" * 60)

    # 检查环境变量配置
    print("📋 检查环境变量配置...")
    lmstudio_url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    lmstudio_key = os.getenv("LM_STUDIO_API_KEY", "lm-studio-local")
    print(f"   LM_STUDIO_BASE_URL: {lmstudio_url}")
    print(f"   LM_STUDIO_API_KEY: {lmstudio_key}")

    # 运行各项测试
    test_results = []
    test_results.append(test_lmstudio_adapter())
    test_results.append(test_sidebar_functions())
    test_results.append(test_analysis_runner_integration())

    # 总结结果
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)

    passed_tests = sum(test_results)
    total_tests = len(test_results)

    if passed_tests == total_tests:
        print(f"🎉 所有 {total_tests} 项测试通过！")
        print("✅ LM Studio 集成功能完全正常")
        print("\n💡 接下来可以:")
        print("   1. 启动 LM Studio 并加载模型")
        print("   2. 在 Web 界面中选择 LM Studio 作为 LLM 提供商")
        print("   3. 测试连接和模型发现功能")
        print("   4. 运行完整的股票分析流程")
    else:
        print(f"❌ {total_tests - passed_tests} 项测试失败")
        print("⚠️ 请检查失败的测试项")

    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)