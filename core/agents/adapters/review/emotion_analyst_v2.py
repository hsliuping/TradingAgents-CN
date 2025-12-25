"""
情绪分析师 v2.0 (复盘分析)

基于ResearcherAgent基类实现的情绪分析师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier
from ...registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None


@register_agent
class EmotionAnalystV2(ResearcherAgent):
    """
    情绪分析师 v2.0 (复盘分析)
    
    功能：
    - 分析交易中的情绪化操作
    - 评估交易纪律执行情况
    - 识别追涨杀跌行为
    
    工作流程：
    1. 读取交易信息和市场数据
    2. 使用LLM分析情绪控制
    3. 生成情绪分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("emotion_analyst_v2", llm)

        result = agent.execute({
            "trade_info": {...},
            "market_data": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="emotion_analyst_v2",
        name="情绪分析师 v2.0",
        description="分析交易中的情绪化操作和纪律执行情况",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    researcher_type = "review_emotion"
    stance = "neutral"
    output_field = "emotion_analysis"

    def _build_system_prompt(self, stance: str) -> str:
        """构建系统提示词"""
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="reviewers_v2",
                    agent_name="emotion_analyst_v2",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取情绪分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        return """您是一位专业的情绪分析师。

您的职责是分析交易中的情绪控制和纪律执行。

分析要点：
1. 追涨杀跌 - 是否存在追涨杀跌行为
2. 恐慌抛售 - 是否因恐慌而抛售
3. 贪婪持有 - 是否因贪婪而过度持有
4. 交易纪律 - 交易纪律执行情况
5. 情绪评分 - 1-10分的情绪控制评分

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """构建用户提示词"""
        trade_info = state.get("trade_info", {})
        market_data = state.get("market_data", {})
        code = trade_info.get("code", ticker)
        trades = trade_info.get("trades", [])
        
        # 分析交易行为模式
        trade_patterns = []
        for t in trades:
            price_change = t.get("price_change_before", 0)
            pattern = "上涨中" if price_change > 0 else "下跌中" if price_change < 0 else "震荡中"
            trade_patterns.append(
                f"- {t.get('date', 'N/A')}: {t.get('side', 'N/A')} "
                f"(交易前市场{pattern}, 变化{price_change:.2%})"
            )
        pattern_str = "\n".join(trade_patterns) if trade_patterns else "无法分析交易模式"
        
        # 格式化收益信息
        realized_pnl = trade_info.get('realized_pnl', 0)
        realized_pnl_pct = trade_info.get('realized_pnl_pct', 0)
        pnl_sign = "+" if realized_pnl >= 0 else ""

        return f"""请分析以下交易的情绪控制：

=== 交易信息 ===
- 股票代码: {code}
- 交易次数: {len(trades)} 次（{len([t for t in trades if t.get('side') == 'buy'])} 次买入，{len([t for t in trades if t.get('side') == 'sell'])} 次卖出）
- 最终收益: {pnl_sign}{realized_pnl:.2f}元（{pnl_sign}{realized_pnl_pct:.2f}%）
- 持仓周期: {trade_info.get('first_buy_date', 'N/A')} 至 {trade_info.get('last_sell_date', 'N/A')}（共约 {trade_info.get('holding_days', 0)} 天）

=== 交易行为模式 ===
{pattern_str}

=== 市场环境 ===
{market_data.get('summary', '无市场数据')}

请撰写详细的情绪分析报告，包括：
1. 追涨杀跌行为识别
2. 恐慌抛售分析
3. 贪婪持有分析
4. 交易纪律评估
5. 情绪控制评分（1-10分）"""

    def _get_required_reports(self) -> List[str]:
        """获取需要的数据列表"""
        return ["trade_info", "market_data"]

