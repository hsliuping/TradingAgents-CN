"""
看跌研究员 v2.0

基于ResearcherAgent基类实现的看跌研究员
"""

import logging
from typing import Dict, Any, List

from core.agents.researcher import ResearcherAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt, get_user_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None
    get_user_prompt = None

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class BearResearcherV2(ResearcherAgent):
    """
    看跌研究员 v2.0
    
    功能：
    - 从看跌角度综合分析多个报告
    - 找出所有风险因素和看跌理由
    - 生成看跌观点报告
    
    工作流程：
    1. 读取市场报告、新闻报告、基本面报告等
    2. 从看跌角度综合分析
    3. 生成看跌观点报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("bear_researcher_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "market_report": "...",
            "news_report": "...",
            "fundamentals_report": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="bear_researcher_v2",
        name="看跌研究员 v2.0",
        description="从看跌角度综合分析多个报告，找出风险因素和看跌理由",
        category=AgentCategory.RESEARCHER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 研究员不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False),
        ],
        outputs=[
            AgentOutput(name="bear_report", type="string", description="看跌观点报告"),
        ],
        requires_tools=False,
        output_field="bear_report",
        report_label="【看跌观点 v2】",
    )

    # 研究员类型
    researcher_type = "bear"

    # 立场
    stance = "bear"

    # 输出字段名
    output_field = "bear_report"

    # 辩论配置
    debate_state_field = "investment_debate_state"
    history_field = "bear_history"
    opponent_history_field = "bull_history"

    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 立场（bull/bear）
            state: 工作流状态（可选，用于提取变量如 company_name, ticker 等）
            
        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        logger.info("🔍 [BearResearcherV2] 开始构建系统提示词")
        
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        template_variables = {}
        if state:
            # 提取 ticker 和 company_name
            if "ticker" in state:
                template_variables["ticker"] = state["ticker"]
            if "company_name" in state:
                template_variables["company_name"] = state["company_name"]
            # 提取日期
            if "analysis_date" in state or "trade_date" in state:
                analysis_date = state.get("analysis_date") or state.get("trade_date")
                if analysis_date:
                    # 确保日期格式正确
                    if isinstance(analysis_date, str) and len(analysis_date) > 10:
                        analysis_date = analysis_date.split()[0]
                    template_variables["current_date"] = analysis_date
                    template_variables["analysis_date"] = analysis_date
        
        prompt = self._get_prompt_from_template(
            agent_type="researchers_v2",
            agent_name="bear_researcher_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量（current_price, industry 等）
            context=state.get("context") if state else None,  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取看跌研究员提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：使用旧版的默认提示词（与数据库模板保持一致）
        return """你是一位看跌分析师，负责论证不投资股票 {company_name}（股票代码：{ticker}）的理由。

⚠️ 重要提醒：当前分析的是 {market_name}，所有价格和估值请使用 {currency_name}（{currency_symbol}）作为单位。
⚠️ 在你的分析中，请始终使用公司名称"{company_name}"而不是股票代码"{ticker}"来称呼这家公司。

你的目标是提出合理的论证，强调风险、挑战和负面指标。利用提供的研究和数据来突出潜在的不利因素并有效反驳看涨论点。
"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（从模板系统获取）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            reports: 各类分析报告
            historical_context: 历史上下文
            state: 当前状态

        Returns:
            用户提示词
        """
        company_name = self._get_company_name(ticker, state)

        # 准备模板变量
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
        }

        # 添加所有报告到模板变量
        for key, value in reports.items():
            template_variables[key] = str(value) if value else ""

        # 添加历史上下文
        if historical_context:
            template_variables["historical_context"] = historical_context

        # 🔑 从 state 中提取系统变量并合并到 template_variables
        if state:
            system_vars = [
                "current_price", "industry", "market_name",
                "currency_name", "currency_symbol", "current_date", "start_date"
            ]
            for var in system_vars:
                if var in state and var not in template_variables:
                    template_variables[var] = state[var]
                    logger.debug(f"📊 [系统变量] 合并到模板变量 {var}: {state[var]}")
            
            # 也添加其他可能有用的 state 字段（如果不存在于 template_variables 中）
            # 但排除一些内部字段
            exclude_fields = {"context", "messages", "prompt_overrides", "skip_cache"}
            for key, value in state.items():
                if key not in template_variables and key not in exclude_fields:
                    # 只添加简单类型（字符串、数字、布尔值），避免复杂对象
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        template_variables[key] = value

        # 使用基类的通用方法从模板系统获取用户提示词（统一使用 _get_prompt_from_template）
        prompt = self._get_prompt_from_template(
            agent_type="researchers_v2",
            agent_name="bear_researcher_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量（作为备用）
            context=state.get("context") if state else None,  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取看跌研究员用户提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：如果模板系统不可用，使用旧方式
        if get_user_prompt:
            try:
                preference_id = state.get("preference_id", "neutral") if state else "neutral"

                prompt = get_user_prompt(
                    agent_type="researchers_v2",
                    agent_name="bear_researcher_v2",
                    variables=template_variables,
                    preference_id=preference_id,
                    fallback_prompt=None,
                    context=state
                )

                if prompt:
                    logger.info(f"✅ 从模板系统获取看跌研究员用户提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ 从模板系统获取用户提示词失败: {e}，使用降级提示词")

        # 降级：使用旧版的硬编码提示词（与数据库模板保持一致）
        prompt = """基于提供的分析报告进行深度分析。
可用资源：
- 市场研究报告：{market_research_report}
- 社交媒体情绪报告：{sentiment_report}
- 最新世界事务新闻：{news_report}
- 公司基本面报告：{fundamentals_report}
- 辩论对话历史：{history}
- 最后的看涨论点：{current_response}
- 类似情况的反思和经验教训：{past_memory_str}
"""

        # 替换变量（使用实际的报告内容）
        prompt = prompt.format(
            market_research_report=reports.get("market_report", ""),
            sentiment_report=reports.get("sentiment_report", ""),
            news_report=reports.get("news_report", ""),
            fundamentals_report=reports.get("fundamentals_report", ""),
            history=state.get("history", "") if state else "",
            current_response=state.get("current_response", "") if state else "",
            past_memory_str=state.get("past_memory_str", "") if state else ""
        )

        return prompt

    def _get_required_reports(self) -> List[str]:
        """
        获取需要的报告列表
        
        Returns:
            报告字段名列表
        """
        return [
            "market_report",        # 市场分析报告
            "news_report",          # 新闻分析报告
            "fundamentals_report",  # 基本面分析报告
            "sentiment_report",     # 社媒分析报告（市场情绪）
            "sector_report",        # 板块分析报告（行业分析）
            "index_report",         # 大盘分析报告
        ]

    def _get_company_name(self, ticker: str, state: Dict[str, Any]) -> str:
        """获取公司名称"""
        # 优先从state获取
        if "company_name" in state:
            return state["company_name"]
        
        # 使用StockUtils获取
        if StockUtils:
            try:
                market_info = StockUtils.get_market_info(ticker)
                if market_info.get('is_china'):
                    from tradingagents.dataflows.interface import get_china_stock_info_unified
                    stock_info = get_china_stock_info_unified(ticker)
                    if "股票名称:" in stock_info:
                        return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            except Exception as e:
                logger.debug(f"获取公司名称失败: {e}")
        
        return f"股票{ticker}"

