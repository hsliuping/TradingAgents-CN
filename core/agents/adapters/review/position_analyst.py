"""
仓位分析师智能体

分析仓位控制和加减仓策略的合理性
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class PositionAnalystAgent(BaseAgent):
    """
    仓位分析师智能体
    
    分析仓位管理，包括:
    - 初始仓位是否合理
    - 加减仓时机和比例
    - 仓位与风险的匹配度
    - 资金利用效率
    """
    
    metadata = BUILTIN_AGENTS["position_analyst"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "PositionAnalystAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行仓位分析
        
        Args:
            state: 包含以下键的状态字典:
                - trade_info: 交易信息
                - position_history: 仓位变化历史
                
        Returns:
            更新后的状态，包含:
                - position_analysis: 仓位分析报告
        """
        trade_info = state.get("trade_info", {})

        logger.info(f"📊 [仓位分析师] 开始分析仓位管理...")
        logger.info(f"   📋 股票: {trade_info.get('code', 'N/A')}, 交易次数: {len(trade_info.get('trades', []))}")

        # 构建提示词（支持用户偏好）
        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(trade_info, user_id, preference_id)
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
                logger.info(f"   📄 LLM 返回内容: {analysis[:100]}..." if len(analysis) > 100 else f"   📄 LLM 返回内容: {analysis}")
            except Exception as e:
                logger.error(f"   ❌ [仓位分析师] LLM调用失败: {e}")
                analysis = f"仓位分析失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行仓位分析"

        logger.info(f"📊 [仓位分析师] ✅ 分析完成")

        # 只返回新增的字段，不返回整个 state（避免并发更新冲突）
        return {
            "position_analysis": analysis,
        }
    
    def _build_prompt(self, trade_info: Dict, user_id: str = None, preference_id: str = "neutral") -> str:
        """构建仓位分析提示词"""
        trades = trade_info.get("trades", [])

        # 分析仓位变化
        position_changes = []
        current_position = 0
        for t in trades:
            side = t.get("side", "")
            qty = t.get("quantity", 0)
            if side == "buy":
                current_position += qty
            else:
                current_position -= qty
            position_changes.append(
                f"- {t.get('date', 'N/A')}: {side} {qty}股, 当前持仓: {current_position}股"
            )

        position_str = "\n".join(position_changes) if position_changes else "无仓位变化记录"

        # 准备模板变量
        template_variables = {
            "position_str": position_str,
            "total_buy_quantity": trade_info.get('total_buy_quantity', 0),
            "total_sell_quantity": trade_info.get('total_sell_quantity', 0),
            "total_cost": trade_info.get('total_cost', 0),
            "pnl": trade_info.get('pnl', 0)
        }

        # 硬编码的降级提示词
        fallback_prompt = f"""你是一位专业的仓位管理分析师。请分析以下交易的仓位控制:

## 仓位变化记录
{position_str}

## 交易统计
- 总买入数量: {trade_info.get('total_buy_quantity', 0)}股
- 总卖出数量: {trade_info.get('total_sell_quantity', 0)}股
- 总投入资金: {trade_info.get('total_cost', 0):.2f}元
- 实际盈亏: {trade_info.get('pnl', 0):.2f}元

## 分析要求
请从以下角度分析仓位管理:
1. **初始建仓评估**: 首次建仓比例是否合理？
2. **加仓策略评估**: 加仓时机和比例是否恰当？是否越跌越买？
3. **减仓策略评估**: 减仓时机和比例是否合理？是否过早/过晚？
4. **风险控制评估**: 最大仓位是否过重？是否设置止损？
5. **仓位评分**: 给出1-100的仓位管理评分

请用简洁专业的语言回答。"""

        prompt = self._get_prompt_from_template(
            agent_type="reviewers",
            agent_name="position_analyst",
            variables=template_variables,
            context={"user_id": user_id, "preference_id": preference_id},
            fallback_prompt=fallback_prompt
        )
        if prompt:
            logger.info(f"✅ [仓位分析师] 成功从模板系统获取提示词 (长度: {len(prompt)})")
            return prompt
        logger.warning(f"⚠️ [仓位分析师] 模板系统未返回提示词，使用降级提示词")
        return fallback_prompt

