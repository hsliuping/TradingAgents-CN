"""
市场分析师Agent v2.0

基于AnalystAgent基类实现的市场分析师
使用配置驱动的方式，支持动态工具绑定
"""

import logging
from typing import Any, Dict, Optional

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

try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError):
    logger.warning("无法导入get_agent_prompt，将使用默认提示词")
    get_agent_prompt = None


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
            if not system_prompt and get_agent_prompt:
                try:
                    template_variables = {
                        "market_name": market_type,
                        "ticker": ticker,
                        "analysis_date": analysis_date
                    }
                    system_prompt = get_agent_prompt(
                        agent_type="analysts",
                        agent_name="market_analyst",
                        variables=template_variables,
                        preference_id="neutral",
                        fallback_prompt=None,
                        context=context
                    )
                except Exception:
                    system_prompt = None
            if not system_prompt:
                system_prompt = self._build_system_prompt(market_type)

            user_prompt = user_override or self._build_user_prompt(ticker, analysis_date, {}, state)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

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

    def _build_system_prompt(self, market_type: str) -> str:
        """
        构建系统提示词

        Args:
            market_type: 市场类型（A股/港股/美股）

        Returns:
            系统提示词
        """
        # 尝试从模板系统获取
        if get_agent_prompt:
            try:
                template_variables = {
                    "market_name": market_type,
                }

                prompt = get_agent_prompt(
                    agent_type="analysts",
                    agent_name="market_analyst",
                    variables=template_variables,
                    preference_id="neutral",
                    fallback_prompt=None
                )

                if prompt:
                    logger.debug(f"✅ 从模板系统获取市场分析师系统提示词")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ 从模板系统获取提示词失败: {e}，使用默认提示词")

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
        tool_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据
            state: 工作流状态

        Returns:
            用户提示词
        """
        # 获取公司名称和市场信息
        if StockUtils:
            market_info = StockUtils.get_market_info(ticker)
            company_name = self._get_company_name(ticker, market_info)
            market_name = market_info['market_name']
        else:
            company_name = ticker
            market_name = "未知市场"

        # 构建提示词
        prompt = f"""请分析 {company_name}（{ticker}）在 {analysis_date} 的市场表现：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}
市场类型：{market_name}

"""

        # 添加工具数据
        if tool_data:
            prompt += "数据分析：\n"
            for key, value in tool_data.items():
                prompt += f"\n{key}:\n{value}\n"
        else:
            prompt += "注意：未获取到工具数据，请基于历史经验进行分析。\n"

        prompt += "\n请给出详细的市场分析报告。"

        return prompt

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
