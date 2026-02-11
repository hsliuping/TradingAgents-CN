#!/usr/bin/env python3
"""
TradingAgents LazyLLM 适配器测试脚本

运行方式:
    # 设置环境变量
    export TRADING_QWEN_API_KEY=sk-xxx
    
    # 运行测试
    python -m tradingagents.llm_adapters.lazyllm.test
"""

import os
import sys

# 确保可以导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def test_config():
    """测试配置模块"""
    print("\n" + "=" * 50)
    print("测试 1: 配置模块")
    print("=" * 50)
    
    from tradingagents.llm_adapters.lazyllm.config import trading_config, LAZYLLM_AVAILABLE
    
    print(f"LazyLLM 可用: {LAZYLLM_AVAILABLE}")
    
    config_summary = trading_config.get_config_summary()
    print(f"配置摘要:")
    for key, value in config_summary.items():
        print(f"  {key}: {value}")
    
    # 检查 API Key
    for source in ['qwen', 'deepseek', 'zhipu', 'openai']:
        api_key = trading_config.get_api_key(source)
        print(f"  {source} API Key: {'已设置' if api_key else '未设置'}")
    
    return True


def test_adapter():
    """测试 LangChain 适配器"""
    print("\n" + "=" * 50)
    print("测试 2: TradingLLMAdapter (LangChain 兼容)")
    print("=" * 50)
    
    from tradingagents.llm_adapters.lazyllm import TradingLLMAdapter, create_trading_llm
    from tradingagents.llm_adapters.lazyllm.config import trading_config
    
    # 检查是否有可用的 API Key
    api_key = trading_config.get_api_key(trading_config.default_source)
    if not api_key:
        print("⚠️ 未找到 API Key，跳过适配器测试")
        print("请设置环境变量，如: TRADING_QWEN_API_KEY=sk-xxx")
        return False
    
    try:
        # 创建适配器
        print(f"创建 TradingLLMAdapter (source={trading_config.default_source})...")
        llm = create_trading_llm()
        
        print(f"模型: {llm.model_name}")
        print(f"来源: {llm.source}")
        
        # 测试调用
        print("\n发送测试请求...")
        response = llm.invoke("你好，请用一句话介绍自己")
        
        print(f"✅ 响应成功!")
        print(f"响应内容: {response.content[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_automodel():
    """测试 TradingAutoModel"""
    print("\n" + "=" * 50)
    print("测试 3: TradingAutoModel (LazyLLM 原生)")
    print("=" * 50)
    
    from tradingagents.llm_adapters.lazyllm.config import trading_config, LAZYLLM_AVAILABLE
    
    if not LAZYLLM_AVAILABLE:
        print("⚠️ LazyLLM 未安装，跳过 AutoModel 测试")
        return False
    
    # 检查是否有可用的 API Key
    api_key = trading_config.get_api_key(trading_config.default_source)
    if not api_key:
        print("⚠️ 未找到 API Key，跳过 AutoModel 测试")
        return False
    
    try:
        from tradingagents.llm_adapters.lazyllm import TradingAutoModel
        
        print(f"创建 TradingAutoModel...")
        model = TradingAutoModel()
        
        print(f"模型信息: {model.get_info()}")
        
        # 测试调用
        print("\n发送测试请求...")
        response = model("你好，请用一句话介绍自己")
        
        print(f"✅ 响应成功!")
        print(f"响应内容: {response[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """集成测试 - 模拟实际使用场景"""
    print("\n" + "=" * 50)
    print("测试 4: 集成测试 - 股票分析场景")
    print("=" * 50)
    
    from tradingagents.llm_adapters.lazyllm import create_trading_llm
    from tradingagents.llm_adapters.lazyllm.config import trading_config
    
    api_key = trading_config.get_api_key(trading_config.default_source)
    if not api_key:
        print("⚠️ 未找到 API Key，跳过集成测试")
        return False
    
    try:
        llm = create_trading_llm()
        
        # 模拟股票分析请求
        query = """
        作为一个股票分析师，请简要分析以下信息：
        - 股票代码: 600519 (贵州茅台)
        - 当前价格: 1500元
        - 今日涨幅: +2.5%
        
        请给出简短的技术面分析观点（50字以内）。
        """
        
        print("发送股票分析请求...")
        response = llm.invoke(query)
        
        print(f"✅ 响应成功!")
        print(f"分析结果: {response.content}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("TradingAgents LazyLLM 适配器测试")
    print("=" * 60)
    
    results = {}
    
    # 测试配置
    results['config'] = test_config()
    
    # 测试适配器
    results['adapter'] = test_adapter()
    
    # 测试 AutoModel
    results['automodel'] = test_automodel()
    
    # 集成测试
    results['integration'] = test_integration()
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败/跳过"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
