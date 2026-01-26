"""
市场分析师Agent v2.0

基于AnalystAgent基类实现的市场分析师
使用配置驱动的方式，支持动态工具绑定
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from ..analyst import AnalystAgent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入工具函数
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class MarketAnalystV2(AnalystAgent):
    """
    市场分析师 v2.0

    功能：
    - 分析股票的价格走势
    - 分析技术指标
    - 分析成交量
    - 生成市场分析报告

    工作流程：
    1. 调用工具获取价格数据、技术指标、成交量数据
    2. 使用LLM分析数据
    3. 生成市场分析报告

    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent_with_dynamic_tools

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent_with_dynamic_tools("market_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="market_analyst_v2",
        name="市场分析师 v2.0",
        description="分析股票的价格走势、技术指标和成交量，生成市场分析报告",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[
            "get_stock_price",
            "get_technical_indicators",
            "get_volume_data"
        ],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="market_report", type="string", description="市场分析报告"),
        ],
        requires_tools=True,
        output_field="market_report",
        report_label="【市场分析 v2】",
    )

    # 分析师类型
    analyst_type = "market"

    # 输出字段名
    output_field = "market_report"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        覆盖执行逻辑以支持模板调试与提示词覆盖
        """
        try:
            ticker = state.get("ticker") or state.get("company_of_interest")
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            market_type = state.get("market_type", "A股")
            context = state.get("context")
            overrides = state.get("prompt_overrides") or {}
            system_override = overrides.get("system")
            user_override = overrides.get("user")
            analysis_override = overrides.get("analysis")

            if not ticker or not analysis_date:
                raise ValueError("Missing required parameters: ticker or analysis_date")

            system_prompt = system_override
            if not system_prompt:
                # 🔑 从 state 中提取必要的变量（系统变量应该在工作流创建时已经准备好）
                template_variables = {}
                
                # 基础变量
                if "ticker" in state:
                    template_variables["ticker"] = state["ticker"]
                else:
                    template_variables["ticker"] = ticker
                
                # 日期相关
                if "analysis_date" in state or "trade_date" in state:
                    analysis_date = state.get("analysis_date") or state.get("trade_date")
                    if analysis_date:
                        if isinstance(analysis_date, str) and len(analysis_date) > 10:
                            analysis_date = analysis_date.split()[0]
                        template_variables["current_date"] = analysis_date
                        template_variables["analysis_date"] = analysis_date
                else:
                    current_date = state.get("current_date", analysis_date)
                    template_variables["current_date"] = current_date
                    template_variables["analysis_date"] = analysis_date
                    template_variables["start_date"] = state.get("start_date", current_date)
                
                # 公司信息（从 state 中获取，工作流引擎应该已经准备好）
                template_variables["company_name"] = state.get("company_name", "")
                template_variables["market_name"] = state.get("market_name", market_type)
                template_variables["currency_name"] = state.get("currency_name", "人民币")
                template_variables["currency_symbol"] = state.get("currency_symbol", "¥")
                template_variables["tool_names"] = ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
                
                system_prompt = self._get_prompt_from_template(
                    agent_type="analysts_v2",
                    agent_name="market_analyst_v2",
                    variables=template_variables,  # 传递必要的变量
                    state=state,  # 🔑 传递 state，基类会自动提取系统变量
                    context=context,
                    fallback_prompt=None,
                    prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
                )

            if not system_prompt:
                # 🔑 传递 state 给 _build_system_prompt，以便从 state 中提取变量完善模板
                system_prompt = self._build_system_prompt(market_type, context=context, state=state)

            user_prompt = user_override
            if not user_prompt:
                user_prompt = self._build_user_prompt(ticker, analysis_date, state)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")            

            if self._llm:
                if self._langchain_tools:
                    report = self.invoke_with_tools(messages, analysis_prompt=analysis_override)
                else:
                    response = self._llm.invoke(messages)
                    report = response.content if hasattr(response, 'content') else str(response)
            else:
                raise ValueError("LLM not initialized")

            return {self.output_field: report}

        except Exception as e:
            logger.error(f"[{self.agent_id}] 执行失败: {e}", exc_info=True)
            return {self.output_field: f"执行失败: {str(e)}"}

    def _build_system_prompt(self, market_type: str = None, context=None, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）

        Args:
            market_type: 市场类型（A股/港股/美股）（保留以兼容基类）
            context: AgentContext 对象（用于调试模式）
            state: 工作流状态（用于提取模板变量）
            
        Returns:
            系统提示词
        """
        logger.info("🔍 [MarketAnalystV2] 开始构建系统提示词")
        
        if state is None:
            state = {}
        
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        # 注意：虽然系统提示词通常不需要变量，但某些模板可能需要 ticker、current_date 等
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        template_variables = {}
        
        # 如果 state 中有 ticker 和 analysis_date，提取它们（系统提示词模板可能需要）
        if "ticker" in state:
            template_variables["ticker"] = state["ticker"]
        if "analysis_date" in state or "trade_date" in state:
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            if analysis_date:
                # 确保日期格式正确
                if isinstance(analysis_date, str) and len(analysis_date) > 10:
                    analysis_date = analysis_date.split()[0]
                template_variables["current_date"] = analysis_date
                template_variables["analysis_date"] = analysis_date
        
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="market_analyst_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=context or state.get("context"),  # 优先使用传入的 context，否则从 state 获取
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )

        if prompt:
            return prompt

        # 默认提示词
        return f"""你是一位专业的{market_type}市场分析师，擅长技术分析。

你的职责：
1. 分析股票的价格走势（涨跌幅、趋势方向）
2. 分析技术指标（MA、MACD、RSI、KDJ等）
3. 分析成交量（放量、缩量、量价关系）
4. 综合判断市场情绪和趋势

分析要求：
- 客观、专业、基于数据
- 指出关键的技术信号
- 给出明确的趋势判断
- 使用中文输出

输出格式：
请以结构化的方式输出分析报告，包括：
- 价格走势分析
- 技术指标分析
- 成交量分析
- 综合判断
"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 和 fundamentals_analyst_v2 的实现）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            state: 工作流状态（用于提取模板变量）

        Returns:
            用户提示词
        """
        logger.info("🔍 [MarketAnalystV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        market_name = "中国A股"
        company_name = ""
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                company_name = self._get_company_name(ticker, market_info)
                market_name = market_info.get('market_name', "中国A股")
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        else:
            company_name = ticker
            market_name = "未知市场"
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "analysis_date": analysis_date,
            "current_date": analysis_date,
            "start_date": "",  # 可以计算1年前的日期
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
        }
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        # 🔑 注意：工具返回的数据会通过 ToolMessage 传递，不需要在 user_prompt 中检查
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="market_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取市场分析师 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认提示词（不再检查 tool_data，因为工具数据会通过 ToolMessage 传递）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        return f"""请分析 {company_name}（{ticker}）在 {analysis_date} 的市场表现：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}
市场类型：{market_name}

请调用工具获取市场数据，然后生成详细的市场分析报告。"""

    def _get_company_name(self, ticker: str, market_info: dict) -> str:
        """
        获取公司名称

        Args:
            ticker: 股票代码
            market_info: 市场信息

        Returns:
            公司名称
        """
        try:
            if market_info['is_china']:
                from tradingagents.dataflows.interface import get_china_stock_info_unified
                stock_info = get_china_stock_info_unified(ticker)
                if stock_info and "股票名称:" in stock_info:
                    return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            elif market_info['is_hk']:
                from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                return get_hk_company_name_improved(ticker)
            elif market_info['is_us']:
                us_stock_names = {
                    'AAPL': '苹果公司', 'TSLA': '特斯拉', 'NVDA': '英伟达',
                    'MSFT': '微软', 'GOOGL': '谷歌', 'AMZN': '亚马逊',
                }
                return us_stock_names.get(ticker.upper(), f"美股{ticker}")
        except Exception as e:
            logger.warning(f"获取公司名称失败: {e}")

        return f"股票{ticker}"
