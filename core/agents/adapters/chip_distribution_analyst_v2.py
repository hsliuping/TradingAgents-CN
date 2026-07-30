"""
筹码分布分析师Agent v2.0

基于AnalystAgent基类实现的筹码分布分析师。
分析股票筹码分布，评估获利比例、平均成本和筹码集中度。
提示词配置在数据库模板中，用户可以修改。
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


@register_agent
class ChipDistributionAnalystV2(AnalystAgent):
    """
    筹码分布分析师 v2.0

    功能：
    - 获取股票筹码分布数据
    - 分析获利比例（浮盈/浮亏情况）
    - 分析平均持仓成本
    - 评估筹码集中度（90%/70%区间）
    - 生成筹码分布分析报告

    工作流程：
    1. 调用筹码分布工具获取数据（AkShare优先，Tushare备用）
    2. 使用LLM深度分析筹码分布含义
    3. 生成筹码分布分析报告
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="chip_distribution_analyst_v2",
        name="筹码分布分析师 v2.0",
        description="分析股票筹码分布，评估获利比例、平均成本和筹码集中度，生成筹码分布分析报告",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        icon="🧮",
        color="#e74c3c",
        tags=["筹码分布", "持仓成本", "获利比例", "v2.0"],
        default_tools=["get_chip_distribution"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="chip_report", type="string", description="筹码分布分析报告"),
        ],
        requires_tools=True,
        output_field="chip_report",
        report_label="【筹码分布分析 v2】",
        workflow_stage="analyst",
        execution_order=15,
    )

    # 分析师类型
    analyst_type = "chip_distribution"

    # 输出字段名
    output_field = "chip_report"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行筹码分布分析"""
        try:
            ticker, analysis_date = self._extract_common_params(state)
            context = state.get("context")
            overrides = state.get("prompt_overrides") or {}
            system_override = overrides.get("system")
            user_override = overrides.get("user")
            analysis_override = overrides.get("analysis")

            if not ticker:
                raise ValueError("Missing required parameters: ticker")

            # 构建系统提示词
            system_prompt = system_override
            if not system_prompt:
                template_variables = {
                    "ticker": ticker,
                    "analysis_date": analysis_date,
                    "current_date": analysis_date,
                    "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else "",
                }
                # 注入公司名称
                company_name = state.get("company_name", "")
                if not company_name and StockUtils and ticker:
                    try:
                        market_info = StockUtils.get_market_info(ticker)
                        template_variables["company_name"] = market_info.get("company_name", ticker)
                        template_variables["market_name"] = market_info.get("market_name", "中国A股")
                    except Exception:
                        template_variables["company_name"] = ticker
                        template_variables["market_name"] = "中国A股"
                else:
                    template_variables["company_name"] = company_name or ticker
                    template_variables["market_name"] = state.get("market_name", "中国A股")

                system_prompt = self._get_prompt_from_template(
                    agent_type="analysts_v2",
                    agent_name="chip_distribution_analyst_v2",
                    variables=template_variables,
                    state=state,
                    context=context,
                    fallback_prompt=None,
                    prompt_type="system"
                )

            if not system_prompt:
                system_prompt = self._build_system_prompt(state=state)

            # 构建用户提示词
            user_prompt = user_override
            if not user_prompt:
                user_prompt = self._build_user_prompt(ticker, analysis_date, state)

            system_prompt = self._apply_global_trading_advice_guard(system_prompt)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            if self._llm:
                if self._langchain_tools:
                    analysis_prompt = analysis_override or self._build_analysis_prompt(ticker, analysis_date)
                    report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                    tool_summary = self._format_tool_call_summary()
                    if self._chip_tool_unavailable():
                        report = self._build_unavailable_report(ticker, analysis_date)
                else:
                    response = self._invoke_llm_with_trace(messages)
                    report = response.content if hasattr(response, "content") else str(response)
                    tool_summary = ""
            else:
                raise ValueError("LLM未初始化")

            result = {self.output_field: report}
            if tool_summary:
                result["tool_call_summaries"] = {self.analyst_type: tool_summary}
            return result

        except Exception as e:
            logger.error(f"[{self.agent_id}] 执行失败: {e}", exc_info=True)
            return {self.output_field: f"筹码分布分析失败: {str(e)}"}

    def _chip_tool_unavailable(self) -> bool:
        summaries = getattr(self, "_tool_call_summaries_collected", []) or []
        chip_calls = [s for s in summaries if s.get("tool_name") == "get_chip_distribution"]
        if not chip_calls:
            return False

        last_call = chip_calls[-1]
        result = str(last_call.get("result_preview") or "")
        error_markers = ("❌", "工具执行失败", "无法获取", "未能获取")
        return (not last_call.get("success")) or any(marker in result for marker in error_markers)

    def _build_unavailable_report(self, ticker: str, analysis_date: str) -> str:
        summaries = getattr(self, "_tool_call_summaries_collected", []) or []
        chip_calls = [s for s in summaries if s.get("tool_name") == "get_chip_distribution"]
        reason = "筹码分布工具未返回有效数据"
        if chip_calls:
            last_call = chip_calls[-1]
            reason = last_call.get("error") or last_call.get("result_preview") or reason

        return f"""⚠️ **筹码分布数据暂不可用**

股票代码：{ticker}  
分析日期：{analysis_date}

本次未能生成有效筹码分布分析报告，原因是筹码分布工具没有返回可分析的数据。

**工具返回信息**：{reason}

为避免产生误导性结论，本节点不基于模型猜测或补写筹码结构、获利比例、平均成本、支撑压力位等指标。请稍后重试，或检查 AkShare/Tushare 数据源、网络连接与本机 socket 资源状态。"""

    def _build_analysis_prompt(self, ticker: str, analysis_date: str) -> str:
        return f"""基于筹码分布工具返回的真实数据，生成 {ticker} 在 {analysis_date} 的筹码分布分析报告。

要求：
1. 只能使用 ToolMessage 中实际返回的数据，不得使用模型知识判断当前年份或日期是否存在。
2. 如果工具返回以“❌”开头，或内容包含“工具执行失败”“无法获取”“未能获取”，请直接说明“筹码分布数据暂不可用”，并引用工具失败原因。
3. 工具失败时禁止编造获利比例、平均成本、筹码区间、支撑压力位，也不要生成未来日期不可分析之类的推断。
4. 工具成功时，围绕获利比例、平均成本、90%/70%筹码区间、集中度、支撑压力关系进行分析。
5. 使用中文 Markdown 输出。"""

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """构建默认系统提示词（数据库模板优先）"""
        if state is None:
            state = {}

        template_variables = {}
        if "ticker" in state:
            template_variables["ticker"] = state["ticker"]
        analysis_date = state.get("analysis_date") or state.get("trade_date")
        if analysis_date:
            if isinstance(analysis_date, str) and len(analysis_date) > 10:
                analysis_date = analysis_date.split()[0]
            template_variables["current_date"] = analysis_date
            template_variables["analysis_date"] = analysis_date

        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="chip_distribution_analyst_v2",
            variables=template_variables,
            state=state,
            context=state.get("context"),
            fallback_prompt=None,
            prompt_type="system"
        )
        if prompt:
            return prompt

        return """你是一位专业的A股筹码分布分析师，擅长通过筹码分布数据洞察市场博弈格局。

你的职责：
1. 解读筹码获利比例（当前价格下浮盈筹码占比）
2. 分析平均持仓成本与当前价格的关系
3. 评估90%/70%筹码集中区间及集中度
4. 判断上方压力和下方支撑
5. 综合研判主力持仓意图和趋势

分析要求：
- 客观解读筹码数据，避免主观臆断
- 结合获利比例判断抛压轻重
- 结合集中度判断趋势稳定性
- 给出明确的支撑/压力位判断
- 使用中文输出

输出格式：
请以结构化方式输出筹码分布分析报告，包括：
- 筹码获利状况
- 成本结构分析
- 筹码集中度评估
- 支撑压力位分析
- 综合研判
"""

    def _build_user_prompt(self, ticker: str, analysis_date: str, state: Dict[str, Any]) -> str:
        """构建用户提示词（数据库模板优先）"""
        if state is None:
            state = {}

        company_name = state.get("company_name", ticker)
        market_name = state.get("market_name", "中国A股")

        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "analysis_date": analysis_date,
            "current_date": analysis_date,
            "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else "",
        }

        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="chip_distribution_analyst_v2",
            variables=template_variables,
            state=state,
            context=state.get("context"),
            fallback_prompt=None,
            prompt_type="user"
        )
        if prompt:
            return prompt

        return f"""请分析 {company_name}（{ticker}）在 {analysis_date} 的筹码分布情况：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}
市场：{market_name}

请调用筹码分布工具获取数据，然后生成详细的筹码分布分析报告。
重点分析：获利比例、平均成本、筹码集中度、支撑压力位。"""

