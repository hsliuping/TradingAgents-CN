import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_export_templates_include_standard_prompt_footer() -> None:
    templates = json.loads((ROOT / "exports" / "current_db_templates.json").read_text(encoding="utf-8"))

    checked = 0
    for item in templates:
        content = item.get("content")
        if not isinstance(content, dict) or "system_prompt" not in content:
            continue

        checked += 1
        system_prompt = str(content.get("system_prompt") or "")
        assert "请使用中文，基于真实数据进行分析。" in system_prompt
        assert "本分析报告仅供参考，不构成投资建议。" in system_prompt

    assert checked > 0


def test_all_export_templates_have_single_disclaimer_block() -> None:
    templates = json.loads((ROOT / "exports" / "current_db_templates.json").read_text(encoding="utf-8"))

    checked = 0
    for item in templates:
        content = item.get("content")
        if not isinstance(content, dict) or "system_prompt" not in content:
            continue

        checked += 1
        system_prompt = str(content.get("system_prompt") or "")
        assert system_prompt.count("**免责声明**") == 1
        assert system_prompt.count("本分析报告仅供参考，不构成投资建议。") == 1

    assert checked > 0