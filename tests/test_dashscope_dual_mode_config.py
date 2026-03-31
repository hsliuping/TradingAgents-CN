from app.core.dashscope_modes import (
    DASHSCOPE_CODING_BASE_URL,
    DASHSCOPE_COMPATIBLE_BASE_URL,
    DASHSCOPE_ENDPOINT_MODE_CODING_PLAN,
    DASHSCOPE_ENDPOINT_MODE_COMPATIBLE,
    get_dashscope_base_url_for_model,
    get_dashscope_default_deep_model,
    get_dashscope_default_model,
    get_dashscope_mode_from_base_url,
    get_dashscope_mode_from_model,
)
from app.models.config import LLMConfig, ModelProvider
from app.services.config_service import ConfigService


def test_dashscope_mode_helpers_cover_both_endpoints():
    assert get_dashscope_mode_from_base_url(DASHSCOPE_COMPATIBLE_BASE_URL) == DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    assert get_dashscope_mode_from_base_url(DASHSCOPE_CODING_BASE_URL) == DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
    assert get_dashscope_default_model(DASHSCOPE_ENDPOINT_MODE_COMPATIBLE) == "qwen-turbo"
    assert get_dashscope_default_deep_model(DASHSCOPE_ENDPOINT_MODE_COMPATIBLE) == "qwen-max"
    assert get_dashscope_default_model(DASHSCOPE_ENDPOINT_MODE_CODING_PLAN) == "qwen3.5-plus"
    assert get_dashscope_default_deep_model(DASHSCOPE_ENDPOINT_MODE_CODING_PLAN) == "qwen3-max-2026-01-23"
    assert get_dashscope_mode_from_model("qwen3.5-plus") == DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
    assert get_dashscope_mode_from_model("qwen-turbo") == DASHSCOPE_ENDPOINT_MODE_COMPATIBLE


def test_normalize_dashscope_catalog_keeps_existing_extra_models():
    service = ConfigService()
    normalized = service._normalize_dashscope_model_catalog_data(
        {
            "provider": "dashscope",
            "provider_name": "阿里百炼",
            "models": [
                {
                    "name": "qwen3.5-plus",
                    "display_name": "Qwen 3.5 Plus",
                    "base_url": DASHSCOPE_CODING_BASE_URL,
                },
                {
                    "name": "qwen-experimental",
                    "display_name": "Qwen Experimental",
                    "base_url": DASHSCOPE_COMPATIBLE_BASE_URL,
                },
            ],
        }
    )

    model_modes = {model["name"]: model["endpoint_mode"] for model in normalized["models"]}
    assert "qwen-turbo" in model_modes
    assert "qwen3.5-plus" in model_modes
    assert "qwen-experimental" in model_modes
    assert model_modes["qwen-turbo"] == DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    assert model_modes["qwen3.5-plus"] == DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
    assert model_modes["qwen-experimental"] == DASHSCOPE_ENDPOINT_MODE_COMPATIBLE


def test_dashscope_provider_payload_resets_legacy_coding_default():
    service = ConfigService()
    payload = service._get_dashscope_provider_payload(
        {
            "name": "dashscope",
            "display_name": "阿里百炼",
            "default_base_url": DASHSCOPE_CODING_BASE_URL,
            "extra_config": {},
        }
    )

    assert payload["default_base_url"] == DASHSCOPE_COMPATIBLE_BASE_URL
    assert payload["extra_config"]["endpoint_mode"] == DASHSCOPE_ENDPOINT_MODE_COMPATIBLE


def test_prepare_dashscope_provider_migration_preserves_user_selected_mode_after_first_run():
    service = ConfigService()
    payload = service._prepare_dashscope_provider_for_migration(
        {
            "name": "dashscope",
            "display_name": "阿里百炼",
            "default_base_url": DASHSCOPE_CODING_BASE_URL,
            "extra_config": {
                "endpoint_mode": DASHSCOPE_ENDPOINT_MODE_CODING_PLAN,
                "dual_mode_migrated": True,
            },
        }
    )

    assert payload["default_base_url"] == DASHSCOPE_CODING_BASE_URL
    assert payload["extra_config"]["endpoint_mode"] == DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
    assert payload["extra_config"]["dual_mode_migrated"] is True


def test_normalize_dashscope_system_settings_restores_compatible_defaults():
    service = ConfigService()
    normalized = service._normalize_dashscope_system_settings(
        {
            "quick_analysis_model": "qwen3.5-plus",
            "deep_analysis_model": "qwen3-max-2026-01-23",
            "backend_url": DASHSCOPE_CODING_BASE_URL,
            "quick_backend_url": DASHSCOPE_CODING_BASE_URL,
            "deep_backend_url": DASHSCOPE_CODING_BASE_URL,
        }
    )

    assert normalized["quick_analysis_model"] == "qwen-turbo"
    assert normalized["deep_analysis_model"] == "qwen-max"
    assert normalized["backend_url"] == DASHSCOPE_COMPATIBLE_BASE_URL
    assert normalized["quick_backend_url"] == DASHSCOPE_COMPATIBLE_BASE_URL
    assert normalized["deep_backend_url"] == DASHSCOPE_COMPATIBLE_BASE_URL


def test_normalize_dashscope_system_settings_preserves_non_dashscope_urls():
    service = ConfigService()
    normalized = service._normalize_dashscope_system_settings(
        {
            "quick_analysis_model": "gpt-4o-mini",
            "deep_analysis_model": "deepseek-chat",
            "backend_url": "https://api.openai.com/v1",
            "quick_backend_url": "https://api.openai.com/v1",
            "deep_backend_url": "https://api.deepseek.com",
        }
    )

    assert normalized["quick_analysis_model"] == "gpt-4o-mini"
    assert normalized["deep_analysis_model"] == "deepseek-chat"
    assert normalized["backend_url"] == "https://api.openai.com/v1"
    assert normalized["quick_backend_url"] == "https://api.openai.com/v1"
    assert normalized["deep_backend_url"] == "https://api.deepseek.com"
    assert normalized["_dashscope_dual_mode_migrated"] is True


def test_normalize_dashscope_system_settings_keeps_user_selected_coding_defaults_after_migration():
    service = ConfigService()
    normalized = service._normalize_dashscope_system_settings(
        {
            "quick_analysis_model": "qwen3.5-plus",
            "deep_analysis_model": "qwen3-max-2026-01-23",
            "backend_url": DASHSCOPE_CODING_BASE_URL,
            "quick_backend_url": DASHSCOPE_CODING_BASE_URL,
            "deep_backend_url": DASHSCOPE_CODING_BASE_URL,
            "_dashscope_dual_mode_migrated": True,
        }
    )

    assert normalized["quick_analysis_model"] == "qwen3.5-plus"
    assert normalized["deep_analysis_model"] == "qwen3-max-2026-01-23"
    assert normalized["backend_url"] == DASHSCOPE_CODING_BASE_URL
    assert normalized["quick_backend_url"] == DASHSCOPE_CODING_BASE_URL
    assert normalized["deep_backend_url"] == DASHSCOPE_CODING_BASE_URL


def test_ensure_dashscope_llm_configs_assigns_canonical_api_bases():
    service = ConfigService()
    configs = [
        LLMConfig(provider=ModelProvider.DASHSCOPE, model_name="qwen3.5-plus", api_base=None),
        LLMConfig(provider=ModelProvider.DASHSCOPE, model_name="qwen-turbo", api_base=None),
    ]

    normalized = service._ensure_dashscope_llm_configs(configs)
    model_to_base = {config.model_name: config.api_base for config in normalized}

    assert model_to_base["qwen-turbo"] == DASHSCOPE_COMPATIBLE_BASE_URL
    assert model_to_base["qwen-max"] == DASHSCOPE_COMPATIBLE_BASE_URL
    assert model_to_base["qwen3.5-plus"] == DASHSCOPE_CODING_BASE_URL
    assert model_to_base["qwen3-max-2026-01-23"] == DASHSCOPE_CODING_BASE_URL
    assert get_dashscope_base_url_for_model("qwen3-max-2026-01-23") == DASHSCOPE_CODING_BASE_URL
