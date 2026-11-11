"""种子模板断言：启动注入的系统模板不得包含执行模式（advice_mode=execution）内容。

执行模式提示词属于本地私有资产，只经 scripts/local/import_execution_prompts.py
写入自用机器，永不进入 app/services/system_prompt_seed_service.py 的种子清单。
本测试防止后续误把执行模板塞进发行种子。
"""

from app.services.system_prompt_seed_service import _build_system_prompt_templates

EXECUTION_MARKERS = ("执行模式", "advice_mode")


def test_seed_templates_contain_no_execution_advice_mode():
    templates = _build_system_prompt_templates()
    assert templates, "种子模板清单不应为空"

    for template in templates:
        assert template.get("advice_mode") != "execution", (
            f"种子模板 {template.get('agent_type')}/{template.get('agent_name')} "
            "不得标记为 execution"
        )


def test_seed_templates_contain_no_execution_prompt_text():
    for template in _build_system_prompt_templates():
        content = template.get("content") or {}
        blob = "\n".join(str(content.get(key) or "") for key in content)
        for marker in EXECUTION_MARKERS:
            assert marker not in blob, (
                f"种子模板 {template.get('agent_type')}/{template.get('agent_name')} "
                f"疑似混入执行模式内容（命中标记：{marker}）"
            )
