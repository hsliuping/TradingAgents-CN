"""
测试真实导出数据样本的脱敏功能。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.database.backups import _sanitize_document


def _load_export_sample() -> dict:
    """优先读取仓库现有导出样本；不存在时使用内置最小样本。"""
    project_root = Path(__file__).resolve().parent.parent
    candidate_paths = [
        project_root / "install" / "database_export_config.json",
        project_root / "install" / "database_export_config_2025-11-13.json",
        project_root / "install" / "database_export_config_2025-10-25.json",
    ]

    for path in candidate_paths:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and "data" in payload:
                return payload

    return {
        "export_info": {"source": "generated-test-sample"},
        "data": {
            "system_configs": [
                {
                    "llm_configs": [
                        {"provider": "openai", "api_key": "sk-test-secret"},
                        {"provider": "dashscope", "api_key": "dashscope-secret"},
                    ],
                    "system_settings": {
                        "finnhub_api_key": "finnhub-secret",
                        "tushare_token": "tushare-secret",
                        "reddit_client_secret": "reddit-secret",
                    },
                }
            ],
            "llm_providers": [
                {"name": "openai", "api_key": "provider-secret"},
                {"name": "dashscope", "api_key": "provider-secret-2"},
            ],
            "users": [{"username": "demo"}],
        },
    }


def test_sanitize_real_export_file(tmp_path: Path):
    """测试对真实导出结构的脱敏。"""
    export_data = _load_export_sample()

    sanitized_data = _sanitize_document(export_data["data"])

    for config in sanitized_data.get("system_configs", []):
        for llm_config in config.get("llm_configs", []):
            assert llm_config.get("api_key") == ""

        system_settings = config.get("system_settings", {})
        for key in ["finnhub_api_key", "tushare_token", "reddit_client_secret"]:
            if key in system_settings:
                assert system_settings[key] == ""

    for provider in sanitized_data.get("llm_providers", []):
        assert provider.get("api_key") == ""

    sanitized_export = {
        "export_info": export_data.get("export_info", {}),
        "data": sanitized_data,
    }

    output_path = tmp_path / "database_export_config_sanitized.json"
    output_path.write_text(
        json.dumps(sanitized_export, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["data"] == sanitized_data
