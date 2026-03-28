#!/usr/bin/env python3
"""
配置管理功能测试
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.config.config_manager import ConfigManager, ModelConfig, PricingConfig, TokenTracker


@pytest.fixture(autouse=True)
def disable_mongodb_storage(monkeypatch):
    """配置管理测试默认走本地 JSON，避免依赖外部 MongoDB 环境。"""
    monkeypatch.setenv("USE_MONGODB_STORAGE", "false")


def test_config_manager():
    """测试配置管理器基本功能"""
    print("🧪 测试配置管理器")
    print("=" * 50)
    
    # 创建临时目录用于测试
    with tempfile.TemporaryDirectory() as temp_dir:
        config_manager = ConfigManager(temp_dir)
        
        # 测试模型配置
        print("📝 测试模型配置...")
        models = config_manager.load_models()
        assert len(models) > 0, "应该有默认模型配置"
        
        # 添加新模型
        new_model = ModelConfig(
            provider="test_provider",
            model_name="test_model",
            api_key="test_key_123",
            max_tokens=2000,
            temperature=0.5
        )
        
        models.append(new_model)
        config_manager.save_models(models)
        
        # 重新加载验证
        reloaded_models = config_manager.load_models()
        assert len(reloaded_models) == len(models), "模型数量应该匹配"
        
        test_model = next((m for m in reloaded_models if m.provider == "test_provider"), None)
        assert test_model is not None, "应该找到测试模型"
        assert test_model.api_key == "test_key_123", "API密钥应该匹配"
        
        print("✅ 模型配置测试通过")
        
        # 测试定价配置
        print("📝 测试定价配置...")
        pricing_configs = config_manager.load_pricing()
        assert len(pricing_configs) > 0, "应该有默认定价配置"
        
        # 添加新定价
        new_pricing = PricingConfig(
            provider="test_provider",
            model_name="test_model",
            input_price_per_1k=0.001,
            output_price_per_1k=0.002,
            currency="CNY"
        )
        
        pricing_configs.append(new_pricing)
        config_manager.save_pricing(pricing_configs)
        
        # 测试成本计算
        cost, currency = config_manager.calculate_cost("test_provider", "test_model", 1000, 500)
        expected_cost = (1000 / 1000) * 0.001 + (500 / 1000) * 0.002
        assert abs(cost - expected_cost) < 0.000001, f"成本计算错误: {cost} != {expected_cost}"
        assert currency == "CNY", f"货币单位应该匹配: {currency}"
        
        print("✅ 定价配置测试通过")
        
        # 测试使用记录
        print("📝 测试使用记录...")
        record = config_manager.add_usage_record(
            provider="test_provider",
            model_name="test_model",
            input_tokens=1000,
            output_tokens=500,
            session_id="test_session",
            analysis_type="test_analysis"
        )
        
        assert record.cost == expected_cost, "使用记录成本应该匹配"
        
        # 测试统计
        stats = config_manager.get_usage_statistics(30)
        assert stats["total_requests"] >= 1, "应该有至少一条使用记录"
        assert stats["total_cost"] >= expected_cost, "总成本应该包含测试记录"
        
        print("✅ 使用记录测试通过")
        
        # 测试设置
        print("📝 测试系统设置...")
        settings = config_manager.load_settings()
        assert "default_provider" in settings, "应该有默认设置"
        
        settings["test_setting"] = "test_value"
        config_manager.save_settings(settings)
        
        reloaded_settings = config_manager.load_settings()
        assert reloaded_settings["test_setting"] == "test_value", "设置应该被保存"
        
        print("✅ 系统设置测试通过")


def test_token_tracker():
    """测试Token跟踪器"""
    print("\n🧪 测试Token跟踪器")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_manager = ConfigManager(temp_dir)
        token_tracker = TokenTracker(config_manager)
        
        # 测试使用跟踪
        print("📝 测试使用跟踪...")
        record = token_tracker.track_usage(
            provider="dashscope",
            model_name="qwen-turbo",
            input_tokens=2000,
            output_tokens=1000,
            session_id="test_session_123",
            analysis_type="stock_analysis"
        )
        
        assert record is not None, "应该返回使用记录"
        assert record.input_tokens == 2000, "输入token数应该匹配"
        assert record.output_tokens == 1000, "输出token数应该匹配"
        assert record.cost > 0, "成本应该大于0"
        
        print("✅ 使用跟踪测试通过")
        
        # 测试成本估算
        print("📝 测试成本估算...")
        estimated_cost, currency = token_tracker.estimate_cost(
            provider="dashscope",
            model_name="qwen-turbo",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )

        assert estimated_cost > 0, "估算成本应该大于0"
        assert currency == "CNY", f"货币单位应该匹配: {currency}"
        
        print("✅ 成本估算测试通过")
        
        # 测试会话成本
        print("📝 测试会话成本...")
        session_cost = token_tracker.get_session_cost("test_session_123")
        assert session_cost == record.cost, "会话成本应该匹配记录成本"
        
        print("✅ 会话成本测试通过")


def test_pricing_accuracy():
    """测试定价准确性"""
    print("\n🧪 测试定价准确性")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_manager = ConfigManager(temp_dir)
        
        # 测试不同供应商的定价
        test_cases = [
            ("dashscope", "qwen-turbo", 1000, 500),
            ("dashscope", "qwen-plus", 2000, 1000),
            ("openai", "gpt-3.5-turbo", 1000, 500),
            ("google", "gemini-pro", 1000, 500),
        ]
        
        for provider, model, input_tokens, output_tokens in test_cases:
            cost, currency = config_manager.calculate_cost(provider, model, input_tokens, output_tokens)
            print(f"📊 {provider} {model}: {input_tokens}+{output_tokens} tokens = ¥{cost:.6f}")
            
            # 验证成本计算逻辑
            pricing_configs = config_manager.load_pricing()
            pricing = next((p for p in pricing_configs if p.provider == provider and p.model_name == model), None)
            
            if pricing:
                expected_cost = (input_tokens / 1000) * pricing.input_price_per_1k + (output_tokens / 1000) * pricing.output_price_per_1k
                assert abs(cost - expected_cost) < 0.000001, f"成本计算错误: {cost} != {expected_cost}"
                assert currency == pricing.currency, f"货币单位应该匹配: {currency} != {pricing.currency}"
            else:
                assert cost == 0.0, f"未知模型应该返回0成本，但得到 {cost}"
                assert currency == "CNY", f"未知模型应该返回默认货币单位，但得到 {currency}"
        
        print("✅ 定价准确性测试通过")


def test_usage_statistics():
    """测试使用统计功能"""
    print("\n🧪 测试使用统计功能")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_manager = ConfigManager(temp_dir)
        
        # 添加多条使用记录
        test_records = [
            ("dashscope", "qwen-turbo", 1000, 500, "session1", "stock_analysis"),
            ("dashscope", "qwen-plus", 2000, 1000, "session2", "stock_analysis"),
            ("openai", "gpt-3.5-turbo", 1500, 750, "session3", "news_analysis"),
            ("google", "gemini-pro", 1200, 600, "session4", "social_analysis"),
        ]
        
        total_expected_cost = 0
        for provider, model, input_tokens, output_tokens, session_id, analysis_type in test_records:
            record = config_manager.add_usage_record(
                provider=provider,
                model_name=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                session_id=session_id,
                analysis_type=analysis_type
            )
            total_expected_cost += record.cost
        
        # 测试统计数据
        stats = config_manager.get_usage_statistics(30)
        
        assert stats["total_requests"] == len(test_records), f"请求数应该是 {len(test_records)}"
        print(f"📊 统计总成本: {stats['total_cost']:.6f}, 预期总成本: {total_expected_cost:.6f}")
        assert abs(stats["total_cost"] - total_expected_cost) < 0.001, "总成本应该匹配"
        
        # 测试按供应商统计
        provider_stats = stats["provider_stats"]
        assert "dashscope" in provider_stats, "应该有dashscope统计"
        assert "openai" in provider_stats, "应该有openai统计"
        assert "google" in provider_stats, "应该有google统计"
        
        dashscope_stats = provider_stats["dashscope"]
        assert dashscope_stats["requests"] == 2, "dashscope应该有2个请求"
        
        print("✅ 使用统计测试通过")


def main():
    """主测试函数"""
    print("🧪 配置管理功能测试")
    print("=" * 60)
    
    try:
        test_config_manager()
        test_token_tracker()
        test_pricing_accuracy()
        test_usage_statistics()
        
        print("\n🎉 所有测试通过！")
        print("=" * 60)
        print("✅ 配置管理功能正常")
        print("✅ Token跟踪功能正常")
        print("✅ 成本计算准确")
        print("✅ 使用统计正确")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
