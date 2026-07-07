"""财经专家顾问模块

当 helper 返回 no_data 时，用 LLM 作为资深金融从业者判断：
1. 该股票没有这类数据是否业务合理（如银行股无质押是合理的）
2. 如果不合理，推荐更合适的测试股票
3. 给出专家建议，反馈给 Skill 生成管道

适用场景：
- 质押分析 helper 返回 no_data：银行股/白马股可能无质押（合理），民营股无质押可能不合理
- 财务分析 helper 返回 no_data：次新股可能无年报（合理），老股无年报不合理
- 新闻分析 helper 返回 no_data：冷门股可能无新闻（半合理），热点股无新闻不合理
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.llm import UnifiedLLMClient

logger = logging.getLogger(__name__)


@dataclass
class ExpertJudgment:
    """财经专家对 no_data 的判断结果"""

    is_rational: bool = True  # no_data 是否业务合理
    reasoning: str = ""  # 判断理由
    recommended_stocks: List[Dict[str, str]] = field(default_factory=list)  # 推荐的更合适测试股票
    advice: str = ""  # 给 LLM 的建议（注入 feedback）
    confidence: float = 0.0  # 判断置信度 0-1

    def to_feedback_text(self) -> str:
        """转换为可注入 feedback 的文本"""
        lines = []
        lines.append("【财经专家判断 — no_data 合理性分析】")
        lines.append(f"判断结果: {'合理（该股票本应无此类数据）' if self.is_rational else '不合理（该股票本应有此类数据）'}")
        if self.reasoning:
            lines.append(f"判断理由: {self.reasoning}")
        if self.recommended_stocks:
            lines.append("推荐换股重试（这些股票更可能有数据）:")
            for stock in self.recommended_stocks[:3]:
                code = stock.get("code", "")
                name = stock.get("name", "")
                reason = stock.get("reason", "")
                lines.append(f"  - {code} {name}: {reason}")
        if self.advice:
            lines.append(f"专家建议: {self.advice}")
        return "\n".join(lines)


class FinancialExpertAdvisor:
    """财经专家顾问：用 LLM 判断 no_data 是否业务合理 + 推荐更合适的测试股票"""

    # A 股常见有质押数据的股票池（民营企业、高质押率典型）
    # 用于 LLM 推荐时的参考，避免 LLM 凭空捏造
    _PLEDGE_LIKELY_STOCKS = [
        {"code": "000651", "name": "格力电器", "industry": "家电", "reason": "大股东有质押历史，数据完整"},
        {"code": "002594", "name": "比亚迪", "industry": "汽车", "reason": "质押记录丰富（400+ 条）"},
        {"code": "300750", "name": "宁德时代", "industry": "新能源", "reason": "有质押记录，数据规范"},
        {"code": "600276", "name": "恒瑞医药", "industry": "医药", "reason": "白马股，质押较少但可能有"},
        {"code": "600519", "name": "贵州茅台", "industry": "白酒", "reason": "蓝筹股，大股东通常不质押"},
    ]

    # 各类 Skill 推荐的测试股票通用池（有完整财务数据、有新闻、有质押等）
    _GENERAL_TEST_STOCKS = [
        {"code": "000651", "name": "格力电器", "industry": "家电", "reason": "数据完整，财务规范，有质押"},
        {"code": "600519", "name": "贵州茅台", "industry": "白酒", "reason": "蓝筹龙头，财报完整，新闻丰富"},
        {"code": "002594", "name": "比亚迪", "industry": "汽车", "reason": "热点股，数据齐全"},
        {"code": "300750", "name": "宁德时代", "industry": "新能源", "reason": "创业板龙头，数据规范"},
        {"code": "600036", "name": "招商银行", "industry": "银行", "reason": "金融蓝筹，财报完整"},
    ]

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
    ):
        self._llm_client = llm_client
        self._provider = provider
        self._model = model

    def _get_client(self) -> UnifiedLLMClient:
        if self._llm_client is None:
            kwargs = {}
            if self._model:
                kwargs["model"] = self._model
            self._llm_client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
        return self._llm_client

    def judge_no_data_rationality(
        self,
        stock_symbol: str,
        stock_name: str,
        industry: str,
        skill_purpose: str,
        data_type: str,
        helper_name: str,
        helper_warnings: List[str],
        skill_category: str = "",
    ) -> ExpertJudgment:
        """
        判断 helper 返回 no_data 是否业务合理

        Args:
            stock_symbol: 测试股票代码（如 "000001"）
            stock_name: 测试股票名称（如 "平安银行"）
            industry: 股票所属行业（如 "银行"）
            skill_purpose: Skill 的功能描述（如 "股权质押风险画像与趋势分析"）
            data_type: 数据类型描述（如 "质押数据"、"年报财务数据"）
            helper_name: helper 函数名（如 "get_pledge_risk_profile"）
            helper_warnings: helper 返回的 warnings 列表
            skill_category: Skill 类别（如 "fundamentals"）

        Returns:
            ExpertJudgment: 专家判断结果
        """
        try:
            client = self._get_client()
            prompt = self._build_judgment_prompt(
                stock_symbol=stock_symbol,
                stock_name=stock_name,
                industry=industry,
                skill_purpose=skill_purpose,
                data_type=data_type,
                helper_name=helper_name,
                helper_warnings=helper_warnings,
                skill_category=skill_category,
            )

            from core.llm import Message

            response = client.chat([Message(role="user", content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)
            return self._parse_judgment(raw, stock_symbol, data_type)
        except Exception as e:
            logger.warning(f"⚠️ 财经专家判断失败，降级为默认合理: {e}")
            # 降级：默认认为 no_data 是合理的，避免误判
            return ExpertJudgment(
                is_rational=True,
                reasoning=f"专家判断失败（{e}），默认认为 no_data 业务合理",
                recommended_stocks=[],
                advice="请人工确认 no_data 是否合理",
                confidence=0.0,
            )

    def _build_judgment_prompt(
        self,
        stock_symbol: str,
        stock_name: str,
        industry: str,
        skill_purpose: str,
        data_type: str,
        helper_name: str,
        helper_warnings: List[str],
        skill_category: str,
    ) -> str:
        """构建财经专家判断 prompt"""
        # 根据数据类型提供参考股票池
        reference_pool = ""
        if "质押" in data_type or "pledge" in helper_name.lower():
            reference_pool = "\n".join(
                f"  - {s['code']} {s['name']}（{s['industry']}）: {s['reason']}"
                for s in self._PLEDGE_LIKELY_STOCKS
            )
        else:
            reference_pool = "\n".join(
                f"  - {s['code']} {s['name']}（{s['industry']}）: {s['reason']}"
                for s in self._GENERAL_TEST_STOCKS
            )

        warnings_text = "\n".join(f"  - {w}" for w in helper_warnings) if helper_warnings else "  (无)"

        return f"""你是一位资深 A 股金融分析师，擅长判断金融数据的业务合理性。

## 背景
我们正在生成一个 Skill 工具：{skill_purpose}
测试股票：{stock_symbol} {stock_name}（行业：{industry}）
调用的标准 helper 函数：{helper_name}
helper 返回状态：no_data（无数据）
helper 返回的警告：
{warnings_text}

## 你的任务
判断"{stock_name}（{stock_symbol}）没有{data_type}"是否业务合理。

## 判断要点
1. **行业特性**：银行股通常无质押（监管限制），民营制造股通常有质押
2. **公司性质**：央企/国企蓝筹通常质押少，民营中小企业通常质押多
3. **数据类型特性**：
   - 质押数据：银行/保险/白酒龙头可能无质押（合理），民营制造业应有质押
   - 年报财务：上市超过 1 年的公司应有年报，次新股可能无年报（合理）
   - 新闻数据：热点股应有新闻，冷门股可能无新闻（半合理）
   - 技术指标：所有上市股票都应有技术指标数据（无数据=不合理）
4. **不要假设数据源失效**：先假设数据源正常，判断 no_data 是否业务合理

## 输出格式（严格 JSON）
```json
{{
  "is_rational": true或false,
  "reasoning": "判断理由（用金融从业者视角，结合行业和公司特性）",
  "recommended_stocks": [
    {{"code": "股票代码", "name": "股票名称", "reason": "推荐理由（为什么这只股票更可能有数据）"}}
  ],
  "advice": "给 Skill 生成 LLM 的建议（如：建议换股重试 / no_data 是业务正确结果应返回 success / 检查数据源权限等）",
  "confidence": 0.0到1.0
}}
```

## 参考股票池（A 股常见有数据股票）
{reference_pool}

## 重要约束
- recommended_stocks 最多 3 个，必须从参考股票池中选择
- 如果 is_rational=true（no_data 业务合理），advice 应建议"返回 success + 标注无数据"
- 如果 is_rational=false（no_data 不合理），advice 应建议"换股重试"
- confidence 反映你对判断的把握程度

请只输出纯 JSON，不要任何其他文字。"""


    def _parse_judgment(self, raw: str, original_symbol: str, data_type: str) -> ExpertJudgment:
        """解析 LLM 返回的 JSON 判断"""
        # 提取 JSON
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            logger.warning(f"⚠️ 财经专家返回非 JSON: {raw[:200]}")
            return ExpertJudgment(
                is_rational=True,
                reasoning="专家返回格式异常，默认认为 no_data 业务合理",
                confidence=0.0,
            )

        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ 财经专家 JSON 解析失败: {e}")
            return ExpertJudgment(
                is_rational=True,
                reasoning="专家 JSON 解析失败，默认认为 no_data 业务合理",
                confidence=0.0,
            )

        # 解析推荐股票
        recommended = []
        for stock in data.get("recommended_stocks", [])[:3]:
            if isinstance(stock, dict) and stock.get("code"):
                recommended.append(
                    {
                        "code": str(stock.get("code", "")).strip(),
                        "name": str(stock.get("name", "")).strip(),
                        "reason": str(stock.get("reason", "")).strip(),
                    }
                )

        return ExpertJudgment(
            is_rational=bool(data.get("is_rational", True)),
            reasoning=str(data.get("reasoning", "")),
            recommended_stocks=recommended,
            advice=str(data.get("advice", "")),
            confidence=float(data.get("confidence", 0.0)),
        )


# 全局单例
_expert_advisor: Optional[FinancialExpertAdvisor] = None


def get_financial_expert_advisor(
    llm_client: Optional[UnifiedLLMClient] = None,
    provider: str = "deepseek",
    model: Optional[str] = None,
) -> FinancialExpertAdvisor:
    """获取财经专家顾问全局实例"""
    global _expert_advisor
    if _expert_advisor is None or llm_client is not None:
        _expert_advisor = FinancialExpertAdvisor(
            llm_client=llm_client, provider=provider, model=model
        )
    return _expert_advisor
