"""
LM Studio集成测试
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock
import requests

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tradingagents.llm_adapters.lmstudio_adapter import ChatLMStudio
from web.components.sidebar import test_lmstudio_connection, get_lmstudio_models


class TestLMStudioAdapter:
    """LM Studio适配器测试类"""

    def test_lmstudio_adapter_initialization(self):
        """测试LM Studio适配器初始化"""
        # 模拟环境变量
        with patch.dict(os.environ, {
            "LM_STUDIO_BASE_URL": "http://localhost:1234/v1",
            "LM_STUDIO_API_KEY": "lm-studio-local"
        }):
            adapter = ChatLMStudio(
                model="llama-3.1-8b-instruct",
                temperature=0.1,
                timeout=30
            )

            assert adapter.provider_name == "lmstudio"
            assert adapter.model_name == "llama-3.1-8b-instruct"
            assert adapter.base_url == "http://localhost:1234/v1"

    def test_lmstudio_adapter_with_custom_params(self):
        """测试带自定义参数的LM Studio适配器初始化"""
        with patch.dict(os.environ, {
            "LM_STUDIO_BASE_URL": "http://localhost:8080/v1",
            "LM_STUDIO_API_KEY": "test-key-12345"
        }):
            adapter = ChatLMStudio(
                model="custom-model",
                api_key="test-key-12345",
                base_url="http://localhost:8080/v1",
                temperature=0.2,
                max_tokens=2000,
                timeout=60
            )

            assert adapter.model_name == "custom-model"
            assert adapter.base_url == "http://localhost:8080/v1"

    @patch('tradingagents.llm_adapters.lmstudio_adapter.requests.get')
    def test_lmstudio_connection_success(self, mock_get):
        """测试LM Studio连接成功的情况"""
        # 模拟成功的API响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = test_lmstudio_connection("http://localhost:1234/v1", "lm-studio-local")
        assert result is True

    @patch('tradingagents.llm_adapters.lmstudio_adapter.requests.get')
    def test_lmstudio_connection_failure(self, mock_get):
        """测试LM Studio连接失败的情况"""
        # 模拟连接失败
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = test_lmstudio_connection("http://localhost:1234/v1", "lm-studio-local")
        assert result is False

    @patch('tradingagents.llm_adapters.lmstudio_adapter.requests.get')
    def test_lmstudio_get_models_success(self, mock_get):
        """测试获取LM Studio模型列表成功"""
        # 模拟模型列表响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "llama-3.1-8b-instruct"},
                {"id": "qwen2.5-7b-instruct"},
                {"id": "chatglm3-6b"}
            ]
        }
        mock_get.return_value = mock_response

        models = get_lmstudio_models("http://localhost:1234/v1", "lm-studio-local")

        assert len(models) == 3
        assert "llama-3.1-8b-instruct" in models
        assert "qwen2.5-7b-instruct" in models
        assert "chatglm3-6b" in models

    @patch('tradingagents.llm_adapters.lmstudio_adapter.requests.get')
    def test_lmstudio_get_models_failure(self, mock_get):
        """测试获取LM Studio模型列表失败"""
        # 模拟API错误
        mock_get.side_effect = Exception("API Error")

        models = get_lmstudio_models("http://localhost:1234/v1", "lm-studio-local")
        assert models == []


class TestLMStudioIntegration:
    """LM Studio集成端到端测试"""

    def test_sidebar_lmstudio_functions(self):
        """测试sidebar中的LM Studio相关函数"""
        # 测试连接函数
        with patch('tradingagents.web.components.sidebar.requests.get') as mock_get:
            # 模拟成功响应
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            assert test_lmstudio_connection("http://localhost:1234/v1", "lm-studio-local") is True

        # 测试模型获取函数
        with patch('tradingagents.web.components.sidebar.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"id": "test-model"}]
            }
            mock_get.return_value = mock_response

            models = get_lmstudio_models("http://localhost:1234/v1", "lm-studio-local")
            assert models == ["test-model"]

    @patch('tradingagents.llm_adapters.lmstudio_adapter.ChatLMStudio')
    def test_lmstudio_adapter_with_invalid_url(self, mock_adapter):
        """测试无效URL的处理"""
        # 模拟连接验证失败
        mock_adapter.return_value.test_connection = False

        with patch.dict(os.environ, {
            "LM_STUDIO_BASE_URL": "http://invalid-url",
            "LM_STUDIO_API_KEY": "test-key"
        }):
            with pytest.raises(ValueError):
                ChatLMStudio(model="test-model")

    def test_lmstudio_timeout_configuration(self):
        """测试超时配置"""
        with patch.dict(os.environ, {
            "LM_STUDIO_BASE_URL": "http://localhost:1234/v1",
            "LM_STUDIO_API_KEY": "test-key"
        }):
            adapter = ChatLMStudio(
                model="test-model",
                timeout=5  # 5秒超时
            )
            assert adapter.timeout == 5


class TestLMStudioErrorHandling:
    """LM Studio错误处理测试"""

    def test_connection_retry_mechanism(self):
        """测试连接重试机制"""
        with patch.object(ChatLMStudio, '_generate') as mock_generate:
            # 模拟前两次失败，第三次成功
            mock_generate.side_effect = [
                Exception("Connection failed"),
                Exception("Connection failed again"),
                "success"
            ]

            adapter = ChatLMStudio(
                model="test-model",
                base_url="http://localhost:1234/v1",
                api_key="test-key"
            )

            # 这里应该会重试并最终成功
            result = adapter._generate(
                [{"content": "test"}],
                stop=None
            )
            assert result == "success"

    def test_model_not_found_error(self):
        """测试模型不存在错误"""
        with patch.object(ChatLMStudio, '_generate') as mock_generate:
            mock_generate.side_effect = Exception("Model not found")

            adapter = ChatLMStudio(
                model="nonexistent-model",
                base_url="http://localhost:1234/v1",
                api_key="test-key"
            )

            with pytest.raises(Exception):
                adapter._generate(
                    [{"content": "test"}],
                    stop=None
                )

    def test_timeout_error_handling(self):
        """测试超时错误处理"""
        with patch.object(ChatLMStudio, '_generate') as mock_generate:
            mock_generate.side_effect = requests.exceptions.Timeout("Request timeout")

            adapter = ChatLMStudio(
                model="test-model",
                base_url="http://localhost:1234/v1",
                api_key="test-key",
                timeout=1  # 1秒超时
            )

            with pytest.raises(Exception):
                adapter._generate(
                    [{"content": "test"}],
                    stop=None
                )


def run_lmstudio_tests():
    """运行所有LM Studio测试"""
    print("🧪 开始LM Studio集成测试...")

    # 创建测试套件
    test_suite = [
        TestLMStudioAdapter(),
        TestLMStudioIntegration(),
        TestLMStudioErrorHandling()
    ]

    # 运行测试
    all_passed = True
    failed_tests = []

    for test_class in test_suite:
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]

        for test_method in test_methods:
            try:
                print(f"  运行 {test_class.__name__}.{test_method}...")
                test_instance = test_class()
                getattr(test_instance, test_method)()
                print(f"  ✅ {test_method} 通过")
            except Exception as e:
                print(f"  ❌ {test_method} 失败: {e}")
                all_passed = False
                failed_tests.append(f"{test_class.__name__}.{test_method}")

    # 总结结果
    print("\n📊 测试结果总结:")
    if all_passed:
        print("✅ 所有测试通过！")
        print("🎉 LM Studio集成功能正常工作")
    else:
        print(f"❌ {len(failed_tests)} 个测试失败:")
        for test in failed_tests:
            print(f"  - {test}")
        print("\n⚠️ 请检查失败的测试并修复相关问题")

    return all_passed


if __name__ == "__main__":
    run_lmstudio_tests()