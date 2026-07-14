"""
测试 research_manager 的「量化评分缺失」哨兵 + 动态检测逻辑

背景（2026-06-14）：
- 600926 报告（standard 模式）不含「数据质量验证 & 量化评分」段
- 但旧提示词硬编码"基本面报告末尾附带了量化评分表格"
- 诱导 LLM 幻觉编造 PE/PB "较高" 评分 + "PE可能失真" 警告
- 导致 final_trade_decision 做出与真实数据方向相反的"立即卖出"决策

修复：
- 动态扫描 fundamentals_report 是否含评分段关键字
- 含 → 附加评分指引
- 不含 → 注入缺失哨兵 + 禁止 LLM 臆造 + 强制引用具体数字
"""
import pytest
from unittest.mock import MagicMock


def _make_state(fundamentals_report: str) -> dict:
    """构造一个最小的 research_manager state"""
    return {
        "company_of_interest": "600926",
        "market_report": "市场报告：MACD 空头排列，RSI 29.47 超卖",
        "sentiment_report": "情绪报告：散户情绪恐慌",
        "news_report": "新闻报告：央行降准 0.5%",
        "fundamentals_report": fundamentals_report,
        "investment_debate_state": {
            "history": "看跌: 行业资金流出\n看涨: PE 破净低估",
            "count": 2,
        },
    }


def _make_llm(prompt_capture: dict) -> MagicMock:
    """构造一个会捕获 prompt 的 mock LLM"""
    mock = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "## 投资计划：买入"
    mock.invoke = MagicMock(side_effect=lambda p: (prompt_capture.update(prompt=p), mock_response)[1])
    return mock


# 600926 真实报告（standard 模式）—— 不含「量化评分」段
FUNDAMENTALS_STANDARD = """# 杭州银行（600926）基本面分析报告

## 一、公司基本信息
- 股票代码: 600926
- 公司名称: 杭州银行

## 二、核心估值指标
- 市盈率(PE): 5.80倍
- 市净率(PB): 0.81倍（破净低估）
- ROE: 数据待补充
"""

# comprehensive 模式报告—— 含「量化评分」段
FUNDAMENTALS_COMPREHENSIVE = """# 杭州银行（600926）基本面分析报告（全面版）

## 二、核心估值指标
- 市盈率(PE): 5.80倍
- 市净率(PB): 0.81倍

## 🔍 数据质量验证 & 量化评分（辅助参考）

### 📊 量化评分总计（0-100）
| 维度 | 得分 | 说明 |
|------|:---:|------|
| **总分** | **72** | 建议: 买入 |
| PE估值 | 85 | PE=5.80 远低于行业平均 6~8，估值极具吸引力 |
| PB估值 | 80 | PB=0.81 破净，安全边际充足 |
"""


@pytest.fixture
def research_manager_factory():
    """从 research_manager 模块动态构建 manager，避开重型 import"""
    from tradingagents.agents.managers.research_manager import create_research_manager
    return create_research_manager


class TestQuantScoringSentinel:
    """量化评分哨兵 + 动态检测 + 估值铁律测试"""

    def test_standard_report_injects_missing_sentinel(self, research_manager_factory):
        """standard 模式报告不含评分表 → 必须注入缺失哨兵"""
        state = _make_state(FUNDAMENTALS_STANDARD)
        prompt_capture = {}
        llm = _make_llm(prompt_capture)

        node = research_manager_factory(llm, memory=None)
        node(state)

        prompt = prompt_capture["prompt"]

        # 1. 必须含缺失哨兵
        assert "未包含量化评分表" in prompt, \
            "未注入缺失哨兵（standard 模式无评分表时）"
        # 2. 必须显式禁止捏造
        assert "严禁凭空捏造" in prompt, \
            "未禁止 LLM 捏造 PE/PB 评分"
        # 3. 必须禁止"PE 失真"等警告
        assert "「PE 失真」" in prompt or "PE 失真" in prompt, \
            "未禁止 LLM 捏造 PE 失真警告"
        # 4. 必须强制引用具体数字
        assert "PE=X.XX" in prompt and "PB=X.XX" in prompt, \
            "未要求 LLM 引用具体数字"

    def test_comprehensive_report_uses_quant_guidance(self, research_manager_factory):
        """comprehensive 模式报告含评分表 → 必须含评分指引，不含缺失哨兵"""
        state = _make_state(FUNDAMENTALS_COMPREHENSIVE)
        prompt_capture = {}
        llm = _make_llm(prompt_capture)

        node = research_manager_factory(llm, memory=None)
        node(state)

        prompt = prompt_capture["prompt"]

        # 1. 必须含评分指引
        assert "数据质量验证 & 量化评分" in prompt, \
            "未附加评分指引"
        # 2. 不应含缺失哨兵
        assert "未包含量化评分表" not in prompt, \
            "错误注入了缺失哨兵（实际报告含评分表）"
        # 3. 不应含"严禁凭空捏造"
        assert "严禁凭空捏造" not in prompt, \
            "错误地禁止了 LLM 引用评分（实际报告含评分）"

    def test_no_pe_distortion_warning_in_hardcoded_prompt(self, research_manager_factory):
        """提示词里不再硬编码"PE可能失真"作为示例"""
        state = _make_state(FUNDAMENTALS_STANDARD)
        prompt_capture = {}
        llm = _make_llm(prompt_capture)

        node = research_manager_factory(llm, memory=None)
        node(state)

        prompt = prompt_capture["prompt"]

        # 旧提示词硬编码的"PE可能失真"示例不应再出现
        # （除非报告真的有该警告，否则 LLM 会被诱导幻觉）
        assert '如"PE可能失真"' not in prompt, \
            "提示词仍硬编码 'PE可能失真' 示例，会诱导 LLM 幻觉"

    def test_explicit_no_inversion_rule(self, research_manager_factory):
        """必须显式禁止把"低估"反向写成"较高"或"高估"——这是 600926 案例核心"""
        state = _make_state(FUNDAMENTALS_STANDARD)
        prompt_capture = {}
        llm = _make_llm(prompt_capture)

        node = research_manager_factory(llm, memory=None)
        node(state)

        prompt = prompt_capture["prompt"]

        # 必须含方向防反规则
        assert "低估" in prompt and "较高" in prompt and "高估" in prompt, \
            "未显式声明'禁止把低估反向写成较高/高估'铁律"
        assert "反向" in prompt, \
            "未使用'反向'关键词提示 LLM"

    def test_prompt_includes_fundamentals_report_full_text(self, research_manager_factory):
        """提示词必须把 fundamentals_report 完整传入（防 LLM 看不到原文就臆造）"""
        state = _make_state(FUNDAMENTALS_STANDARD)
        prompt_capture = {}
        llm = _make_llm(prompt_capture)

        node = research_manager_factory(llm, memory=None)
        node(state)

        prompt = prompt_capture["prompt"]

        # 报告原文关键数字必须出现在 prompt
        assert "5.80" in prompt, "PE 实际数字 5.80 未传入 prompt"
        assert "0.81" in prompt, "PB 实际数字 0.81 未传入 prompt"
        assert "600926" in prompt, "股票代码未传入 prompt"
