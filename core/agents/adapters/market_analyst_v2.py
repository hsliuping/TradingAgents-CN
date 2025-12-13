"""
市场分析师智能体 v2.0

使用插件化架构的市场分析师实现
- 动态工具绑定
- LangChain 集成
- 使用 BaseAgent 标准化工具调用循环处理
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from ..base import BaseAgent
from ..config import BUILTIN_AGENTS, AgentMetadata, AgentCategory, LicenseTier
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class MarketAnalystAgentV2(BaseAgent):
    """
    市场分析师智能体 v2.0

    特性:
    - 使用 LangChain LLM
    - 动态工具绑定（从配置或数据库加载）
    - 支持工具调用

    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent_with_dynamic_tools

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent_with_dynamic_tools("market_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        })
    """

    # 创建 v2 专用的元数据（使用不同的 ID）
    metadata = AgentMetadata(
        id="market_analyst_v2",
        name="市场分析师 v2.0",
        description="分析市场数据、价格走势和技术指标（插件化架构版本）",
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_market_data_unified"],
        version="2.0.0"
    )
    
    def __init__(
        self,
        config: Optional[Any] = None,
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[list] = None
    ):
        """
        初始化市场分析师
        
        Args:
            config: Agent 配置（可选）
            llm: LangChain LLM 实例
            tool_ids: 工具 ID 列表（可选，如果不提供则从配置加载）
        """
        super().__init__(config=config, llm=llm, tool_ids=tool_ids)
        
        # 如果没有提供 tool_ids，从配置加载
        if tool_ids is None and llm is not None:
            tool_ids = self.load_tools_from_config()
            if tool_ids:
                self._load_tools_v2(tool_ids)
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行市场分析（使用 BaseAgent 标准化工具调用循环）

        Args:
            state: 包含以下键的状态字典:
                - ticker: 股票代码
                - start_date: 开始日期
                - end_date: 结束日期
                - messages: 消息历史（可选）

        Returns:
            更新后的状态，包含:
                - market_analysis: 市场分析结果
                - messages: 更新的消息历史
        """
        ticker = state.get("ticker") or state.get("company_of_interest")
        start_date = state.get("start_date") or state.get("trade_date")
        end_date = state.get("end_date") or state.get("trade_date")

        if not ticker:
            raise ValueError("缺少必需参数: ticker 或 company_of_interest")

        logger.info(f"开始市场分析: {ticker} ({start_date} - {end_date})")

        # 构建消息
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(ticker, start_date, end_date)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # 使用 BaseAgent 标准化的工具调用方法
        if self._llm and self.tools:
            analysis_prompt = self._build_analysis_prompt(ticker)
            analysis = self.invoke_with_tools(messages, analysis_prompt)
        else:
            # 降级：没有 LLM 或工具
            logger.warning("没有配置 LLM 或工具，返回模拟结果")
            analysis = self._generate_mock_report(ticker, start_date, end_date)

        # 更新状态
        state["market_analysis"] = analysis
        state["market_report"] = analysis  # 兼容旧版字段名

        # 🔧 返回清洁消息，不包含 tool_calls（防止死循环）
        clean_message = AIMessage(content=analysis)
        if "messages" not in state:
            state["messages"] = []
        state["messages"].append(clean_message)

        logger.info(f"✅ 市场分析完成，报告长度: {len(analysis)} 字符")

        return state

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一位专业的市场分析师。
你的任务是分析股票的市场数据、价格走势和技术指标。

请使用提供的工具获取市场数据，然后进行分析。

分析应包括:
1. 价格走势分析
2. 技术指标解读
3. 成交量分析
4. 支撑位和阻力位
5. 短期和中期趋势判断

重要：完成分析后，请直接输出完整的分析报告，不要再次调用工具。
"""

    def _build_user_prompt(self, ticker: str, start_date: str, end_date: str) -> str:
        """构建用户提示词"""
        return f"""请分析股票 {ticker} 的市场数据。

分析时间范围: {start_date} 至 {end_date}

请先使用工具获取市场数据，然后提供详细的技术分析报告。
"""

    def _build_analysis_prompt(self, ticker: str) -> str:
        """构建分析报告生成提示词（工具调用后使用）"""
        return f"""根据以上工具返回的数据，请生成 {ticker} 的完整市场分析报告。

报告应包括:
1. 价格走势分析
2. 技术指标解读（MA、MACD、RSI等）
3. 成交量分析
4. 支撑位和阻力位
5. 短期和中期趋势判断
6. 投资建议

请直接输出分析报告，不要再调用工具。
"""

    def _generate_mock_report(self, ticker: str, start_date: str, end_date: str) -> str:
        """生成模拟报告（用于测试或降级）"""
        return f"""这是一个模拟的市场分析报告。

股票代码: {ticker}
分析期间: {start_date} 至 {end_date}

价格走势：上涨
技术指标：看涨
建议：持有"""

