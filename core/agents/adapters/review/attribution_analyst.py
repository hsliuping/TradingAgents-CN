"""
归因分析师智能体

分析收益来源，区分大盘/行业/个股Alpha贡献
"""

import logging
from typing import Any, Dict, Optional

from ...base import BaseAgent
from ...config import AgentConfig, BUILTIN_AGENTS
from ...registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class AttributionAnalystAgent(BaseAgent):
    """
    归因分析师智能体
    
    分析收益归因，包括:
    - Beta收益 (大盘贡献)
    - 行业超额收益
    - 个股Alpha (选股能力)
    - 择时贡献
    """
    
    metadata = BUILTIN_AGENTS["attribution_analyst"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
    
    def set_dependencies(self, llm: Any, toolkit: Any = None) -> "AttributionAnalystAgent":
        """设置依赖项"""
        self._llm = llm
        return self
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行归因分析
        
        Args:
            state: 包含以下键的状态字典:
                - trade_info: 交易信息
                - benchmark_data: 基准数据 (大盘、行业指数)
                
        Returns:
            更新后的状态，包含:
                - attribution_analysis: 归因分析报告
        """
        trade_info = state.get("trade_info", {})
        benchmark_data = state.get("benchmark_data", {})

        logger.info(f"📈 [归因分析师] 开始分析收益归因...")
        logger.info(f"   📋 股票: {trade_info.get('code', 'N/A')}, 收益率: {trade_info.get('return_rate', 0):.2%}")
        logger.info(f"   📊 基准: 大盘={benchmark_data.get('market_return', 0):.2%}, 行业={benchmark_data.get('industry_name', 'N/A')}")

        # 构建提示词（支持用户偏好）
        user_id = state.get("user_id")
        preference_id = state.get("preference_id", "neutral")
        prompt = self._build_prompt(trade_info, benchmark_data, user_id, preference_id)
        logger.info(f"   📝 提示词长度: {len(prompt)} 字符")

        if self._llm:
            try:
                logger.info(f"   🤖 调用 LLM 分析...")
                response = self._llm.invoke(prompt)
                analysis = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"   ✅ LLM 返回成功，响应长度: {len(analysis)} 字符")
                logger.info(f"   📄 LLM 返回内容: {analysis[:100]}..." if len(analysis) > 100 else f"   📄 LLM 返回内容: {analysis}")
            except Exception as e:
                logger.error(f"   ❌ [归因分析师] LLM调用失败: {e}")
                analysis = f"归因分析失败: {str(e)}"
        else:
            logger.warning(f"   ⚠️ LLM未配置")
            analysis = "LLM未配置，无法进行归因分析"

        logger.info(f"📈 [归因分析师] ✅ 分析完成")

        # 只返回新增的字段，不返回整个 state（避免并发更新冲突）
        return {
            "attribution_analysis": analysis,
        }
    
    def _build_prompt(self, trade_info: Dict, benchmark_data: Dict, user_id: str = None, preference_id: str = "neutral") -> str:
        """构建归因分析提示词"""
        # 提取基准数据
        market_return = benchmark_data.get("market_return", 0)
        industry_return = benchmark_data.get("industry_return", 0)
        industry_name = benchmark_data.get("industry_name", "未知行业")

        # 计算超额收益
        stock_return = trade_info.get("return_rate", 0)

        # 准备模板变量
        template_variables = {
            "stock_return": stock_return,
            "market_return": market_return,
            "industry_name": industry_name,
            "industry_return": industry_return,
            "market_excess": stock_return - market_return,
            "industry_excess": stock_return - industry_return,
            "holding_period": trade_info.get('holding_period', 0),
            "avg_buy_price": trade_info.get('avg_buy_price', 0),
            "avg_sell_price": trade_info.get('avg_sell_price', 0)
        }

        # 硬编码的降级提示词
        fallback_prompt = f"""你是一位专业的收益归因分析师。请分析以下交易的收益来源:

## 收益数据
- 个股收益率: {stock_return:.2%}
- 同期大盘收益: {market_return:.2%}
- 所属行业: {industry_name}
- 同期行业收益: {industry_return:.2%}

## 超额收益计算
- 相对大盘超额: {(stock_return - market_return):.2%}
- 相对行业超额: {(stock_return - industry_return):.2%}

## 交易信息
- 持仓周期: {trade_info.get('holding_period', 0)}天
- 买入均价: {trade_info.get('avg_buy_price', 0):.2f}
- 卖出均价: {trade_info.get('avg_sell_price', 0):.2f}

## 分析要求
请从以下角度进行收益归因:
1. **Beta收益分析**: 大盘贡献了多少收益？
2. **行业贡献分析**: 行业因素贡献了多少？
3. **个股Alpha分析**: 选股能力贡献了多少？
4. **择时贡献分析**: 买卖时机选择贡献了多少？
5. **归因评分**: 给出1-100的投资能力评分

请量化各因素贡献，用简洁专业的语言回答。"""

        # 尝试从模板系统获取提示词
        try:
            from tradingagents.utils.template_client import get_agent_prompt

            prompt = get_agent_prompt(
                agent_type="reviewers",
                agent_name="attribution_analyst",
                variables=template_variables,
                user_id=user_id,
                preference_id=preference_id,
                fallback_prompt=fallback_prompt,
                context=None
            )
            logger.info(f"✅ [归因分析师] 成功从模板系统获取提示词 (长度: {len(prompt)})")
            return prompt

        except Exception as e:
            logger.warning(f"⚠️ [归因分析师] 模板系统获取失败，使用降级提示词: {e}")
            return fallback_prompt

