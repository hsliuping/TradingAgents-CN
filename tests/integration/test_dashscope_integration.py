#!/usr/bin/env python3
"""
阿里百炼大模型集成测试脚本

需要环境变量：
- TEST_DASHSCOPE_API_KEY
- TEST_FINNHUB_API_KEY

未配置时应 skipped，而不是 failed。
"""

import os
import sys
from pathlib import Path

import pytest

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

from tests.conftest import require_env

pytestmark = pytest.mark.integration

def test_import():
    """测试导入是否正常"""
    print("🔍 测试1: 检查模块导入...")
    try:
        from tradingagents.llm_adapters import ChatDashScope
        print("✅ ChatDashScope 导入成功")
        
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        print("✅ TradingAgentsGraph 导入成功")
        
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_api_key():
    """测试API密钥配置"""
    print("\n🔍 测试2: 检查API密钥配置...")

    dashscope_key = require_env("TEST_DASHSCOPE_API_KEY")
    finnhub_key = require_env("TEST_FINNHUB_API_KEY")

    print(f"✅ TEST_DASHSCOPE_API_KEY: {dashscope_key[:10]}...")
    print(f"✅ TEST_FINNHUB_API_KEY: {finnhub_key[:10]}...")
    
    return True

def test_dashscope_connection():
    """测试阿里百炼连接"""
    print("\n🔍 测试3: 检查阿里百炼连接...")
    
    try:
        import dashscope
        from dashscope import Generation
        
        # 设置API密钥
        dashscope.api_key = require_env("TEST_DASHSCOPE_API_KEY")
        
        # 测试简单调用
        response = Generation.call(
            model="qwen-turbo",
            messages=[{"role": "user", "content": "你好，请回复'连接成功'"}],
            result_format="message"
        )
        
        if response.status_code == 200:
            content = response.output.choices[0].message.content
            print(f"✅ 阿里百炼连接成功: {content}")
            return True
        else:
            print(f"❌ 阿里百炼连接失败: {response.code} - {response.message}")
            return False
            
    except Exception as e:
        print(f"❌ 阿里百炼连接测试失败: {e}")
        return False

def test_langchain_adapter():
    """测试LangChain适配器"""
    print("\n🔍 测试4: 检查LangChain适配器...")
    
    try:
        from tradingagents.llm_adapters import ChatDashScope
        from langchain_core.messages import HumanMessage
        
        # 创建适配器实例
        llm = ChatDashScope(model="qwen-turbo")
        
        # 测试调用
        messages = [HumanMessage(content="请回复'适配器工作正常'")]
        response = llm.invoke(messages)
        
        print(f"✅ LangChain适配器工作正常: {response.content}")
        return True
        
    except Exception as e:
        print(f"❌ LangChain适配器测试失败: {e}")
        return False

def test_trading_graph_config():
    """测试TradingGraph配置"""
    print("\n🔍 测试5: 检查TradingGraph配置...")
    
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        
        # 创建阿里百炼配置
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = "dashscope"
        config["deep_think_llm"] = "qwen-plus"
        config["quick_think_llm"] = "qwen-turbo"
        
        # 尝试初始化（不运行分析）
        ta = TradingAgentsGraph(debug=False, config=config)
        
        print("✅ TradingGraph 配置成功")
        print(f"   深度思考模型: {config['deep_think_llm']}")
        print(f"   快速思考模型: {config['quick_think_llm']}")
        return True
        
    except Exception as e:
        print(f"❌ TradingGraph 配置失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 阿里百炼大模型集成测试")
    print("=" * 50)
    
    tests = [
        test_import,
        test_api_key,
        test_dashscope_connection,
        test_langchain_adapter,
        test_trading_graph_config,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！阿里百炼集成工作正常")
        print("\n💡 下一步:")
        print("   1. 运行 python demo_dashscope.py 进行完整测试")
        print("   2. 或使用 python -m cli.main analyze 启动交互式分析")
    else:
        print("⚠️  部分测试失败，请检查配置")
        print("\n🔧 故障排除:")
        print("   1. 确认已安装 dashscope: pip install dashscope")
        print("   2. 检查API密钥是否正确设置")
        print("   3. 确认网络连接正常")
        print("   4. 查看详细错误信息")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
