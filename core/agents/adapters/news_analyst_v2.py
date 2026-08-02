"""
新闻分析师 v2.0

基于AnalystAgent基类实现的新闻分析师
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from core.agents.analyst import AnalystAgent
from core.agents.base import GENERIC_REPORT_FALLBACK
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class NewsAnalystV2(AnalystAgent):
    """
    新闻分析师 v2.0
    
    功能：
    - 获取股票相关新闻与公告
    - 识别事件影响路径与时效性
    - 提炼催化、风险与待验证事项
    
    工作流程：
    1. 调用统一新闻工具获取新闻数据
    2. 使用LLM分析新闻内容
    3. 生成新闻分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("news_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="news_analyst_v2",
        name="新闻分析师 v2.0",
        description="分析股票相关新闻与公告，提炼事件影响路径、催化与风险提示",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_news_headlines_unified", "get_stock_news_details_unified"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="news_report", type="string", description="新闻分析报告"),
        ],
        requires_tools=True,
        output_field="news_report",
        report_label="【新闻分析 v2】",
        workflow_stage="analyst",
    )

    # 分析师类型
    analyst_type = "news"
    
    # 输出字段名
    output_field = "news_report"

    def load_tools_from_config(self) -> list:
        """强制新闻分析师使用拆分后的标题/明细工具。"""
        tool_ids = super().load_tools_from_config()
        filtered_tool_ids = [
            tool_id
            for tool_id in tool_ids
            if tool_id != "get_stock_news_unified"
        ]

        for required_tool in ["get_stock_news_headlines_unified", "get_stock_news_details_unified"]:
            if required_tool not in filtered_tool_ids:
                filtered_tool_ids.append(required_tool)

        return filtered_tool_ids

    @staticmethod
    def _build_news_tool_workflow_prompt(analysis_date: str) -> str:
        """返回新闻工具的固定调用顺序说明。"""
        return f"""
工具工作流要求：
1. 第一步必须调用 get_stock_news_headlines_unified，curr_date 必须传 {analysis_date}。
2. 先根据标题、来源、相关性、明细建议做去重筛选，不要直接开始写分析。
3. 第二步再调用 get_stock_news_details_unified，并把选中的 1 至 3 个 news_id 一次性传入。
4. 如果标题工具提示“可暂不展开”，除非该新闻对核心论点必要，否则不要继续拉明细。
5. 不要调用 get_stock_news_unified；该工具是兼容接口，不是本分析师的默认流程。
""".strip()

    @staticmethod
    def _sanitize_template_prompt(prompt: Optional[str]) -> str:
        """移除模板中残留的旧统一新闻工具指令，避免与两阶段工作流冲突。"""
        prompt_text = str(prompt or "").strip()
        if not prompt_text:
            return ""

        sanitized_lines = []
        skip_next_param_line = False
        for raw_line in prompt_text.splitlines():
            line = raw_line.rstrip()
            if "get_stock_news_unified" in line:
                skip_next_param_line = True
                continue

            if skip_next_param_line and line.strip().startswith("参数:"):
                skip_next_param_line = False
                continue

            skip_next_param_line = False
            sanitized_lines.append(line)

        sanitized_prompt = "\n".join(sanitized_lines)
        sanitized_prompt = re.sub(r"\n{3,}", "\n\n", sanitized_prompt).strip()
        return sanitized_prompt

    @staticmethod
    def _has_two_stage_news_workflow(prompt: Optional[str]) -> bool:
        """判断模板是否已经自带两阶段新闻工具工作流。"""
        prompt_text = str(prompt or "")
        return (
            "get_stock_news_headlines_unified" in prompt_text
            and "get_stock_news_details_unified" in prompt_text
        )

    def _get_langchain_tool_by_name(self, tool_name: str):
        for tool in self._langchain_tools:
            if getattr(tool, "name", "") == tool_name:
                return tool
        return None

    def _invoke_prefetch_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Optional[str]:
        tool = self._get_langchain_tool_by_name(tool_name)
        if tool is None:
            logger.warning(f"[NewsAnalystV2] 预取工具未找到，跳过: {tool_name}")
            return None

        try:
            result = tool.invoke(tool_args)
        except Exception as exc:
            logger.warning(f"[NewsAnalystV2] 预取工具执行失败 {tool_name}: {exc}")
            return None

        result_text = str(result or "").strip()
        return result_text or None

    @staticmethod
    def _select_news_ids_for_details(ticker: str, analysis_date: str, limit: int = 3) -> List[str]:
        """根据标题工具的推荐动作选择需要展开明细的 news_id。"""
        try:
            from core.tools.implementations.news import stock_news as stock_news_module

            bundle = stock_news_module._build_stock_news_bundle(ticker, analysis_date, limit=12)
        except Exception as exc:
            logger.warning(f"[NewsAnalystV2] 读取新闻候选集失败，无法选择 news_id: {exc}")
            return []

        items = bundle.get("items") or []
        selected_ids: List[str] = []
        for desired_action in ["建议查看", "按需查看"]:
            for item in items:
                if item.get("detail_action") != desired_action:
                    continue

                news_id = str(item.get("news_id") or "").strip()
                if not news_id or news_id in selected_ids:
                    continue

                selected_ids.append(news_id)
                if len(selected_ids) >= limit:
                    return selected_ids

        return selected_ids

    def _build_prefetched_tool_message(
        self,
        ticker: str,
        analysis_date: Optional[str],
    ) -> Tuple[Optional[HumanMessage], List[str]]:
        """显式执行新闻标题与新闻明细两步工具，避免 LLM 在 live 下卡在伪工具调用文本。"""
        if not self._langchain_tools:
            return None, []

        from datetime import datetime

        _raw_date = analysis_date or datetime.now().strftime("%Y-%m-%d")
        if isinstance(_raw_date, datetime):
            effective_date = _raw_date.strftime("%Y-%m-%d")
        else:
            effective_date = str(_raw_date)
        sections: List[str] = []
        consumed_tool_names: List[str] = []

        headline_result = self._invoke_prefetch_tool(
            "get_stock_news_headlines_unified",
            {"ticker": ticker, "curr_date": effective_date, "limit": 12},
        )
        if headline_result:
            sections.append(f"### 去重后的新闻标题（get_stock_news_headlines_unified）\n{headline_result}")
            consumed_tool_names.append("get_stock_news_headlines_unified")

        selected_news_ids = self._select_news_ids_for_details(ticker, effective_date, limit=3)
        if selected_news_ids:
            details_result = self._invoke_prefetch_tool(
                "get_stock_news_details_unified",
                {
                    "ticker": ticker,
                    "curr_date": effective_date,
                    "news_ids": ",".join(selected_news_ids),
                },
            )
            if details_result:
                sections.append(f"### 已展开的新闻明细（get_stock_news_details_unified）\n{details_result}")
                consumed_tool_names.append("get_stock_news_details_unified")
        elif headline_result:
            sections.append(
                "### 明细选择说明\n当前标题候选中没有高优先级必须展开的新闻，后续分析需要基于标题级证据谨慎展开。"
            )

        if not sections:
            return None, []

        content = (
            "以下新闻工具结果已预先获取。请直接基于这些标题与明细撰写分析，不要再重复调用同名工具；"
            "如果某条新闻未展开更长明细，请明确写工具结果未提供更长正文。\n\n"
            + "\n\n".join(sections)
        )
        return HumanMessage(content=content), consumed_tool_names

    def _invoke_prefetched_analysis(self, messages: List[Any], analysis_prompt: str) -> str:
        """在新闻工具预取完成后，直接让 LLM 生成最终分析报告。"""
        final_messages = list(messages)
        final_messages.append(
            HumanMessage(
                content=(
                    "新闻标题与明细已经提供完毕。不要输出工具调用、JSON 或 XML 标签，"
                    "直接输出最终中文 Markdown 研究报告。\n\n"
                    + analysis_prompt
                )
            )
        )

        response = self._invoke_llm_with_trace(final_messages)
        report = response.content if hasattr(response, "content") else str(response)

        if "```" in report or '"name": "get_stock_news_' in report:
            logger.warning("[NewsAnalystV2] 预取分析阶段仍返回伪工具调用，追加强约束后重试一次")
            final_messages.append(
                HumanMessage(
                    content=(
                        "不要再请求调用任何工具。标题与明细都已经给出。现在只输出最终 Markdown 报告正文，"
                        "必须包含：最新新闻汇总、新闻影响分析、市场情绪评估、分析观点。"
                    )
                )
            )
            response = self._invoke_llm_with_trace(final_messages)
            report = response.content if hasattr(response, "content") else str(response)

        # 兜底：若两次重试后 report 仍是工具调用 JSON/XML，降级为文本说明而非存入原始 JSON
        if "</tool_call>" in report or '"name": "get_stock_news_' in report:
            logger.error("[NewsAnalystV2] 两次重试后仍返回伪工具调用，降级处理")
            report = "当前新闻数据已获取但分析模型未能正常展开，新闻研究结论暂时不可用，请参考其他维度报告。"

        return report

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """覆盖执行逻辑以支持专用新闻分析提示词。"""
        try:
            ticker, analysis_date = self._extract_common_params(state)

            market_type = state.get("market_type", "A股")
            context = state.get("context")
            overrides = state.get("prompt_overrides") or {}
            system_override = overrides.get("system")
            user_override = overrides.get("user")
            analysis_override = overrides.get("analysis")

            if not ticker:
                raise ValueError("Missing required parameters: ticker")

            system_prompt = system_override or self._build_system_prompt(market_type, context=context, state=state)
            user_prompt = user_override or self._build_user_prompt(ticker, analysis_date, {}, state)
            analysis_prompt = analysis_override or self._build_analysis_prompt(ticker)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            if self._llm:
                prefetched_message = None
                prefetched_tool_names: List[str] = []
                if self._langchain_tools:
                    prefetched_message, prefetched_tool_names = self._build_prefetched_tool_message(
                        ticker,
                        analysis_date,
                    )
                    if prefetched_message:
                        messages.append(prefetched_message)

                original_tools = list(self._langchain_tools)
                try:
                    if prefetched_tool_names:
                        self._langchain_tools = [
                            tool for tool in original_tools
                            if getattr(tool, "name", "") not in prefetched_tool_names
                        ]

                        # 有预取数据（prefetched_message 已追加到 messages）时直接进入分析，
                        # 避免 LLM 调用残余工具后把工具调用 JSON 存成报告
                        if not self._langchain_tools or prefetched_message is not None:
                            report = self._invoke_prefetched_analysis(messages, analysis_prompt)
                        else:
                            report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                    elif self._langchain_tools:
                        report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                    else:
                        response = self._invoke_llm_with_trace(messages)
                        report = response.content if hasattr(response, "content") else str(response)
                finally:
                    self._langchain_tools = original_tools
            else:
                raise ValueError("LLM not initialized")

            result = {self.output_field: report}
            # 🆕 附带工具调用摘要
            tool_summary = self._format_tool_call_summary()
            if tool_summary:
                result["tool_call_summaries"] = {self.analyst_type: tool_summary}
            return result

        except Exception as e:
            logger.error(f"[{self.agent_id}] 执行失败: {e}", exc_info=True)
            return {self.output_field: GENERIC_REPORT_FALLBACK}

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
        logger.info("🔍 [NewsAnalystV2] 开始构建系统提示词")
        
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
            agent_name="news_analyst_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=context or state.get("context"),  # 优先使用传入的 context，否则从 state 获取
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        prompt = self._sanitize_template_prompt(prompt)
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")

        workflow_prompt = self._build_news_tool_workflow_prompt(
            template_variables.get("analysis_date") or template_variables.get("current_date") or ""
        )

        if prompt:
            prompt_text = prompt.rstrip()
            if self._has_two_stage_news_workflow(prompt_text):
                return prompt_text
            return f"{prompt_text}\n\n{workflow_prompt}"
        
        # 降级：使用默认提示词
        return f"""您是一位专业的财经新闻分析师。

    您的职责是基于真实新闻、公告与监管信息，识别对公司研究判断有意义的事件线索，区分短期噪音与中期变量。

    分析要点：
    1. 核心事件事实 - 最近公告、新闻、监管变化的关键信息
    2. 事件影响路径 - 这些事件将影响经营、估值预期、行业位置还是风险暴露
    3. 时效性与可信度 - 事件是否过时、是否来自可靠来源
    4. 催化与风险 - 哪些因素可能强化判断，哪些因素会削弱判断
    5. 后续观察事项 - 仍需跟踪的披露、数据点或验证信号

    严格要求：
    - 不得输出买入、卖出、持有、加减仓、目标价、价格区间、止损止盈或仓位建议。
    - 允许引用工具返回的真实时间、事件与数字，但不得改写成执行建议或价格触发条件。

    请使用中文，基于真实数据进行分析。

    {workflow_prompt}"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],  # 保留参数以兼容基类，但工具数据会通过 ToolMessage 传递
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 和 fundamentals_analyst_v2 的实现）
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据（保留以兼容基类，但工具数据会通过 ToolMessage 传递）
            state: 工作流状态（用于提取模板变量）
            
        Returns:
            用户提示词
        """
        logger.info("🔍 [NewsAnalystV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        company_name = self._get_company_name(ticker, state)
        market_name = "中国A股"
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                market_name = market_info.get('market_name', "中国A股")
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        # 🔑 关键：确保日期格式正确（YYYY-MM-DD），而不是 datetime 对象
        if isinstance(analysis_date, str):
            # 如果已经是字符串，确保格式正确
            if len(analysis_date) > 10:
                # 如果是 datetime 字符串（如 "2026-01-14 00:00:00"），只取日期部分
                analysis_date_str = analysis_date.split()[0]
            else:
                analysis_date_str = analysis_date
        else:
            # 如果是 datetime 对象，转换为字符串
            from datetime import datetime
            if isinstance(analysis_date, datetime):
                analysis_date_str = analysis_date.strftime("%Y-%m-%d")
            else:
                analysis_date_str = str(analysis_date)
        
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "analysis_date": analysis_date_str,  # 🔑 确保是字符串格式 YYYY-MM-DD
            "current_date": analysis_date_str,  # 🔑 确保是字符串格式 YYYY-MM-DD
            "start_date": "",  # 可以计算1年前的日期
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
        }
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        # 🔑 注意：工具返回的数据会通过 ToolMessage 传递，不需要在 user_prompt 中检查
        
        # 🔍 调试：打印模板变量
        logger.info(f"🔍 [NewsAnalystV2] 准备传递给模板系统的变量:")
        for k, v in template_variables.items():
            logger.info(f"  - {k}: {v}")
        
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="news_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        prompt = self._sanitize_template_prompt(prompt)
        
        workflow_prompt = self._build_news_tool_workflow_prompt(analysis_date_str)

        if prompt:
            logger.info(f"✅ 从模板系统获取新闻分析师 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            prompt_text = prompt.rstrip()
            if self._has_two_stage_news_workflow(prompt_text):
                return prompt_text
            return f"{prompt_text}\n\n{workflow_prompt}"
        
        # 降级：使用默认提示词（不再检查 tool_data，因为工具数据会通过 ToolMessage 传递）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        # 🔑 关键：在默认提示词中明确告诉LLM要使用什么日期调用工具
        return f"""请对股票 {ticker}（{company_name}）进行详细的新闻事件研究：

**分析日期**：{analysis_date_str}

    {workflow_prompt}

    请调用工具获取新闻数据，然后基于真实结果输出中文研究报告，至少包含：
    1. 核心新闻与公告事实
    2. 事件影响路径与时效性判断
    3. 主要催化、主要风险与信息缺口
    4. 需要继续跟踪的后续观察事项

    禁止输出买卖建议、目标价、价格区间、止损止盈、仓位计划或任何执行性指令。"""

    def _get_company_name(self, ticker: str, state: Dict[str, Any]) -> str:
        """获取公司名称"""
        company_name = str(
            state.get("company_name")
            or state.get("stock_name")
            or state.get("name")
            or ""
        )
        if company_name:
            return company_name
        
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

    def _build_analysis_prompt(self, ticker: str) -> str:
        """构建工具调用后的新闻分析提示词。"""
        return f"""基于获取的数据，请生成 {ticker} 的专业新闻分析报告，包括：

    1. 最新新闻汇总
    2. 新闻影响分析
    3. 市场情绪评估
    4. 分析观点

    如果多个标题本质上描述同一事件的不同转述、转载或跟进，必须合并成同一条核心事件，不得重复累加为多份独立证据。
    如果工具只提供标题、发布时间、来源或链接，而没有正文细节、金额、业绩数值或监管结论，只能基于显性信息说明事件类别和研究相关性，不得补造细节。
    时效性与来源可信度要单独交代，不要仅因发布时间较近就放大事件确定性。
    如果新闻之间存在方向冲突，必须明确写出冲突点以及为什么不能下更强结论。
    如果工具没有返回某项事件细节、市场反馈或后续进展，请直接写“工具结果未提供”或“该环节仍待验证”，不要自行补全。
    分析 `新闻影响分析` 时，可用表格概括新闻、类型和影响等级；类型优先写偏积极、偏审慎或中性，不要写成买点、利空出尽或交易机会。
    `市场情绪评估` 只说明新闻对市场情绪的可能影响及其限制，不要把情绪变化直接写成股价结论。
    `分析观点` 中必须同时给出新闻面评估、短期反应预期和对整体研究结论的影响；短期反应预期只能写预期变化方向与原因，不得写股价点位预测。
    如存在信息缺口或仍待验证事项，可在对应段落顺带一句说明，无需单列章节。
    可以引用工具返回的真实时间、来源、标题和数字做事实说明，但不得把这些内容改写成目标价、价格区间、短期股价预测、支撑阻力位或执行计划。
    请使用研究口径表达事件含义，优先使用“偏积极”“偏审慎”“中性”“强化了某项预期”“增加了某项不确定性”“仍待验证”等表述，不要使用“重大利好”“重大利空”“短线催化”“打开上涨空间”“明确买点”等交易化措辞。
    在工具结果充分时，报告应保持足够展开，正常情况下不少于700字。

    不要输出投资建议、目标价、价格区间、仓位或执行计划。
    不得添加任何署名、作者、分析师、日期或声明信息。"""

