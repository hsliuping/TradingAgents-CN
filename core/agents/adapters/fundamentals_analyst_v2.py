"""
基本面分析师智能体 v2.0

基于 BaseAgent 的插件化架构实现
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseAgent
from ..config import AgentConfig, AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法

# 导入股票工具类
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    StockUtils = None

logger = logging.getLogger(__name__)


@register_agent
class FundamentalsAnalystAgentV2(BaseAgent):
    """
    基本面分析师智能体 v2.0

    特性:
    - 使用 LangChain LLM
    - 动态工具绑定（从配置或数据库加载）
    - 支持工具调用

    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent_with_dynamic_tools

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent_with_dynamic_tools("fundamentals_analyst_v2", llm)

        result = agent.execute({
            "ticker": "000001.SZ",
            "trade_date": "2024-12-01"
        })
    """

    # 创建 v2 专用的元数据（使用不同的 ID）
    metadata = AgentMetadata(
        id="fundamentals_analyst_v2",
        name="基本面分析师 v2.0",
        description="分析公司财务数据和基本面指标（插件化架构版本）",
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_fundamentals_unified"],
        version="2.0.0",
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="fundamentals_report", type="string", description="基本面分析报告"),
        ],
        requires_tools=True,
        output_field="fundamentals_report",
        report_label="【基本面分析 v2】",
    )

    def __init__(
        self,
        config: Optional[Any] = None,
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[list] = None
    ):
        """
        初始化基本面分析师
        
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
        执行基本面分析（使用 BaseAgent 标准化工具调用循环）

        Args:
            state: 包含以下键的状态字典:
                - ticker: 股票代码
                - trade_date: 交易日期
                - messages: 消息历史（可选）
                - prompt_overrides: 提示词覆盖（可选，用于调试）

        Returns:
            更新后的状态，包含:
                - fundamentals_report: 基本面分析报告
                - messages: 更新的消息历史
        """
        ticker = state.get("ticker") or state.get("company_of_interest")
        trade_date = state.get("trade_date") or state.get("end_date")
        context = state.get("context")

        # 支持提示词覆盖（用于调试）
        overrides = state.get("prompt_overrides") or {}
        system_override = overrides.get("system")
        user_override = overrides.get("user")
        analysis_override = overrides.get("analysis")

        if not ticker:
            raise ValueError("缺少必需参数: ticker 或 company_of_interest")

        logger.info(f"开始基本面分析: {ticker} (日期: {trade_date})")

        # 构建系统提示词（优先级：覆盖 > 模板 > 默认）
        system_prompt = system_override
        if not system_prompt:
            system_prompt = self._build_system_prompt(state)

        # 构建用户提示词（优先级：覆盖 > 默认）
        user_prompt = user_override
        if not user_prompt:
            user_prompt = self._build_user_prompt(ticker, trade_date, state)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # 使用 BaseAgent 标准化的工具调用方法
        if self._llm and self.tools:
            # 使用默认提示词（模板中已包含详细的分析要求和输出格式）
            # 除非用户通过 prompt_overrides 覆盖
            analysis = self.invoke_with_tools(messages, analysis_prompt=analysis_override)
        else:
            # 降级：没有 LLM 或工具
            logger.warning("没有配置 LLM 或工具，返回模拟结果")
            analysis = self._generate_mock_report(ticker, trade_date)

        logger.info(f"✅ 基本面分析完成，报告长度: {len(analysis)} 字符")

        # 只返回新增的字段，避免覆盖并行节点的更新
        return {
            "fundamentals_report": analysis
        }

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词

        Args:
            state: 工作流状态（用于提取模板变量）

        Returns:
            系统提示词
        """
        if state is None:
            state = {}

        # 从模板系统获取提示词
        try:
            ticker = state.get("ticker") or state.get("company_of_interest", "")
            trade_date = state.get("trade_date") or state.get("end_date", "")
            context = state.get("context")

            # 获取市场信息和公司名称
            market_name = "中国A股"
            company_name = ""
            currency_name = "人民币"
            currency_symbol = "¥"

            if StockUtils and ticker:
                try:
                    market_info = StockUtils.get_market_info(ticker)
                    market_name = market_info.get("market_name", "中国A股")
                    currency_name = market_info.get("currency_name", "人民币")
                    currency_symbol = market_info.get("currency_symbol", "¥")
                except Exception as e:
                    logger.warning(f"获取市场信息失败: {e}")

            # 准备模板变量
            template_variables = {
                "ticker": ticker,
                "company_name": company_name,
                "market_name": market_name,
                "current_date": trade_date,
                "start_date": "",  # 可以计算1年前的日期
                "currency_name": currency_name,
                "currency_symbol": currency_symbol,
                "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
            }

            # 从 context 中获取 preference_id
            preference_id = "neutral"
            if context and hasattr(context, 'preference_id'):
                preference_id = context.preference_id or "neutral"

            prompt = self._get_prompt_from_template(
                agent_type="analysts_v2",
                agent_name="fundamentals_analyst_v2",
                variables=template_variables,
                context=context,
                fallback_prompt=None
            )

            if prompt:
                logger.info(f"✅ 从模板系统获取基本面分析师 v2.0 提示词 (长度: {len(prompt)})")
                return prompt
        except Exception as e:
            logger.warning(f"⚠️ 从模板系统获取提示词失败: {e}")

        # 降级：使用默认提示词
        return """你是一位专业的股票基本面分析师。

你的任务是：
1. 使用工具获取股票的基本面数据（财务数据、估值指标等）
2. 分析公司的财务健康状况、盈利能力、成长性
3. 评估公司的估值水平（市盈率、市净率等）
4. 提供投资建议和合理价位区间

要求：
- 必须基于真实数据进行分析
- 分析要专业、客观、详细
- 使用中文撰写报告"""

    def _build_user_prompt(self, ticker: str, trade_date: str, state: Dict[str, Any] = None) -> str:
        """构建用户提示词"""
        return f"""请分析股票 {ticker} 的基本面情况。

分析日期：{trade_date}

请调用工具获取基本面数据，然后生成详细的分析报告。"""

    def _build_analysis_prompt(self, ticker: str) -> str:
        """构建分析提示词"""
        return f"""基于获取的数据，请生成 {ticker} 的基本面分析报告，包括：

1. 财务健康状况分析
2. 盈利能力评估
3. 成长性分析
4. 估值水平评估
5. 投资建议和合理价位区间"""

    def _generate_mock_report(self, ticker: str, trade_date: str) -> str:
        """生成模拟报告（降级方案）"""
        return f"""这是一个模拟的基本面分析报告。

股票代码: {ticker}
分析日期: {trade_date}

财务状况：良好
盈利能力：稳定
估值水平：合理
建议：持有"""

