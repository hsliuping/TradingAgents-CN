"""
看跌研究员 v2.0

基于ResearcherAgent基类实现的看跌研究员
"""

import logging
from typing import Dict, Any, List

from core.agents.researcher import ResearcherAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent
from core.agents.utils.weight_calculator import calculate_report_weights, format_weighted_reports_prompt

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
        
        # 降级：使用默认提示词
        return """您是一位专业的看跌研究员。

**⚠️ 重要约束**：
- **必须严格基于用户提示词中提供的实时分析报告进行分析**（包括市场分析、基本面分析、新闻分析、板块分析、大盘分析等）
- **禁止使用LLM内部知识或历史数据进行分析**（如2023年、2024年的数据）
- **如果报告中缺少某些数据，请明确说明"报告中未提供此数据"，不要编造或使用内部知识**
- **所有分析结论必须基于提供的报告内容，不得自行补充或假设数据**

您的职责是从谨慎和风险控制的角度，综合分析用户提示词中提供的各类报告，识别潜在风险。

分析要点：
1. 识别所有潜在的风险因素（基于报告内容）
2. 分析可能导致股价下跌的因素（基于报告内容）
3. 评估估值是否过高（基于报告中的估值数据）
4. 识别市场情绪是否过度乐观（基于报告中的情绪分析）
5. 提供风险提示和谨慎建议

请使用中文，保持客观和专业。**严格基于提供的报告内容进行分析**。"""

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

        # 🆕 计算报告权重
        trading_style = state.get("trading_style")  # 从state获取交易风格（如果有）
        weights = calculate_report_weights(reports, trading_style)

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

        # 降级：使用硬编码提示词
        prompt = f"""请从看跌角度综合分析以下报告，对股票 {ticker}（{company_name}）进行风险评估：

=== 分析日期 ===
{analysis_date}

"""

        # 🆕 使用权重格式化报告
        if weights:
            # 报告标签映射
            report_labels = {
                "market_report": "市场分析（技术分析）",
                "news_report": "新闻分析",
                "sentiment_report": "社媒分析（市场情绪）",
                "fundamentals_report": "基本面分析",
                "sector_report": "板块分析（行业分析）",
                "index_report": "大盘分析",
            }

            weighted_reports_text = format_weighted_reports_prompt(reports, weights, report_labels)
            prompt += weighted_reports_text
        else:
            # 如果没有权重信息，使用原来的方式（向后兼容）
            reports_text = ""
            for report_name, report_content in reports.items():
                if report_content:
                    reports_text += f"\n=== {report_name} ===\n{report_content}\n"
            prompt += f"=== 各类分析报告 ===\n{reports_text}"

        # 添加历史上下文
        if historical_context:
            prompt += f"\n=== 历史上下文 ===\n{historical_context}\n"

        # 添加可用报告说明（如果还没有）
        if "可用分析报告" not in prompt and "📊 可用分析报告" not in prompt:
            prompt += """
        
**📊 可用分析报告**：
以下报告已提供，请基于这些报告进行分析：
- **市场分析报告** (`market_report`): 技术分析、价格走势、成交量等
- **基本面分析报告** (`fundamentals_report`): 财务数据、估值指标、盈利能力等
- **新闻分析报告** (`news_report`): 最新新闻事件、市场动态等
- **社媒分析报告** (`sentiment_report`): 市场情绪、社交媒体讨论等
- **板块分析报告** (`sector_report`): 行业分析、板块表现等
- **大盘分析报告** (`index_report`): 大盘走势、市场环境等
**📈 当前股价**: {current_price} {currency_symbol}（系统实时获取）
**注意**：如果某个报告为空或未提供，请明确说明"该报告未提供"，不要使用内部知识补充。
"""
        
        prompt += """
        
请撰写详细的看跌观点报告（必须基于上述报告内容），包括：
1. 主要风险因素识别（基于报告内容）
2. 可能导致下跌的催化剂（基于报告内容）
3. 估值风险评估（基于报告中的估值数据）
4. 市场情绪风险（基于报告中的情绪分析）
5. 投资风险提示"""

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

