"""
基本面分析师智能体

分析财务数据、估值水平、行业地位，评估基本面价值
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class FundamentalAnalystAgent(BaseAgent):
    """
    基本面分析师智能体
    
    分析持仓股票的基本面，包括:
    - 财务数据分析
    - 估值水平评估
    - 行业地位分析
    - 成长性判断
    """
    
    metadata = BUILTIN_AGENTS["pa_fundamental"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "FundamentalAnalystAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行基本面分析"""
        logger.info(f"📊 [基本面分析师] 开始分析...")

        position_info = state.get("position_info", {})
        stock_report = state.get("stock_analysis_report", {})

        logger.info(f"   📋 股票: {position_info.get('code', 'N/A')}")

        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(position_info, stock_report, user_id, preference_id)
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
            except Exception as e:
                logger.error(f"   ❌ LLM调用失败: {e}")
                analysis = f"基本面分析失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行基本面分析"

        logger.info(f"📊 [基本面分析师] ✅ 分析完成")
        return {"fundamental_analysis": analysis}
    
    def _build_prompt(self, position_info: Dict, stock_report: Dict,
                      user_id: str = None, preference_id: str = "neutral") -> str:
        """构建基本面分析提示词"""
        reports = stock_report.get("reports", {})
        fundamentals_report = reports.get("fundamentals_report", "暂无基本面报告")[:2000]
        
        template_variables = {
            "code": position_info.get("code", "N/A"),
            "name": position_info.get("name", "N/A"),
            "current_price": position_info.get("current_price", 0),
            "cost_price": position_info.get("cost_price", 0),
            "industry": position_info.get("industry", "未知"),
            "fundamentals_report": fundamentals_report,
        }

        fallback_prompt = f"""你是一位专业的基本面分析师。请分析以下持仓股票的基本面:

## 持仓信息
- 股票代码: {position_info.get('code', 'N/A')}
- 股票名称: {position_info.get('name', 'N/A')}
- 所属行业: {position_info.get('industry', '未知')}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}

## 基本面报告
{fundamentals_report}

## 分析要求
1. **财务状况**: 营收、利润、现金流分析
2. **估值水平**: PE/PB/PEG等估值指标
3. **行业地位**: 竞争优势和市场份额
4. **成长性**: 未来增长潜力
5. **基本面评分**: 1-10分的基本面评分

请用简洁专业的语言回答。"""

        try:
            from tradingagents.utils.template_client import get_agent_prompt
            prompt = get_agent_prompt(
                agent_type="position_analysis",
                agent_name="pa_fundamental",
                variables=template_variables,
                user_id=user_id,
                preference_id=preference_id,
                fallback_prompt=fallback_prompt,
                context=None
            )
            logger.info(f"✅ [基本面分析师] 成功从模板系统获取提示词")
            return prompt
        except Exception as e:
            logger.warning(f"⚠️ [基本面分析师] 模板系统获取失败: {e}")
            return fallback_prompt

