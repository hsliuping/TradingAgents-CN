"""
研究经理 v2.0

基于ManagerAgent基类实现的研究经理
综合乐观与审慎情景研究，形成平衡研究结论
"""

import logging
from typing import Any, Dict, List, Optional

from ..manager import ManagerAgent
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
    from tradingagents.utils.template_client import get_agent_prompt, get_user_prompt
except (ImportError, KeyError):
    logger.warning("无法导入get_agent_prompt/get_user_prompt，将使用默认提示词")
    get_agent_prompt = None
    get_user_prompt = None

# 不再需要直接导入 get_agent_prompt/get_user_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class ResearchManagerV2(ManagerAgent):
    """
    研究经理 v2.0
    
    功能：
    - 综合乐观与审慎情景研究
    - 主持辩论（可选）
    - 做出平衡研究结论
    - 生成综合研究结论
    
    工作流程：
    1. 读取乐观情景与审慎情景研究报告
    2. 主持辩论（可选）
    3. 综合研判
    4. 生成平衡研究结论与观察重点
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("research_manager_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "bull_report": "...",
            "bear_report": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="research_manager_v2",
        name="研究经理 v2.0",
        description="综合乐观与审慎情景研究，形成平衡研究结论与观察重点",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 管理者不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="bull_report", type="string", description="乐观情景研究报告", source="state", state_field="bull_report", producer_hint="bull_researcher_v2"),
            AgentInput(name="bear_report", type="string", description="审慎情景研究报告", source="state", state_field="bear_report", producer_hint="bear_researcher_v2"),
        ],
        outputs=[
            AgentOutput(name="investment_advice", type="string", description="平衡研究结论"),
        ],
        requires_tools=False,
        output_field="investment_advice",
        report_label="【平衡研究结论 v2】",
        workflow_stage="manager",
        growth_role="optimizer",
        growth_outputs=["investment_plan", "investment_debate_state"],
        memory_scope_hint="research_asset",
        review_level="manual_required",
        growth_source_type="manager_decision",
        maturity_level="stable",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["assistant", "workflow", "agent"],
    )
    
    # 管理者类型
    manager_type = "research"
    
    # 输出字段名
    output_field = "investment_plan"

    # 是否启用辩论
    enable_debate = True

    def _run_delegated_research_agents(self, state: Dict[str, Any]) -> Dict[str, Any]:
        node_config = state.get("node_config") or {}
        delegated_agent_ids = node_config.get("delegated_agent_ids") or []
        if not isinstance(delegated_agent_ids, list):
            return {}

        delegated_outputs: Dict[str, Any] = {}
        for target_agent_id in delegated_agent_ids:
            normalized_target = str(target_agent_id or "").strip()
            if not normalized_target or normalized_target == self.agent_id:
                continue

            if normalized_target == "chip_distribution_analyst_v2" and (state.get("chip_report") or delegated_outputs.get("chip_report")):
                logger.info("[ResearchManagerV2] 已存在 chip_report，跳过委托 chip_distribution_analyst_v2")
                continue

            logger.info("[ResearchManagerV2] 委托补充研究 Agent: %s", normalized_target)
            delegate_result = self.delegate_to_agent(
                normalized_target,
                {**state, **delegated_outputs},
                payload={
                    "task_description": "补充筹码分布与持仓成本结构上下文，供研究经理做综合投资判断",
                },
                metadata={
                    "delegation_role": "research_enrichment",
                },
            )
            if isinstance(delegate_result, dict):
                delegated_outputs.update(delegate_result)

        return delegated_outputs

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行研究经理分析

        重写父类方法以添加 investment_debate_state 输出，
        确保与报告格式化器兼容
        """
        logger.info("=" * 80)
        logger.info("🔍 [ResearchManagerV2] 开始执行投资决策")
        logger.info("=" * 80)

        # 🔍 检查输入数据
        ticker = state.get("ticker", "未知")
        bull_report = state.get("bull_report", "")
        bear_report = state.get("bear_report", "")

        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📈 看涨报告类型: {type(bull_report)}, 长度: {len(str(bull_report))} 字符")
        logger.info(f"📉 看跌报告类型: {type(bear_report)}, 长度: {len(str(bear_report))} 字符")

        # 转换为字符串（如果不是）
        bull_report_str = str(bull_report) if bull_report else ""
        bear_report_str = str(bear_report) if bear_report else ""

        if bull_report_str and len(bull_report_str) > 10:
            logger.info(f"📈 看涨报告前200字符: {bull_report_str[:200]}...")
        else:
            logger.warning("⚠️ 看涨报告为空或过短！")

        if bear_report_str and len(bear_report_str) > 10:
            logger.info(f"📉 看跌报告前200字符: {bear_report_str[:200]}...")
        else:
            logger.warning("⚠️ 看跌报告为空或过短！")

        # 🔥 ETF工作流兜底：若无辩论报告，将三份分析师报告合成为研究材料
        if not bull_report_str and not bear_report_str:
            market_report = state.get("market_report", "")
            news_report = state.get("news_report", "")
            fundamentals_report = state.get("fundamentals_report", "")
            parts = []
            if fundamentals_report:
                parts.append(f"### ETF/基本面分析\n{fundamentals_report}")
            if market_report:
                parts.append(f"### 市场与技术分析\n{market_report}")
            if news_report:
                parts.append(f"### 新闻面分析\n{news_report}")
            if parts:
                combined = "\n\n".join(parts)
                state = {
                    **state,
                    "bull_report": combined,
                    "bear_report": (
                        "（本工作流为无辩论单路分析模式。"
                        "请从上述综合分析材料中，同时识别支持上行的因素和支持下行的因素，进行平衡判断。）"
                    ),
                }
                logger.info(
                    f"[ResearchManagerV2] 无辩论报告，已将分析师报告合成为研究材料 ({len(combined)} 字符)"
                )

        delegated_outputs = self._run_delegated_research_agents(state)
        if delegated_outputs:
            logger.info(f"🔗 [ResearchManagerV2] 已收到委托结果字段: {list(delegated_outputs.keys())}")
            state = {**state, **delegated_outputs}

        # 调用父类方法获取基本输出
        logger.info("🚀 调用父类 execute 方法...")
        result = super().execute(state)
        logger.info("✅ 父类 execute 方法执行完成")

        # 提取决策内容
        decision_value = result.get(self.output_field, "")
        logger.info(f"📝 决策输出字段: {self.output_field}")
        logger.info(f"📝 决策内容类型: {type(decision_value)}")
        logger.info(f"📝 决策内容长度: {len(str(decision_value))} 字符")

        # 🔥 修复：如果是字典（包含 content 字段），提取 content
        if isinstance(decision_value, dict):
            decision_content = decision_value.get("content", "")
            logger.info(f"📝 从字典中提取 content: {len(decision_content)} 字符")
        else:
            decision_content = decision_value
            logger.info(f"📝 直接使用决策内容: {len(decision_content)} 字符")

        # 从 state 中获取现有的 investment_debate_state（如果有）
        existing_debate_state = state.get("investment_debate_state", {})

        # 构建新的 investment_debate_state，包含 judge_decision
        new_debate_state = {
            "judge_decision": decision_content,  # ✅ 关键：添加 judge_decision 字段
            "history": existing_debate_state.get("history", ""),
            "bull_history": existing_debate_state.get("bull_history", ""),
            "bear_history": existing_debate_state.get("bear_history", ""),
            "current_response": decision_content,
            "count": existing_debate_state.get("count", 0),
        }

        logger.info("✅ [ResearchManagerV2] 投资决策执行完成")
        logger.info("=" * 80)

        # 返回包含 investment_debate_state 的结果
        return {
            **delegated_outputs,
            **result,
            "investment_debate_state": new_debate_state,
        }
    
    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）

        Args:
            state: 工作流状态（用于提取模板变量）

        Returns:
            系统提示词
        """
        logger.info("🔍 [ResearchManagerV2] 开始构建系统提示词")
        
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

        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="managers_v2",  # ✅ 修复：使用 v2 类型
            agent_name="research_manager_v2",  # ✅ 修复：使用 v2 名称
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # ✅ 关键：指定获取系统提示词（包含output_format）
        )

        # 检查是否成功获取提示词
        if prompt:
            logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
            logger.info(f"📝 系统提示词前500字符:\n{prompt[:500]}...")

            # 检查是否包含新的研究简报结构指导
            if "core_evidence" in prompt or "后续观察事项" in prompt:
                logger.info("✅ 系统提示词包含【研究简报结构】指导")
            else:
                logger.warning("⚠️ 系统提示词不包含【研究简报结构】指导（可能使用旧版提示词）")

            logger.debug(f"✅ 从模板系统获取研究经理系统提示词")
            return prompt
        else:
            logger.warning("⚠️ 从模板系统获取系统提示词失败，使用默认提示词")
        
        # 默认提示词（合规版本）
        return """你是一位中性的研究经理，负责把乐观情景研究与审慎情景研究整理成平衡研究结论。

    **分析风格**: 客观、克制、基于证据，强调 strongest case 对比、分歧根源、信息缺口与后续观察。

    **核心职责**:
    1. 先用双方最强的成立逻辑理解乐观与审慎两类论证，再形成当前研究判断。
    2. 说明双方共识、关键分歧及分歧根源，而不是只给一个结果标签。
    3. 点明支持判断的核心依据、关键不确定性、判断可能失效的条件与后续观察重点。
    4. 输出面向下游整合与风险审阅的平衡研究结论，帮助后续节点理解“为什么这样看”以及“接下来观察什么”。

    **分析原则**:
    - 应先按双方最强论点等权审阅，再根据证据质量决定当前倾向，不预设结论。
    - 只输出研究判断，不输出买入、卖出、持有、加减仓、仓位比例、目标价、止损止盈或执行节奏。
    - 可以描述上行或下行驱动，但只能表达为研究假设、证据权衡和待验证事项。
    - 若材料涉及当前价格、估值或市场已计入预期，可以说明这些信息如何影响研究判断，但不得延伸为目标价、价格区间、上涨/下跌空间、风险收益比或操作建议。
    - 所有结论必须严格基于提供的报告内容，不得补造信息。
    - 使用中文输出。

    **输出目标**:
    - 让用户理解当前证据更支持哪一类判断，以及为什么另一侧暂时没有占优。
    - 让用户知道关键依据、关键风险、判断升级或下修的前提，以及后续观察事项。
    - 为研究整合员与风险团队提供清晰、可复用的研究结论输入。

    **免责声明**：
    本研究简报仅供信息参考，不构成交易建议或投资承诺。请结合自身情况独立判断。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        inputs: Dict[str, Any],
        debate_summary: Optional[str],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            inputs: 收集的输入字典
            debate_summary: 辩论总结
            state: 工作流状态

        Returns:
            用户提示词
        """
        logger.info("🔍 [ResearchManagerV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        logger.info(f"📝 输入字段: {list(inputs.keys())}")

        # 检查看涨和看跌报告
        bull_report = inputs.get("bull_report", "")
        bear_report = inputs.get("bear_report", "")

        # 转换为字符串（如果不是）
        bull_report_str = str(bull_report) if bull_report else ""
        bear_report_str = str(bear_report) if bear_report else ""

        logger.info(f"📈 看涨报告类型: {type(bull_report)}, 长度: {len(bull_report_str)} 字符")
        logger.info(f"📉 看跌报告类型: {type(bear_report)}, 长度: {len(bear_report_str)} 字符")

        if bull_report_str and len(bull_report_str) > 10:
            # 检查是否包含价格信息
            if "价位" in bull_report_str or "价格" in bull_report_str or "¥" in bull_report_str:
                logger.info("✅ 看涨报告包含价格信息")
            else:
                logger.warning("⚠️ 看涨报告可能不包含价格信息")
        else:
            logger.warning("⚠️ 看涨报告为空或过短！")

        if bear_report_str and len(bear_report_str) > 10:
            # 检查是否包含价格信息
            if "价位" in bear_report_str or "价格" in bear_report_str or "¥" in bear_report_str:
                logger.info("✅ 看跌报告包含价格信息")
            else:
                logger.warning("⚠️ 看跌报告可能不包含价格信息")
        else:
            logger.warning("⚠️ 看跌报告为空或过短！")

        # 获取公司名称
        if StockUtils:
            market_info = StockUtils.get_market_info(ticker)
            company_name = self._get_company_name(ticker, market_info)
        else:
            company_name = ticker
        
        # 从 state 中获取当前价格
        current_price = state.get("current_price", "未知")
        logger.info(f"💰 当前价格: {current_price} (来源: state)")

        # 🆕 提取报告内容（如果是字典，取 content 字段）
        def extract_content(report):
            """从报告中提取纯文本内容"""
            if isinstance(report, dict):
                return report.get('content', str(report))
            return str(report) if report else "无"

        bull_report_content = extract_content(inputs.get("bull_report"))
        bear_report_content = extract_content(inputs.get("bear_report"))

        logger.info(f"📈 看涨报告内容长度: {len(bull_report_content)} 字符")
        logger.info(f"📉 看跌报告内容长度: {len(bear_report_content)} 字符")

        # 🆕 检测辩论模式并获取辩论历史
        debate_history = ""
        is_debate_mode = "investment_debate_state" in state and isinstance(state.get("investment_debate_state"), dict)

        if is_debate_mode:
            debate_state = state.get("investment_debate_state", {})
            full_history = debate_state.get("history", "")
            bull_history = debate_state.get("bull_history", "")
            bear_history = debate_state.get("bear_history", "")

            if full_history:
                debate_history = f"\n【完整辩论历史】\n{full_history}\n"
                logger.info(f"💬 [辩论模式] 读取到辩论历史，长度: {len(full_history)} 字符")
            else:
                logger.info("💬 [辩论模式] 辩论历史为空")
        else:
            logger.info("📝 [单次分析模式] 无辩论历史")

        # 准备模板变量
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
            "current_price": current_price,  # ✅ 添加当前价格
            "bull_report": bull_report_content,  # ✅ 只传递内容，不传递字典
            "bear_report": bear_report_content,  # ✅ 只传递内容，不传递字典
            "debate_summary": debate_summary or "无辩论总结",
            "debate_history": debate_history,  # 🆕 添加辩论历史
        }

        # 添加其他输入到模板变量
        for key, value in inputs.items():
            if key not in ["bull_report", "bear_report"]:
                template_variables[key] = str(value) if value else ""

        # 使用基类的通用方法获取用户提示词（基类会自动从 state 中提取系统变量）
        prompt = self._get_prompt_from_template(
            agent_type="managers_v2",  # ✅ 修复：使用 v2 类型
            agent_name="research_manager_v2",  # ✅ 修复：使用 v2 名称
            variables=template_variables,
            state=state,  # 🆕 传递 state，基类会自动提取系统变量
            context=state,
            fallback_prompt=None,
            prompt_type="user"  # 🆕 指定获取用户提示词
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取研究经理用户提示词 (长度: {len(prompt)})")
            return prompt
        
        market_name = state.get("market_name", "")
        currency_name = state.get("currency_name", "")
        currency_symbol = state.get("currency_symbol", "")

        target_line = f"{company_name}（{ticker}）"
        if market_name:
            target_line = f"{company_name}（{ticker}，{market_name}）"

        prompt = (
            "基于提供的研究材料进行综合研究判断。\n"
            "可用资源：\n"
            f"- 分析目标：{target_line}\n"
            f"- 分析日期：{analysis_date}\n"
            f"- 货币单位：{currency_name}（{currency_symbol}）\n"
            f"- 当前价格上下文：{current_price}\n"
            f"- 看涨观点：{bull_report_content}\n"
            f"- 看跌观点：{bear_report_content}\n"
            f"- 辩论总结：{debate_summary or '材料未提供'}\n"
        )

        for key, value in inputs.items():
            if key not in ["bull_report", "bear_report"]:
                prompt += f"- 补充材料 {key}：{value}\n"

        prompt += f"""

任务重点：
- 先用最强版本概括看涨理由，再用最强版本概括看跌理由，不要把任一方写成稻草人。
- 客观权衡看涨和看跌观点，先概括共识，再写最关键的分歧，形成当前研究判断：看涨 / 中性 / 看跌。
- 明确哪些内容是双方共识，哪些是关键分歧，以及分歧主要来自数据解读、前提假设、时间维度还是市场定价反映程度。
- 说明当前更有支撑的一侧；若保持中性，要解释为何双方证据仍然平衡或都未被充分验证。
- 提炼支持判断的核心依据，突出最关键的证据而非罗列所有信息。
- 识别关键不确定性，以及哪些新增事实会让当前判断上修、下修或失效。
- 列出后续观察事项，优先使用财报、公告、经营指标、行业数据、政策变化等可验证事项。
- 如果材料涉及当前价格或估值，可以说明市场是否已经计入部分乐观/悲观预期，但不得写成目标价、价格区间、上涨/下跌空间或风险收益比。
- 如果任一材料为空或证据不足，必须明确写“材料未提供”或“仍待验证”，不得使用模型记忆补全。
- 如果提到等待财报或年报，不要指定过时年份，直接写“等待下一期财报”或“等待年报发布”。

严格禁止：
- 不得输出买入、卖出、持有、加仓、减仓、清仓等动作建议。
- 不得输出目标价、价格区间、关键价位、风险控制参考价、仓位比例、收益预期。
- 不得把观察条件写成价格触发后的执行动作。

输出格式：
请使用 JSON 输出，字段如下：
```json
{{
    "analysis_view": "看涨|中性|看跌",
    "confidence": 0-100,
    "risk_score": 0.0-1.0,
    "summary": "50-120字的结论摘要，说明当前更偏向哪一侧及主因",
    "reasoning": "200-500字，建议按多方最强依据、空方最强依据、共识点、分歧根源、最终判断来说明多空证据如何权衡",
    "core_evidence": ["核心依据1", "核心依据2", "核心依据3"],
    "uncertainties": ["关键不确定性1", "关键不确定性2"],
    "invalidation_conditions": ["判断下修或失效前提1", "判断下修或失效前提2"],
    "watch_items": ["后续观察事项1", "后续观察事项2", "后续观察事项3"],
    "risk_warning": "100字以内的关键风险提示或主要反证"
}}
```

字段要求：
- `analysis_view`、`confidence`、`summary`、`reasoning` 为必填。
- `core_evidence`、`uncertainties`、`invalidation_conditions`、`watch_items` 为数组，尽量提供 2-5 条。
- `reasoning` 应显式体现：多方最强依据、空方最强依据、双方共识、关键分歧根源，以及为何当前判断偏向某侧或保持中性。
- 所有字段都必须服务于研究判断，不能出现交易执行语言。
"""

        logger.info(f"📝 用户提示词总长度: {len(prompt)} 字符")
        logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")

        if "可用资源" in prompt and "任务重点" in prompt:
            logger.info("✅ 用户提示词包含【可用资源】与【任务重点】指导")
        else:
            logger.warning("⚠️ 用户提示词不包含【可用资源】与【任务重点】指导")

        return prompt
    
    def _get_required_inputs(self) -> List[str]:
        """
        获取需要的输入列表
        
        Returns:
            输入字段名列表
        """
        return [
            "bull_report",
            "bear_report",
            "chip_report",
        ]
    
    def _get_company_name(self, ticker: str, market_info: dict) -> str:
        """获取公司名称"""
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

