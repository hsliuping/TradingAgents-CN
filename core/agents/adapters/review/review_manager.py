"""
复盘总结师智能体

综合所有分析维度，生成完整复盘报告和改进建议
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class ReviewManagerAgent(BaseAgent):
    """
    复盘总结师智能体
    
    综合所有分析结果，包括:
    - 整合时机、仓位、情绪、归因分析
    - 给出总体评分
    - 识别优点和不足
    - 提出改进建议
    """
    
    metadata = BUILTIN_AGENTS["review_manager"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "ReviewManagerAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行复盘总结
        
        Args:
            state: 包含以下键的状态字典:
                - trade_info: 交易信息
                - timing_analysis: 时机分析结果
                - position_analysis: 仓位分析结果
                - emotion_analysis: 情绪分析结果
                - attribution_analysis: 归因分析结果
                
        Returns:
            更新后的状态，包含:
                - review_summary: 复盘总结报告
                - overall_score: 总体评分
                - strengths: 优点列表
                - weaknesses: 不足列表
                - suggestions: 改进建议列表
        """
        trade_info = state.get("trade_info", {})
        timing_analysis = state.get("timing_analysis", "无时机分析")
        position_analysis = state.get("position_analysis", "无仓位分析")
        emotion_analysis = state.get("emotion_analysis", "无情绪分析")
        attribution_analysis = state.get("attribution_analysis", "无归因分析")

        logger.info(f"📝 [复盘总结师] 开始生成复盘报告...")
        logger.info(f"   📋 股票: {trade_info.get('code', 'N/A')}")
        logger.info(f"   📊 已收集分析:")
        logger.info(f"      - 时机分析: {len(timing_analysis)}字符")
        logger.info(f"      - 仓位分析: {len(position_analysis)}字符")
        logger.info(f"      - 情绪分析: {len(emotion_analysis)}字符")
        logger.info(f"      - 归因分析: {len(attribution_analysis)}字符")

        # 构建提示词（支持用户偏好）
        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(
            trade_info, timing_analysis, position_analysis,
            emotion_analysis, attribution_analysis, user_id, preference_id
        )
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 生成总结...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
            except Exception as e:
                logger.error(f"   ❌ [复盘总结师] LLM调用失败: {e}")
                analysis = f"复盘总结失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行复盘总结"

        logger.info(f"📝 [复盘总结师] ✅ 报告生成完成")

        # 只返回新增的字段
        return {
            "review_summary": analysis,
        }
    
    def _build_prompt(
        self,
        trade_info: Dict,
        timing_analysis: str,
        position_analysis: str,
        emotion_analysis: str,
        attribution_analysis: str,
        user_id: str = None,
        preference_id: str = "neutral"
    ) -> str:
        """构建复盘总结提示词"""

        # 准备模板变量
        template_variables = {
            "ticker": trade_info.get('code', 'N/A'),
            "trade_period": f"{trade_info.get('holding_period', 0)}天",
            "total_return": trade_info.get('return_rate', 0),
            "total_pnl": trade_info.get('pnl', 0),
            "timing_analysis": timing_analysis,
            "position_analysis": position_analysis,
            "emotion_analysis": emotion_analysis,
            "attribution_analysis": attribution_analysis
        }

        # 硬编码的降级提示词
        fallback_prompt = f"""你是一位资深的交易复盘专家。请综合以下各维度分析，生成完整的复盘报告:

## 交易概况
- 股票: {trade_info.get('code', 'N/A')} {trade_info.get('name', '')}
- 持仓周期: {trade_info.get('holding_period', 0)}天
- 实际收益率: {trade_info.get('return_rate', 0):.2%}
- 实际盈亏: {trade_info.get('pnl', 0):.2f}元

## 时机分析
{timing_analysis}

## 仓位分析
{position_analysis}

## 情绪分析
{emotion_analysis}

## 归因分析
{attribution_analysis}

## 输出要求
请生成一份结构化的复盘报告，**必须以JSON格式输出**：

```json
{{
  "overall_score": 75,
  "timing_score": 80,
  "position_score": 70,
  "discipline_score": 75,
  "summary": "2-3句话概括这笔交易的整体表现",
  "strengths": [
    "做得好的地方1",
    "做得好的地方2",
    "做得好的地方3"
  ],
  "weaknesses": [
    "需要改进的地方1",
    "需要改进的地方2",
    "需要改进的地方3"
  ],
  "suggestions": [
    "具体可执行的改进建议1",
    "具体可执行的改进建议2",
    "具体可执行的改进建议3"
  ],
  "lesson": "本次交易的关键教训"
}}
```

评分说明:
- overall_score: 总分 (1-100)
- timing_score: 时机选择评分 (1-100)
- position_score: 仓位管理评分 (1-100)
- discipline_score: 纪律执行评分 (1-100)

请确保输出是有效的JSON格式，用```json和```包裹。"""

        # 尝试从模板系统获取提示词
        try:
            from tradingagents.utils.template_client import get_agent_prompt

            prompt = get_agent_prompt(
                agent_type="reviewers",
                agent_name="review_manager",
                variables=template_variables,
                user_id=user_id,
                preference_id=preference_id,
                fallback_prompt=fallback_prompt,
                context=None
            )
            logger.info(f"✅ [复盘总结师] 成功从模板系统获取提示词 (长度: {len(prompt)})")
            return prompt

        except Exception as e:
            logger.warning(f"⚠️ [复盘总结师] 模板系统获取失败，使用降级提示词: {e}")
            return fallback_prompt

