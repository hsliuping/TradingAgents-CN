"""trader_v2 合规校验管线单元测试。

验证内容：
1. _validate_trader_output 校验逻辑（合规术语扫描 + 结构完整性检查）
2. _build_system_prompt 前置合规约束
3. execute 校验结果显式上报

运行方式：
    env\\Scripts\\python.exe scripts\\test_trader_v2_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def test_validate_passes_with_compliant_output():
    """合规输出（含必备章节、无禁用术语）应校验通过。"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2.__new__(TraderV2)  # 绕过 __init__ 避免依赖 LLM/配置
    text = """## 一句话结论
当前研究判断为审慎，主因估值偏高且景气拐点尚未确认。

## 为什么这么看
- 估值处于历史 80% 分位
- 季度营收增速放缓

## 当前判断的限制
报告未提供同行可比估值，结论边界待验证。

## 后续观察事项
- 下一季度营收增速
- 行业政策变化

## 资料边界说明
同行估值数据缺失。

## 免责声明
本研究简报仅供信息参考，不构成投资建议。
"""
    result = agent._validate_trader_output(text)
    assert result is None, f"预期校验通过，但收到警告: {result}"
    print("✅ test_validate_passes_with_compliant_output 通过")


def test_validate_fails_with_forbidden_terms():
    """包含禁用术语（看涨/买入等）应校验失败并上报。"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2.__new__(TraderV2)
    text = """## 一句话结论
当前看涨，建议买入。

## 核心依据
- 技术面突破
"""
    result = agent._validate_trader_output(text)
    assert result is not None, "预期校验失败（禁用术语），但校验通过"
    assert "看涨" in result, f"警告应包含'看涨'，实际: {result}"
    assert "买入" in result, f"警告应包含'买入'，实际: {result}"
    print("✅ test_validate_fails_with_forbidden_terms 通过")


def test_validate_fails_with_missing_sections():
    """缺少必备章节应校验失败并上报。"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2.__new__(TraderV2)
    text = """这是一份没有按结构输出的简报，缺少必备章节标记。当前判断为审慎。
"""
    result = agent._validate_trader_output(text)
    assert result is not None, "预期校验失败（缺少章节），但校验通过"
    assert "一句话结论" in result, f"警告应包含'一句话结论'，实际: {result}"
    assert "为什么这么看" in result, f"警告应包含'为什么这么看'，实际: {result}"
    print("✅ test_validate_fails_with_missing_sections 通过")


def test_validate_fails_with_empty_output():
    """空输出应校验失败。"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2.__new__(TraderV2)
    assert agent._validate_trader_output("") is not None
    assert agent._validate_trader_output("   ") is not None
    assert agent._validate_trader_output(None) is not None
    print("✅ test_validate_fails_with_empty_output 通过")


def test_validate_passes_with_neutral_terms():
    """使用合规术语（乐观/审慎/中性）应校验通过。"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2.__new__(TraderV2)
    text = """## 一句话结论
当前研究判断为中性，多空因素较为平衡。

## 为什么这么看
- 估值合理
- 景气平稳

## 当前判断的限制
信息缺口待补。

## 后续关注
- 政策落地
"""
    result = agent._validate_trader_output(text)
    assert result is None, f"使用合规术语应校验通过，但收到警告: {result}"
    print("✅ test_validate_passes_with_neutral_terms 通过")


def test_build_system_prompt_prepends_compliance():
    """_build_system_prompt 应在最前面前置合规约束。"""
    from core.agents.adapters.trader_v2 import TRADER_COMPLIANCE_PROMPT, TraderV2

    agent = TraderV2.__new__(TraderV2)
    # 模拟 _get_prompt_from_template 返回 None，走 fallback 路径
    agent._get_prompt_from_template = MagicMock(return_value=None)
    prompt = agent._build_system_prompt(state={})
    assert prompt.startswith(TRADER_COMPLIANCE_PROMPT), (
        "fallback 路径的 system prompt 应以合规约束开头"
    )
    assert "乐观" in prompt and "审慎" in prompt and "中性" in prompt
    print("✅ test_build_system_prompt_prepends_compliance (fallback) 通过")

    # 模拟 _get_prompt_from_template 返回模板，走模板路径
    fake_template = "你是一位研究整合员..."
    agent._get_prompt_from_template = MagicMock(return_value=fake_template)
    prompt = agent._build_system_prompt(state={})
    assert prompt.startswith(TRADER_COMPLIANCE_PROMPT), (
        "模板路径的 system prompt 应以合规约束开头"
    )
    assert prompt == TRADER_COMPLIANCE_PROMPT + fake_template
    print("✅ test_build_system_prompt_prepends_compliance (template) 通过")


def test_execute_reports_validation_status():
    """execute 应显式上报校验状态（passed/failed）。"""
    from core.agents.adapters.trader_v2 import TraderV2

    agent = TraderV2.__new__(TraderV2)
    agent.output_field = "trader_investment_plan"

    # 场景1：父类返回合规输出
    compliant_text = """## 一句话结论
当前审慎。

## 为什么这么看
- 估值偏高
"""
    with patch.object(
        TraderV2.__mro__[1],  # 父类 TraderAgent
        "execute",
        return_value={"trader_investment_plan": {"content": compliant_text, "success": True}},
    ):
        result = agent.execute({})
    assert result["trader_plan_validation_status"] == "passed", (
        f"合规输出应上报 passed，实际: {result.get('trader_plan_validation_status')}"
    )
    print("✅ test_execute_reports_validation_status (passed) 通过")

    # 场景2：父类返回不合规输出（含禁用术语）
    non_compliant_text = "看涨，建议买入。"
    with patch.object(
        TraderV2.__mro__[1],
        "execute",
        return_value={"trader_investment_plan": non_compliant_text},
    ):
        result = agent.execute({})
    assert result["trader_plan_validation_status"] == "failed", (
        f"不合规输出应上报 failed，实际: {result.get('trader_plan_validation_status')}"
    )
    assert "trader_plan_validation_warning" in result, "failed 时应包含 warning 字段"
    assert "看涨" in result["trader_plan_validation_warning"]
    print("✅ test_execute_reports_validation_status (failed) 通过")


def test_forbidden_terms_constant():
    """禁用术语表应包含核心交易指令术语。"""
    from core.agents.adapters.trader_v2 import TRADER_FORBIDDEN_TERMS

    for term in ("看涨", "看跌", "买入", "卖出", "加仓", "减仓", "清仓"):
        assert term in TRADER_FORBIDDEN_TERMS, f"禁用术语表缺少: {term}"
    print("✅ test_forbidden_terms_constant 通过")


if __name__ == "__main__":
    test_forbidden_terms_constant()
    test_validate_passes_with_compliant_output()
    test_validate_fails_with_forbidden_terms()
    test_validate_fails_with_missing_sections()
    test_validate_fails_with_empty_output()
    test_validate_passes_with_neutral_terms()
    test_build_system_prompt_prepends_compliance()
    test_execute_reports_validation_status()
    print("\n🎉 全部测试通过")
