"""
研究整合员 v2.0

基于TraderAgent基类实现的研究整合员
根据综合研究证据生成用户版研究简报
（系统输出为研究观察汇总，不构成投资建议）
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..trader import TraderAgent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

logger = logging.getLogger(__name__)


# ==================== 合规约束 & 校验契约定义 ====================
# 目的：与 risk_manager_v2 / research_manager_v2 形成同构的"规格驱动"闭环，
# 让 LLM 输出从"自由决策"降级为"按预定义结构翻译"，从源头消除合规风险。
# 由于 trader_v2 输出是用户可读的 Markdown 简报（非结构化 JSON 决策），
# 这里采用"合规约束 prompt 前置 + 术语扫描校验"的轻量模式，
# 不强制 JSON schema，但显式上报合规违规，便于监控和排查。


# 研究整合员合规约束 & 简报结构契约。
# 按硬约束"system prompt 必须将格式要求放在最前面"，此常量会被前置到
# _build_system_prompt 返回值的最前面，确保 LLM 优先看到合规与结构约束。
TRADER_COMPLIANCE_PROMPT = """【合规性约束·必须严格遵守】
1. 禁止使用 "看涨" / "看跌" / "买入" / "卖出" / "加仓" / "减仓" / "持有" / "清仓" 等交易指令或市场观点术语。
2. 统一使用 "乐观" / "审慎" / "中性" 表达研究结论倾向（"乐观/审慎/中性" 表达的是研究倾向，不构成交易建议）。
3. 禁止给出具体目标价或风险关注价，不得延伸为价格区间、上涨/下跌空间、风险收益比或操作建议。
4. 禁止承诺收益或保证盈利，必须提示风险。
5. 所有结论必须严格基于提供的报告内容，不得补造信息或引入模型内部知识。

【简报结构契约·必须遵守】
请按以下结构输出 Markdown 用户版研究简报，每个章节标题必须出现且顺序一致：

## 一句话结论
（用一句话概括当前研究判断，使用"乐观/审慎/中性"表达倾向）

## 为什么这么看
（概括最关键的 2-4 条证据，每条单独成行）

## 当前判断的限制
（说明信息缺口、脆弱前提与结论边界）

## 后续关注
（列出最值得继续跟踪的公开信号）

## 资料边界说明
（如果报告未提供关键信息，必须明确指出）

## 免责声明
本研究简报仅供信息参考，不构成投资建议或交易承诺。请结合自身情况独立判断。

"""


# 合规禁用术语表（校验管线使用，与 prompt 约束保持一致）
TRADER_FORBIDDEN_TERMS: Tuple[str, ...] = (
    "看涨", "看跌", "买入", "卖出", "加仓", "减仓", "清仓",
)

# 注意："持有" 在简报中可能出现于"持有该观点"等非交易语境，单独校验会产生误报，
# 因此不放入强制禁用表，仅在 prompt 层面约束。如需更严格校验，可在此添加。

# 简报必备章节标记（校验管线使用，与数据库模板 version 14 章节名一致）
TRADER_REQUIRED_SECTIONS: Tuple[str, ...] = (
    "一句话结论", "为什么这么看",
)


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

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class TraderV2(TraderAgent):
    """
    研究整合员 v2.0
    
    功能：
    - 根据综合研究结论生成用户版研究简报
    - 提炼核心依据、判断边界与后续观察事项
    - 统一整理上游报告的用户可读表达
    
    工作流程：
    1. 读取综合研究结论和所有分析报告
    2. 提炼用户最关心的核心信息
    3. 生成用户版研究简报
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("trader_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "investment_plan": {...},
            "market_report": "...",
            "risk_assessment": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="trader_v2",
        name="研究整合员 v2.0",
        description="根据风险审阅后的综合研究结论生成用户版研究简报",
        category=AgentCategory.TRADER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 研究整合员不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论", source="state", state_field="investment_advice", source_state_fields=["investment_plan"], producer_hint="research_manager_v2"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False, source="state", state_field="market_report", producer_hint="market_analyst_v2"),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False, source="state", state_field="fundamentals_report", producer_hint="fundamentals_analyst_v2"),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False, source="state", state_field="news_report", producer_hint="news_analyst_v2"),
            AgentInput(name="sentiment_report", type="string", description="情绪分析报告", required=False, source="state", state_field="sentiment_report", producer_hint="social_analyst_v2"),
            AgentInput(name="index_report", type="string", description="大盘分析报告", required=False, source="state", state_field="index_report", producer_hint="index_analyst_v2"),
            AgentInput(name="sector_report", type="string", description="板块分析报告", required=False, source="state", state_field="sector_report", producer_hint="sector_analyst_v2"),
            AgentInput(name="bull_report", type="string", description="乐观情景研究报告", required=False, source="state", state_field="bull_report", producer_hint="bull_researcher_v2"),
            AgentInput(name="bear_report", type="string", description="审慎情景研究报告", required=False, source="state", state_field="bear_report", producer_hint="bear_researcher_v2"),
        ],
        outputs=[
            AgentOutput(name="trader_investment_plan", type="string", description="用户版研究简报"),
        ],
        requires_tools=False,
        output_field="trader_investment_plan",
        report_label="【用户版研究简报 v2】",
        workflow_stage="trader",
        growth_role="optimizer",
        growth_outputs=["trader_investment_plan"],
        memory_scope_hint="pattern",
        review_level="manual_required",
        growth_source_type="manager_decision",
        maturity_level="stable",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["assistant", "workflow", "agent"],
    )

    # 输出字段名（与报告格式化器期望的字段名一致）
    output_field = "trader_investment_plan"
    
    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）
        
        Args:
            state: 工作流状态（用于提取模板变量）
        
        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        logger.info("🔍 [TraderV2] 开始构建系统提示词")
        
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
        
        prompt = self._get_prompt_from_template(
            agent_type="trader_v2",
            agent_name="trader_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )

        # 🔥 按硬约束"system prompt 必须将格式要求放在最前面"，
        # 将合规约束 & 简报结构契约前置到 prompt 最前面，确保 LLM 优先看到合规约束，
        # 不依赖数据库迁移即可立即生效。
        if prompt:
            prompt = TRADER_COMPLIANCE_PROMPT + prompt
            logger.info(f"📝 系统提示词长度: {len(prompt)} 字符（含合规约束）")
            logger.debug("✅ 从模板系统获取研究整合员系统提示词（已前置合规约束）")
            return prompt

        logger.warning("⚠️ 从模板系统获取系统提示词失败，使用默认提示词")

        # 默认系统提示词（合规版本）— 同样前置合规约束，保证 fallback 路径也受约束
        return TRADER_COMPLIANCE_PROMPT + """你是一位研究整合员，负责根据风险审阅后的综合研究结论生成用户版研究简报。

## 你的职责

    1. **整合研究结论**：把综合研究结论翻译成普通用户可读的简报
    2. **提炼关键信息**：概括为什么这么看、关键分歧、不确定性与后续关注
    3. **保留研究边界**：说明当前判断成立的前提与可能失效的条件
    4. **统一表达口径**：将上游多份报告整理成一致、清晰、可直接阅读的最终简报

## 分析原则

    - **基于研究结论**：以研究经理的综合研究结论和风险审阅结论为主线组织内容
    - **不扩展为交易计划**：不得输出买卖、加减仓、仓位比例、目标价、价格区间、风险关注与收益关注价位或执行节奏
    - **客观呈现证据**：清晰说明支持判断的依据、关键不确定性与后续观察事项
    - **保持用户可读性**：使用简洁中文，不堆叠术语，不制造未提供的信息

## 重要说明

    - **基于已有数据**：你只能使用提供的分析报告与上游研究结论生成用户版研究简报
    - **风险审阅已在上游完成**：本阶段负责整合表达，不再重新生成交易计划或风险控制方案
    - **不引入外部推断**：不得使用模型内部知识、材料外信息或额外价格推演补足结论

**免责声明**：
    本研究简报仅供信息参考，不构成投资建议或交易承诺。请结合自身情况独立判断。"""

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行研究简报生成，并添加合规校验显式上报。

        重写父类方法以在 LLM 输出后添加合规术语扫描和结构完整性校验，
        让错误显式化（参考 risk_manager_v2 / research_manager_v2 的校验管线模式）。

        校验策略：
        - 校验通过：设置 trader_plan_validation_status="passed"
        - 校验失败：保留原始输出（用户可读简报不自动修改，避免引入错误），
          设置 trader_plan_validation_status="failed" + trader_plan_validation_warning
        """
        logger.info("=" * 80)
        logger.info("📝 [TraderV2] 开始执行用户版研究简报生成")
        logger.info("=" * 80)

        # P1: 启动执行轨迹采集（TraderV2 自行管理，因为父类 TraderAgent 不在 ManagerAgent 改造范围）
        from core.agents.execution_trace_recorder import (
            start_execution_trace, is_trace_enabled
        )
        recorder = None
        if is_trace_enabled():
            try:
                recorder = start_execution_trace(self, state)
            except Exception as e:
                logger.warning(f"⚠️ [TraderV2] 启动轨迹采集失败: {e}")

        try:
            # 记录输入
            if recorder:
                _input_keys = [
                    "investment_plan", "market_report", "fundamentals_report",
                    "news_report", "sentiment_report", "index_report", "sector_report",
                    "bull_report", "bear_report", "risk_assessment",
                ]
                _inputs = {k: state.get(k) for k in _input_keys if state.get(k)}
                recorder.record_inputs(_inputs)

            # 调用父类方法获取基本输出
            import time as _time
            _t0 = _time.time()
            result = super().execute(state)
            _llm_duration_ms = int((_time.time() - _t0) * 1000)

            # 提取简报内容（兼容字典/字符串两种输出形态）
            decision_value = result.get(self.output_field, "")
            if isinstance(decision_value, dict):
                decision_text = (
                    decision_value.get("content", "")
                    or decision_value.get("markdown", "")
                    or str(decision_value)
                )
            else:
                decision_text = str(decision_value) if decision_value else ""

            # P1: 记录输出快照和 token_usage（从 TraderAgent stash 的 _last_llm_response 提取）
            if recorder:
                _llm_response = getattr(self, "_last_llm_response", None)
                if _llm_response is not None:
                    recorder.record_llm_response(_llm_response, llm_duration_ms=_llm_duration_ms)
                else:
                    # response 不可达时，仅记录输出快照（无 token_usage）
                    from app.pro.models.execution_trace import OutputSnapshot
                    recorder.trace.output = OutputSnapshot(
                        output_raw_length=len(decision_text),
                        output_raw_preview=decision_text[:500] if decision_text else None,
                        output_parsed_keys=list(decision_value.keys()) if isinstance(decision_value, dict) else [],
                        output_parsed_success=decision_value.get("success", True) if isinstance(decision_value, dict) else True,
                        output_parsed_type="dict" if isinstance(decision_value, dict) else type(decision_value).__name__,
                    )
                    recorder.trace.llm_duration_ms = _llm_duration_ms
                recorder.record_parsed_output(decision_value if isinstance(decision_value, dict) else decision_text)

            # 🔥 合规校验（让错误显式化，不静默兜底）
            validation_warning = self._validate_trader_output(decision_text)

            # 🔥 P2: 执行断言（非阻塞）。TraderV2 继承 TraderAgent（非 ManagerAgent），
            # 直接调用 assertion_executor 单例（parsed=None，因为输出是 Markdown）。
            from app.core.config import settings as _settings
            assertion_violations_dump: list = []
            assertion_has_error = False
            assertion_error_count = 0
            if getattr(_settings, "AGENT_ASSERTION_ENABLED", True):
                try:
                    from core.agents.assertion_executor import assertion_executor
                    assertion_result = assertion_executor.run_assertions_sync(
                        agent_id=self.agent_id,
                        raw_text=decision_text,
                        parsed=None,
                    )
                    assertion_violations_dump = [v.model_dump() for v in assertion_result.violations]
                    assertion_has_error = assertion_result.has_error_violation
                    assertion_error_count = assertion_result.error_count
                    if assertion_violations_dump:
                        result["trader_plan_assertion_violations"] = assertion_violations_dump
                except Exception as assertion_exc:
                    logger.warning(f"⚠️ [TraderV2] 断言执行失败（不影响 agent）: {assertion_exc}")

            # 合并断言结果到 validation_status
            if validation_warning is None and not assertion_has_error:
                logger.info("✅ [TraderV2] 合规校验通过")
                result["trader_plan_validation_status"] = "passed"
                if recorder:
                    # 用 set_validation 更新内存对象，确保 finish() 的 insert 携带 validation
                    # （trader_v2 的 finish 在 finally 中晚于本调用，若用 record_trace_validation
                    #  的 DB update 会因文档未 insert 而 no-op，随后被 finish 覆盖为 None）
                    recorder.set_validation(
                        validation_status="passed",
                        validation_details={"assertion_violations": assertion_violations_dump},
                    )
            else:
                # 合规校验或断言 error 违规任一失败 → failed
                if validation_warning:
                    logger.warning(f"⚠️ [TraderV2] 合规校验发现问题: {validation_warning}")
                    logger.warning(f"⚠️ [TraderV2] 原始输出前 500 字符: {decision_text[:500]}")
                if assertion_has_error:
                    logger.warning(
                        f"⚠️ [TraderV2] 断言 error 违规 {assertion_error_count} 条"
                    )
                result["trader_plan_validation_status"] = "failed"
                if validation_warning:
                    result["trader_plan_validation_warning"] = validation_warning
                if assertion_has_error:
                    result["trader_plan_validation_error"] = (
                        f"断言违规: {assertion_error_count} 条 error"
                    )
                if recorder:
                    recorder.set_validation(
                        validation_status="failed",
                        validation_error=validation_warning or f"断言违规: {assertion_error_count} 条 error",
                        validation_details={
                            "raw_output_preview": decision_text[:500],
                            "assertion_violations": assertion_violations_dump,
                        },
                    )

            logger.info("✅ [TraderV2] 用户版研究简报生成完成")
            logger.info("=" * 80)
            return result

        except Exception as e:
            if recorder:
                recorder.record_error(e)
            raise
        finally:
            if recorder:
                recorder.finish()

    def _validate_trader_output(self, text: str) -> Optional[str]:
        """
        校验 LLM 输出的合规性和结构完整性。

        由于 trader_v2 输出是用户可读的 Markdown 简报（非结构化 JSON），
        本方法采用"合规术语扫描 + 结构完整性检查"的轻量模式，
        检测到违规时返回警告字符串（保留原输出），通过则返回 None。

        Args:
            text: LLM 输出的研究简报文本

        Returns:
            None: 校验通过
            str: 校验警告描述（含违规详情），用于显式上报
        """
        if not text or not text.strip():
            return "输出为空"

        warnings: List[str] = []

        # 1. 合规术语扫描（检测交易指令或市场观点术语）
        found_forbidden = [term for term in TRADER_FORBIDDEN_TERMS if term in text]
        if found_forbidden:
            warnings.append(f"检测到不合规术语: {found_forbidden}")

        # 2. 结构完整性检查（必备章节标记）
        missing_sections = [s for s in TRADER_REQUIRED_SECTIONS if s not in text]
        if missing_sections:
            warnings.append(f"缺少必备章节: {missing_sections}")

        if warnings:
            return "; ".join(warnings)
        return None

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        investment_plan: Dict[str, Any],
        all_reports: Dict[str, Any],
        historical_trades: Optional[List[Dict[str, Any]]],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 的实现）
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            investment_plan: 投资计划
            all_reports: 所有报告字典
            historical_trades: 历史交易记录
            state: 工作流状态
            
        Returns:
            用户提示词
        """
        logger.info("🔍 [TraderV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        company_name = ticker
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                company_name = self._get_company_name(ticker, market_info)
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        
        # 🆕 提取报告内容（如果是字典，取 content 字段）
        def extract_content(report):
            """从报告中提取纯文本内容"""
            if isinstance(report, dict):
                return report.get('content', str(report))
            return str(report) if report else ""
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        # 🔑 注意：风险审阅已在上游完成，本阶段负责整合呈现综合研究结论
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
            "current_date": analysis_date,
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            # 投资计划（转换为字符串）
            "investment_plan": extract_content(investment_plan) if investment_plan else "",
            # 🔑 可用的分析报告（不包括 risk_assessment）
            "market_report": extract_content(all_reports.get("market_report", "")),
            "fundamentals_report": extract_content(all_reports.get("fundamentals_report", "")),
            "news_report": extract_content(all_reports.get("news_report", "")),
            "sentiment_report": extract_content(all_reports.get("sentiment_report", "")),
            # 历史交易记录（转换为字符串）
            "historical_trades": "\n".join([str(trade) for trade in historical_trades[:3]]) if historical_trades else "",
        }
        
        # 🔑 添加其他报告到模板变量（不包括 risk_assessment）
        # 这些报告包括：sector_report, index_report, bull_report, bear_report 等
        excluded_keys = ["risk_assessment", "market_report", "fundamentals_report", "news_report", "sentiment_report"]
        for key, value in all_reports.items():
            if key not in excluded_keys:
                template_variables[f"report_{key}"] = extract_content(value)
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="trader_v2",
            agent_name="trader_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取研究整合员 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认用户提示词
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")

        summary_source = extract_content(all_reports.get("final_trade_decision", "")) or extract_content(all_reports.get("risk_management_decision", "")) or extract_content(investment_plan)
        prompt = f"""请为 {company_name}（{ticker}）生成用户版研究简报：

## 基本信息
- **股票代码**：{ticker}
- **公司名称**：{company_name}
- **分析日期**：{analysis_date}
- **货币单位**：{currency_name}（{currency_symbol}）

    ## 风险审阅后的综合研究结论

    {extract_content(investment_plan) if investment_plan else "无综合研究结论"}

    ## 一句话结论

    {summary_source or "请基于下述材料提炼一句话结论。"}

## 可用分析报告

### 1. 市场分析报告
{extract_content(all_reports.get("market_report", "")) or "无市场分析报告"}

### 2. 基本面分析报告
{extract_content(all_reports.get("fundamentals_report", "")) or "无基本面分析报告"}

### 3. 新闻分析报告
{extract_content(all_reports.get("news_report", "")) or "无新闻分析报告"}

### 4. 板块分析报告
{extract_content(all_reports.get("sector_report", "")) or "无板块分析报告"}

### 5. 大盘分析报告
{extract_content(all_reports.get("index_report", "")) or "无大盘分析报告"}

### 6. 乐观情景研究报告
{extract_content(all_reports.get("bull_report", "")) or "无乐观情景研究报告"}

### 7. 审慎情景研究报告
{extract_content(all_reports.get("bear_report", "")) or "无审慎情景研究报告"}

## 历史交易记录（如有）

{chr(10).join([str(trade) for trade in historical_trades[:3]]) if historical_trades else "无历史交易记录"}

## 任务要求

请基于上述综合研究结论和各类分析报告，生成用户可读的研究简报，优先包含以下结构：

1. **一句话结论**：用一句话概括当前研究判断。
2. **为什么这么看**：概括最关键的 2-4 条证据。
3. **当前判断的限制**：说明信息缺口、脆弱前提与结论边界。
4. **后续关注**：列出最值得继续跟踪的公开信号。
5. **资料边界说明**：如果报告未提供关键信息，必须明确指出。

**重要提示**：
- 不得输出买卖、加减仓、仓位比例、目标价、价格区间、风险关注与收益关注价位或执行节奏
- 可以解释价格、估值和财务数据如何影响研究判断，但不得扩展成操作建议
- 必须使用 {currency_name}（{currency_symbol}）作为货币单位
- 语言要让普通用户看得懂，不得补造材料外信息

**免责声明**：
本研究简报仅供信息参考，不构成投资建议或交易承诺。请结合自身情况独立判断。"""
        
        return prompt
    
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

