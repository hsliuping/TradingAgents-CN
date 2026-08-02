"""
审慎情景研究员 v2.0

基于ResearcherAgent基类实现的审慎情景研究员
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
    审慎情景研究员 v2.0
    
    功能：
    - 从审慎情景角度综合分析多个报告
    - 提炼风险因素、脆弱点与判断边界
    - 生成审慎情景研究报告
    
    工作流程：
    1. 读取市场报告、新闻报告、基本面报告等
    2. 从审慎情景角度综合分析
    3. 生成审慎情景研究报告
    
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
        name="审慎情景研究员 v2.0",
        description="基于现有材料构建偏审慎的研究论证，提炼风险、脆弱点与判断边界",
        category=AgentCategory.RESEARCHER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 研究员不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False, source="state", state_field="market_report", producer_hint="market_analyst_v2"),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False, source="state", state_field="news_report", producer_hint="news_analyst_v2"),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False, source="state", state_field="fundamentals_report", producer_hint="fundamentals_analyst_v2"),
        ],
        outputs=[
            AgentOutput(name="bear_report", type="string", description="审慎情景研究报告"),
        ],
        requires_tools=False,
        output_field="bear_report",
        report_label="【审慎情景研究 v2】",
        workflow_stage="research",
        growth_role="reviewer",
        growth_outputs=["bear_report"],
        memory_scope_hint="pattern",
        review_level="manual_required",
        growth_source_type="analysis_report",
        maturity_level="stable",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["assistant", "workflow", "agent"],
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
            logger.info(f"✅ 从模板系统获取审慎情景研究员提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：使用与当前模板语义一致的默认提示词
        company_name = (state or {}).get("company_name") or (state or {}).get("ticker") or "目标公司"
        ticker = (state or {}).get("ticker") or ""
        market_name = (state or {}).get("market_name") or "当前市场"
        currency_name = (state or {}).get("currency_name") or "报告原始货币"
        currency_symbol = (state or {}).get("currency_symbol") or ""
        company_reference = f"{company_name}（股票代码：{ticker}）" if ticker else company_name
        currency_display = f"{currency_name}（{currency_symbol}）" if currency_symbol else currency_name

        return f"""你是一位审慎情景研究员，负责基于现有材料为 {company_reference} 构建偏审慎的研究论证。

    ⚠️ 当前分析市场：{market_name}。若材料中包含价格、估值或财务数值，请统一使用 {currency_display} 作为单位。
    ⚠️ 行文时请优先使用公司名称“{company_name}”，不要只用股票代码“{ticker}”指代公司。

    你的任务是：
    1. 说明哪些证据削弱当前判断或支持更谨慎的结论。
    2. 突出风险和挑战、竞争劣势与负面指标，但前提是材料中确有依据。
    3. 回应偏乐观观点中最关键的论据，指出其证据短板、前提漏洞或尚未验证之处。
    4. 结合辩论历史与过往反思，说明哪些判断容易失真，以及当前应如何收窄结论边界。
    5. 用普通用户看得懂的语言输出，不故作玄虚。

    严格禁止：
    - 不得输出买卖、加减仓、配置价值、目标价、价格区间、关键价位。
    - 不得输出下跌空间、最大回撤、概率数值、风险收益比。
    - 不得把审慎情景写成执行方案。
    - 不得使用模型内部知识、训练数据或材料外信息补足未提供内容。
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
            logger.info(f"✅ 从模板系统获取审慎情景研究员用户提示词 (长度: {len(prompt)})")
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
                    logger.info(f"✅ 从模板系统获取审慎情景研究员用户提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ 从模板系统获取用户提示词失败: {e}，使用降级提示词")

        # 降级：使用与当前模板语义一致的硬编码提示词
        market_name = state.get("market_name", "当前市场") if state else "当前市场"
        currency_name = state.get("currency_name", "报告原始货币") if state else "报告原始货币"
        currency_symbol = state.get("currency_symbol", "") if state else ""
        currency_display = f"{currency_name}（{currency_symbol}）" if currency_symbol else currency_name

        prompt = """请基于提供的分析报告，为 {company_name}（股票代码：{ticker}）构建偏审慎的研究论证。

    当前分析市场：{market_name}
    如材料中包含价格、估值或财务数值，请统一使用 {currency_display} 作为单位。
    行文时请优先使用公司名称“{company_name}”，不要只用股票代码“{ticker}”指代公司。

    可用资源：
    - 所有分析师报告（含市场/基本面/新闻/情绪/大盘/板块等）：
    {analyst_reports}
    - 辩论对话历史：{historical_context}
    - 最新偏乐观论点：{current_response}
    - 类似情况的反思和经验教训：{past_memory_str}

    请使用 Markdown 输出，并优先包含以下标题：
    ## 核心主张
    ## 主要担忧
    ## 对乐观观点的回应
    ## 判断转弱前提

    要求：
    - 如本轮存在新增且可验证的公开信号，再补充“## 后续观察信号”；如果本轮没有新的观察信号，可以省略该标题，或直接说明“本轮暂无新增观察信号”。
    - 每个关键论据必须在句末用【】标注来源。
    - 如果报告中缺少某项数据，必须明确写“报告中未提供此数据”或“基于现有报告，无法判断...”。
    - 直接回应偏乐观论点，不要只重复己方观点。
    - 若历史反思与当前案例相关，要吸收其中的经验教训；不相关则不要硬套。
    - 多轮多情景研究时，优先输出本轮新增或最值得回应的 1-2 个点；若新增证据有限，可明确写“核心判断延续，暂无新增高质量风险证据或前提修正”，不要为凑结构重复扩写。
    - 只能使用分析日期 {analysis_date} 之前且材料中明确提供的信息，不要引用“去年”“上季度”或模型记忆中的时间信息。
    - 严格禁止输出目标价、价格区间、关键价位、下跌空间、概率数值和任何交易建议。
    - 严格禁止使用模型内部知识、训练数据或材料外信息补足未提供内容。
    """

        # 聚合所有分析师报告
        try:
            from core.workflow.stage_aggregator import aggregate_stage_reports
            analyst_reports_text = aggregate_stage_reports(state or {}, "analyst")
        except Exception:
            analyst_reports_text = ""

        # 替换变量（使用聚合报告 + 保留个别字段兼容）
        prompt = prompt.format(
            company_name=company_name,
            ticker=ticker,
            market_name=market_name,
            currency_display=currency_display,
            analysis_date=analysis_date,
            analyst_reports=analyst_reports_text or "\n".join([
                f"- 市场研究报告：{reports.get('market_report', '')}",
                f"- 社交媒体情绪报告：{reports.get('sentiment_report', '')}",
                f"- 最新世界事务新闻：{reports.get('news_report', '')}",
                f"- 公司基本面报告：{reports.get('fundamentals_report', '')}",
            ]),
            historical_context=historical_context or (state.get("history", "") if state else ""),
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

