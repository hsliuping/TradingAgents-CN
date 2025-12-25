"""
归因分析师 v2.0 (复盘分析)

基于ResearcherAgent基类实现的归因分析师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier
from ...registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt, get_user_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None
    get_user_prompt = None


@register_agent
class AttributionAnalystV2(ResearcherAgent):
    """
    归因分析师 v2.0 (复盘分析)
    
    功能：
    - 分析收益来源
    - 区分大盘/行业/个股Alpha贡献
    - 评估择时能力
    
    工作流程：
    1. 读取交易信息和基准数据
    2. 使用LLM分析收益归因
    3. 生成归因分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("attribution_analyst_v2", llm)

        result = agent.execute({
            "trade_info": {...},
            "benchmark_data": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="attribution_analyst_v2",
        name="归因分析师 v2.0",
        description="分析收益来源，区分大盘/行业/个股Alpha贡献",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    researcher_type = "review_attribution"
    stance = "neutral"
    output_field = "attribution_analysis"

    def _build_system_prompt(self, stance: str) -> str:
        """构建系统提示词"""
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="reviewers_v2",
                    agent_name="attribution_analyst_v2",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取归因分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        return """您是一位专业的归因分析师。

您的职责是分析收益的来源构成。

分析要点：
1. Beta收益 - 大盘贡献的收益
2. 行业超额 - 行业相对大盘的超额收益
3. 个股Alpha - 选股能力带来的超额收益
4. 择时贡献 - 买卖时机选择的贡献
5. 归因评分 - 1-10分的收益质量评分

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """构建用户提示词（从模板系统获取并渲染）"""
        trade_info = state.get("trade_info", {})
        benchmark_data = state.get("benchmark_data", {})

        code = trade_info.get("code", ticker)
        name = trade_info.get("name", code)
        # 使用正确的字段名：realized_pnl_pct 而不是 return_rate
        stock_return = trade_info.get("realized_pnl_pct", 0) / 100  # 转换为小数
        market_return = benchmark_data.get("market_return", 0)
        industry_return = benchmark_data.get("industry_return", 0)
        industry_name = benchmark_data.get("industry_name", "未知行业")

        # 计算超额收益
        market_excess = stock_return - market_return
        industry_excess = industry_return - market_return
        stock_alpha = stock_return - industry_return

        # 准备模板变量
        template_variables = {
            'code': code,
            'name': name,
            'stock_return': f"{stock_return * 100:.2f}",
            'holding_days': trade_info.get('holding_days', 0),
            'market_return': f"{market_return * 100:.2f}",
            'industry_name': industry_name,
            'industry_return': f"{industry_return * 100:.2f}",
            'market_excess': f"{market_excess * 100:.2f}",
            'industry_excess': f"{industry_excess * 100:.2f}",
            'stock_alpha': f"{stock_alpha * 100:.2f}"
        }

        # 降级提示词（如果模板系统不可用）
        fallback_prompt = f"""请分析以下交易的收益归因：

=== 交易信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 股票收益率: {stock_return:.2%}
- 持仓周期: {trade_info.get('holding_days', 0)}天

=== 基准数据 ===
- 大盘收益率: {market_return:.2%}
- 行业: {industry_name}
- 行业收益率: {industry_return:.2%}

=== 超额收益分解 ===
- 相对大盘超额: {market_excess:.2%}
- 行业超额收益: {industry_excess:.2%}
- 个股Alpha: {stock_alpha:.2%}

请撰写详细的归因分析报告，包括：
1. Beta收益分析（大盘贡献）
2. 行业超额收益分析
3. 个股Alpha分析（选股能力）
4. 择时贡献分析
5. 收益质量评分（1-10分）"""

        # 尝试从模板系统获取用户提示词
        if get_user_prompt:
            try:
                prompt = get_user_prompt(
                    agent_type="reviewers_v2",
                    agent_name="attribution_analyst_v2",
                    variables=template_variables,
                    preference_id="neutral",
                    fallback_prompt=fallback_prompt
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取归因分析师用户提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取用户提示词失败: {e}")

        # 降级：使用硬编码提示词
        return fallback_prompt

    def _get_required_reports(self) -> List[str]:
        """获取需要的数据列表"""
        return ["trade_info", "benchmark_data"]

