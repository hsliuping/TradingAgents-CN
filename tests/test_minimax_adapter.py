#!/usr/bin/env python3
"""
MiniMax 适配器单元测试与集成测试
测试 MiniMax LLM 适配器的核心功能
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


class TestMiniMaxTemperatureClamping(unittest.TestCase):
    """测试 MiniMax temperature 限制逻辑"""

    def test_clamp_zero_temperature(self):
        """temperature=0 应被限制到 0.01"""
        from tradingagents.llm_adapters.minimax_adapter import _clamp_temperature
        self.assertAlmostEqual(_clamp_temperature(0.0), 0.01)

    def test_clamp_negative_temperature(self):
        """负数 temperature 应被限制到 0.01"""
        from tradingagents.llm_adapters.minimax_adapter import _clamp_temperature
        self.assertAlmostEqual(_clamp_temperature(-0.5), 0.01)

    def test_clamp_above_max_temperature(self):
        """超过 1.0 的 temperature 应被限制到 1.0"""
        from tradingagents.llm_adapters.minimax_adapter import _clamp_temperature
        self.assertAlmostEqual(_clamp_temperature(1.5), 1.0)
        self.assertAlmostEqual(_clamp_temperature(2.0), 1.0)

    def test_valid_temperature_unchanged(self):
        """有效范围内的 temperature 不应改变"""
        from tradingagents.llm_adapters.minimax_adapter import _clamp_temperature
        self.assertAlmostEqual(_clamp_temperature(0.1), 0.1)
        self.assertAlmostEqual(_clamp_temperature(0.5), 0.5)
        self.assertAlmostEqual(_clamp_temperature(1.0), 1.0)

    def test_edge_temperature(self):
        """边界值 temperature 测试"""
        from tradingagents.llm_adapters.minimax_adapter import _clamp_temperature
        # 0.01 应该保持不变
        self.assertAlmostEqual(_clamp_temperature(0.01), 0.01)
        # 1.0 应该保持不变
        self.assertAlmostEqual(_clamp_temperature(1.0), 1.0)


class TestMiniMaxModels(unittest.TestCase):
    """测试 MiniMax 模型列表"""

    def test_model_list_has_required_models(self):
        """模型列表应包含 MiniMax-M3、MiniMax-M2.7 和 MiniMax-M2.7-highspeed"""
        from tradingagents.llm_adapters.minimax_adapter import MINIMAX_MODELS
        self.assertIn("MiniMax-M3", MINIMAX_MODELS)
        self.assertIn("MiniMax-M2.7", MINIMAX_MODELS)
        self.assertIn("MiniMax-M2.7-highspeed", MINIMAX_MODELS)

    def test_model_context_length(self):
        """模型上下文长度应符合预期：M3 512K，M2.7 系列 204800"""
        from tradingagents.llm_adapters.minimax_adapter import MINIMAX_MODELS
        self.assertEqual(MINIMAX_MODELS["MiniMax-M3"]["context_length"], 512000)
        self.assertEqual(MINIMAX_MODELS["MiniMax-M2.7"]["context_length"], 204800)
        self.assertEqual(MINIMAX_MODELS["MiniMax-M2.7-highspeed"]["context_length"], 204800)

    def test_m3_max_output_tokens(self):
        """M3 最大输出应为 128000"""
        from tradingagents.llm_adapters.minimax_adapter import MINIMAX_MODELS
        self.assertEqual(MINIMAX_MODELS["MiniMax-M3"]["max_output_tokens"], 128000)

    def test_m3_supports_images(self):
        """M3 应支持图片输入"""
        from tradingagents.llm_adapters.minimax_adapter import MINIMAX_MODELS
        self.assertTrue(MINIMAX_MODELS["MiniMax-M3"].get("supports_images", False))

    def test_model_supports_function_calling(self):
        """所有模型都应支持 Function Calling"""
        from tradingagents.llm_adapters.minimax_adapter import MINIMAX_MODELS
        self.assertTrue(MINIMAX_MODELS["MiniMax-M3"]["supports_function_calling"])
        self.assertTrue(MINIMAX_MODELS["MiniMax-M2.7"]["supports_function_calling"])
        self.assertTrue(MINIMAX_MODELS["MiniMax-M2.7-highspeed"]["supports_function_calling"])

    def test_get_available_models(self):
        """get_available_minimax_models 应返回 M3 + M2.7 系列"""
        from tradingagents.llm_adapters.minimax_adapter import get_available_minimax_models
        models = get_available_minimax_models()
        self.assertEqual(len(models), 3)
        self.assertIn("MiniMax-M3", models)
        self.assertIn("MiniMax-M2.7", models)

    def test_no_legacy_models(self):
        """模型列表不应包含已废弃的旧版本（M2.5/M2.1/M2/M1）"""
        from tradingagents.llm_adapters.minimax_adapter import MINIMAX_MODELS
        legacy = {"MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2", "MiniMax-M1"}
        for model_name in MINIMAX_MODELS:
            self.assertNotIn(model_name, legacy,
                             f"旧版模型 {model_name} 不应出现在列表中")


class TestChatMiniMaxInit(unittest.TestCase):
    """测试 ChatMiniMax 初始化"""

    def test_missing_api_key_raises_error(self):
        """缺少 API Key 时应抛出 ValueError"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        with patch.dict(os.environ, {}, clear=True):
            # 确保环境变量中没有 MINIMAX_API_KEY
            os.environ.pop("MINIMAX_API_KEY", None)
            with self.assertRaises(ValueError) as ctx:
                ChatMiniMax(api_key=None)
            self.assertIn("MINIMAX_API_KEY", str(ctx.exception))

    def test_placeholder_api_key_rejected(self):
        """占位符 API Key 应被拒绝"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "your_minimax_api_key_here"}):
            with self.assertRaises(ValueError):
                ChatMiniMax(api_key=None)

    def test_valid_api_key_accepted(self):
        """有效 API Key 应被接受并成功初始化"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        llm = ChatMiniMax(api_key="sk-test-valid-minimax-api-key-12345")
        self.assertEqual(llm.model_name, "MiniMax-M3")

    def test_default_model(self):
        """默认模型应为 MiniMax-M3"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        llm = ChatMiniMax(api_key="sk-test-valid-minimax-api-key-12345")
        self.assertEqual(llm.model_name, "MiniMax-M3")

    def test_custom_model(self):
        """自定义模型应被接受"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        llm = ChatMiniMax(
            model="MiniMax-M2.7-highspeed",
            api_key="sk-test-valid-minimax-api-key-12345"
        )
        self.assertEqual(llm.model_name, "MiniMax-M2.7-highspeed")

    def test_env_base_url(self):
        """环境变量中的 base_url 应被使用"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        with patch.dict(os.environ, {"MINIMAX_BASE_URL": "https://api.minimaxi.com/v1"}):
            llm = ChatMiniMax(api_key="sk-test-valid-minimax-api-key-12345")
            base = getattr(llm, 'openai_api_base', None) or str(getattr(llm, 'base_url', ''))
            # Should use the env var URL (domestic)
            self.assertIn("minimaxi.com", base)


class TestChatMiniMaxTokenEstimation(unittest.TestCase):
    """测试 token 估算功能"""

    def test_estimate_input_tokens(self):
        """输入 token 估算应合理"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        from langchain_core.messages import HumanMessage
        llm = ChatMiniMax(api_key="sk-test-valid-minimax-api-key-12345")
        messages = [HumanMessage(content="Hello, how are you?")]
        tokens = llm._estimate_input_tokens(messages)
        self.assertGreater(tokens, 0)

    def test_estimate_empty_input(self):
        """空消息应返回至少 1 token"""
        from tradingagents.llm_adapters.minimax_adapter import ChatMiniMax
        from langchain_core.messages import HumanMessage
        llm = ChatMiniMax(api_key="sk-test-valid-minimax-api-key-12345")
        messages = [HumanMessage(content="")]
        tokens = llm._estimate_input_tokens(messages)
        self.assertGreaterEqual(tokens, 1)


class TestOpenAICompatibleRegistry(unittest.TestCase):
    """测试 MiniMax 在 OpenAI 兼容注册表中的注册"""

    def test_minimax_in_registry(self):
        """MiniMax 应在 OPENAI_COMPATIBLE_PROVIDERS 中注册"""
        from tradingagents.llm_adapters.openai_compatible_base import OPENAI_COMPATIBLE_PROVIDERS
        self.assertIn("minimax", OPENAI_COMPATIBLE_PROVIDERS)

    def test_minimax_registry_models(self):
        """注册表中的模型列表应正确"""
        from tradingagents.llm_adapters.openai_compatible_base import OPENAI_COMPATIBLE_PROVIDERS
        minimax = OPENAI_COMPATIBLE_PROVIDERS["minimax"]
        self.assertIn("MiniMax-M3", minimax["models"])
        self.assertIn("MiniMax-M2.7", minimax["models"])
        self.assertIn("MiniMax-M2.7-highspeed", minimax["models"])

    def test_minimax_registry_m3_first(self):
        """注册表中 M3 应该是第一个模型（默认模型）"""
        from tradingagents.llm_adapters.openai_compatible_base import OPENAI_COMPATIBLE_PROVIDERS
        minimax = OPENAI_COMPATIBLE_PROVIDERS["minimax"]
        first_model = next(iter(minimax["models"]))
        self.assertEqual(first_model, "MiniMax-M3")

    def test_minimax_registry_m3_context_length(self):
        """注册表中 M3 上下文长度应为 512000"""
        from tradingagents.llm_adapters.openai_compatible_base import OPENAI_COMPATIBLE_PROVIDERS
        minimax = OPENAI_COMPATIBLE_PROVIDERS["minimax"]
        self.assertEqual(minimax["models"]["MiniMax-M3"]["context_length"], 512000)

    def test_minimax_registry_base_url(self):
        """注册表中的 base_url 应为海外版"""
        from tradingagents.llm_adapters.openai_compatible_base import OPENAI_COMPATIBLE_PROVIDERS
        minimax = OPENAI_COMPATIBLE_PROVIDERS["minimax"]
        self.assertEqual(minimax["base_url"], "https://api.minimax.io/v1")

    def test_minimax_registry_api_key_env(self):
        """注册表中的 API Key 环境变量名应正确"""
        from tradingagents.llm_adapters.openai_compatible_base import OPENAI_COMPATIBLE_PROVIDERS
        minimax = OPENAI_COMPATIBLE_PROVIDERS["minimax"]
        self.assertEqual(minimax["api_key_env"], "MINIMAX_API_KEY")

    def test_minimax_adapter_class_exists(self):
        """注册表中的适配器类应正确"""
        from tradingagents.llm_adapters.openai_compatible_base import (
            OPENAI_COMPATIBLE_PROVIDERS, ChatMiniMaxOpenAI
        )
        minimax = OPENAI_COMPATIBLE_PROVIDERS["minimax"]
        self.assertEqual(minimax["adapter_class"], ChatMiniMaxOpenAI)

    def test_minimax_unified_adapter_instantiation(self):
        """统一适配器类应能使用测试 API Key 实例化"""
        from tradingagents.llm_adapters.openai_compatible_base import ChatMiniMaxOpenAI
        adapter = ChatMiniMaxOpenAI(
            model="MiniMax-M3",
            api_key="sk-test-valid-minimax-api-key-12345"
        )
        self.assertIsNotNone(adapter)

    def test_factory_creates_minimax(self):
        """统一工厂函数应能创建 MiniMax 实例"""
        from tradingagents.llm_adapters.openai_compatible_base import create_openai_compatible_llm
        llm = create_openai_compatible_llm(
            provider="minimax",
            model="MiniMax-M3",
            api_key="sk-test-valid-minimax-api-key-12345"
        )
        self.assertIsNotNone(llm)


class TestChatMiniMaxExport(unittest.TestCase):
    """测试 ChatMiniMax 在 __init__.py 中的导出"""

    def test_chatminimax_importable(self):
        """ChatMiniMax 应能从 llm_adapters 包导入"""
        from tradingagents.llm_adapters import ChatMiniMax
        self.assertIsNotNone(ChatMiniMax)

    def test_create_minimax_llm_importable(self):
        """create_minimax_llm 应能导入"""
        from tradingagents.llm_adapters.minimax_adapter import create_minimax_llm
        self.assertIsNotNone(create_minimax_llm)


class TestMiniMaxIntegration(unittest.TestCase):
    """
    MiniMax 集成测试（需要有效的 MINIMAX_API_KEY）
    当 MINIMAX_API_KEY 环境变量未设置时，这些测试会被跳过
    """

    @classmethod
    def setUpClass(cls):
        """检查 API Key 是否可用"""
        cls.api_key = os.getenv("MINIMAX_API_KEY")
        if not cls.api_key or cls.api_key.startswith("your_"):
            cls.api_key = None

    def test_integration_basic_chat(self):
        """集成测试：基本聊天功能（默认 M3 模型）"""
        if not self.api_key:
            self.skipTest("MINIMAX_API_KEY 未设置，跳过集成测试")

        from tradingagents.llm_adapters.minimax_adapter import create_minimax_llm

        llm = create_minimax_llm(
            model="MiniMax-M3",
            api_key=self.api_key,
            max_tokens=50
        )

        response = llm.invoke("你好，请用一句话介绍一下你自己。")
        self.assertIsNotNone(response)
        self.assertTrue(hasattr(response, 'content'))
        self.assertTrue(len(response.content) > 0)
        print(f"✅ 基本聊天响应: {response.content[:100]}...")

    def test_integration_highspeed_model(self):
        """集成测试：M2.7-highspeed 模型"""
        if not self.api_key:
            self.skipTest("MINIMAX_API_KEY 未设置，跳过集成测试")

        from tradingagents.llm_adapters.minimax_adapter import create_minimax_llm

        llm = create_minimax_llm(
            model="MiniMax-M2.7-highspeed",
            api_key=self.api_key,
            max_tokens=50
        )

        response = llm.invoke("What is 2 + 2?")
        self.assertIsNotNone(response)
        self.assertTrue(len(response.content) > 0)
        print(f"✅ Highspeed 模型响应: {response.content[:100]}...")

    def test_integration_connection_test(self):
        """集成测试：连接测试函数"""
        if not self.api_key:
            self.skipTest("MINIMAX_API_KEY 未设置，跳过集成测试")

        from tradingagents.llm_adapters.minimax_adapter import test_minimax_connection

        result = test_minimax_connection(api_key=self.api_key)
        self.assertTrue(result)
        print(f"✅ 连接测试通过")


if __name__ == "__main__":
    unittest.main(verbosity=2)
