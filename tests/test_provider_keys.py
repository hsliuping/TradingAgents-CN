import unittest
from unittest.mock import patch

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.model_catalog import get_model_options
from tradingagents.llm_clients.openai_client import OpenAIClient
from tradingagents.llm_clients.provider_keys import (
    canonical_aliases,
    default_backend_url,
    env_key_for_provider,
    env_keys_for_provider,
    normalize_provider_key,
)
from tradingagents.llm_clients.validators import validate_model


class ProviderKeysTests(unittest.TestCase):
    def test_normalize_dashscope_to_qwen(self):
        self.assertEqual(normalize_provider_key("dashscope"), "qwen")
        self.assertEqual(normalize_provider_key("阿里百炼"), "qwen")

    def test_normalize_zhipu_to_glm(self):
        self.assertEqual(normalize_provider_key("zhipu"), "glm")
        self.assertEqual(normalize_provider_key("智谱AI"), "glm")

    def test_env_key_mapping(self):
        self.assertEqual(env_key_for_provider("qwen"), "DASHSCOPE_API_KEY")
        self.assertEqual(env_key_for_provider("dashscope"), "DASHSCOPE_API_KEY")
        self.assertEqual(env_key_for_provider("glm"), "ZHIPU_API_KEY")
        self.assertEqual(env_key_for_provider("atlascloud"), "ATLASCLOUD_API_KEY")
        self.assertEqual(
            env_keys_for_provider("atlas-cloud"),
            ["ATLASCLOUD_API_KEY", "ATLAS_CLOUD_API_KEY"],
        )

    def test_default_backend_url_mapping(self):
        self.assertIn("dashscope.aliyuncs.com", default_backend_url("qwen"))
        self.assertIn("open.bigmodel.cn", default_backend_url("glm"))
        self.assertEqual(default_backend_url("atlas"), "https://api.atlascloud.ai/v1")

    def test_canonical_aliases(self):
        self.assertIn("dashscope", canonical_aliases("qwen"))
        self.assertIn("zhipu", canonical_aliases("glm"))
        self.assertIn("atlas-cloud", canonical_aliases("atlascloud"))

    def test_normalize_atlascloud_aliases(self):
        self.assertEqual(normalize_provider_key("atlascloud"), "atlascloud")
        self.assertEqual(normalize_provider_key("atlas"), "atlascloud")
        self.assertEqual(normalize_provider_key("Atlas Cloud"), "atlascloud")

    def test_atlascloud_model_catalog_and_validation(self):
        quick_models = [value for _, value in get_model_options("atlascloud", "quick")]
        deep_models = [value for _, value in get_model_options("atlascloud", "deep")]

        self.assertIn("qwen/qwen3.5-flash", quick_models)
        self.assertIn("deepseek-ai/deepseek-v4-pro", deep_models)
        self.assertTrue(validate_model("atlascloud", "qwen/qwen3.5-flash"))
        self.assertFalse(validate_model("atlascloud", "qwen-turbo"))

    def test_atlascloud_factory_and_env_alias(self):
        client = create_llm_client("atlas-cloud", "qwen/qwen3.5-flash")
        self.assertIsInstance(client, OpenAIClient)
        self.assertEqual(client.provider, "atlascloud")

        with patch.dict(
            "os.environ",
            {
                "ATLAS_CLOUD_API_KEY": "test-api-key",
                "ATLASCLOUD_BASE_URL": "https://atlas.example/v1",
            },
            clear=True,
        ):
            with patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI") as mock_chat:
                client.get_llm()

        self.assertEqual(mock_chat.call_args.kwargs["base_url"], "https://atlas.example/v1")
        self.assertEqual(mock_chat.call_args.kwargs["api_key"], "test-api-key")


if __name__ == "__main__":
    unittest.main()
