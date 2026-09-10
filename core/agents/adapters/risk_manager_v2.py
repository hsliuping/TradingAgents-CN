"""
风险评估师 v2.0

基于ManagerAgent基类实现的风险评估师
"""

import logging
from typing import Dict, Any, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from core.agents.manager import ManagerAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)


# ==================== Schema 契约定义 ====================
# 目的：让 LLM 从"自由决策输出格式"降级为"翻译一份预定义 schema"，
# 从源头消除格式不一致（参考桥水 Pat 的"规格驱动"思路）。
# 合规要求：action / investment_adjustment 只能取值 "乐观"/"审慎"/"中性"，
# 禁止使用"看涨/看跌/买入/卖出"等交易指令或市场观点术语。


class FinalTradeDecision(BaseModel):
    """最终研究结论 schema"""
    # 合规术语：乐观/审慎/中性（禁止使用"看涨/看跌/买入/卖出"等交易指令或市场观点术语）
    action: Literal["乐观", "审慎", "中性"]
    confidence: float = Field(ge=0, le=1)
    price_analysis_range: Optional[str] = None
    risk_reference_price: Optional[str] = None
    risk_exposure_ratio: Optional[str] = None
    reasoning: str = ""
    summary: str = ""
    risk_warning: str = ""


class RiskAssessmentOutput(BaseModel):
    """风险审阅结论 schema"""
    risk_level: Literal["低", "中", "高"]
    risk_score: float = Field(ge=0, le=1)
    reasoning: str
    key_risks: List[str] = Field(default_factory=list)
    risk_control: str = ""
    # 合规术语：乐观/审慎/中性（同 action 字段）
    investment_adjustment: Literal["乐观", "审慎", "中性"]
    final_trade_decision: FinalTradeDecision


# 风险审阅结论输出格式契约。
# 按硬约束"system prompt 必须将格式要求放在最前面"，此常量会被前置到
# _build_system_prompt 返回值的最前面，确保 LLM 优先看到格式与合规约束。
RISK_ASSESSMENT_SCHEMA_PROMPT = """【输出格式契约·必须严格遵守】
你的输出必须是一个 JSON 对象，包含以下字段。只输出 JSON，不要包裹在 markdown 代码块中，不要有任何额外文字。

{
  "risk_level": "低" | "中" | "高",
  "risk_score": 0.0-1.0 之间的浮点数,
  "reasoning": "评估结论（字符串）",
  "key_risks": ["核心风险1", "核心风险2"],
  "risk_control": "风控建议（字符串）",
  "investment_adjustment": "乐观" | "审慎" | "中性",
  "final_trade_decision": {
    "action": "乐观" | "审慎" | "中性",
    "confidence": 0.0-1.0 之间的浮点数,
    "price_analysis_range": "价格分析区间（可选，无则填 null）",
    "risk_reference_price": "风险控制参考价位（可选，无则填 null）",
    "risk_exposure_ratio": "风险敞口分析（可选，无则填 null）",
    "reasoning": "分析推理",
    "summary": "分析摘要",
    "risk_warning": "风险提示"
  }
}

【合规性约束·必须遵守】
1. investment_adjustment 与 action 字段只能取值 "乐观" / "审慎" / "中性"。
2. 禁止使用 "看涨" / "看跌" / "买入" / "卖出" / "加仓" / "减仓" / "持有" / "清仓" 等交易指令或市场观点术语。
3. "乐观/审慎/中性" 表达的是研究结论的倾向性，不构成任何交易建议或操作指令。
4. 禁止给出具体目标价或止损价，可输出 "价格分析区间" 并标注不确定性。
5. 禁止承诺收益或保证盈利，必须提示风险。
6. 所有结论必须基于已获取的数据，不得编造数据或指标。

字段约束：
- risk_level: 风险等级，只能是"低"/"中"/"高"三者之一
- risk_score: 0-1 之间的浮点数（不要写 0-100）
- investment_adjustment / action: 只能是"乐观"/"审慎"/"中性"
- confidence: 0-1 之间的浮点数（不要写 0-100）
- key_risks: 字符串数组，每项是一条核心风险
- 可选字段若无内容，填 null，不要省略字段名

输出必须是合法 JSON，不要在 JSON 前后添加任何文字或代码块标记。

"""

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class RiskManagerV2(ManagerAgent):
    """
    风险评估师 v2.0
    
    功能：
    - 主持风险稳健性审阅
    - 综合多方风险研究证据
    - 形成风险研究观察汇总（不构成投资建议）
    
    工作流程：
    1. 读取研究计划和各方风险观点
    2. 主持风险情景审阅（可选）
    3. 综合研判风险
    4. 生成风险研究观察报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("risk_manager_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "investment_plan": "...",
            "risky_opinion": "...",
            "safe_opinion": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="risk_manager_v2",
        name="风险评估师 v2.0",
        description="主持稳健性审阅，综合多方观点，形成风险审阅后的综合研究结论（输出研究观察，不构成投资建议）",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 管理者不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论", source="state", state_field="investment_plan", producer_hint="research_manager_v2"),
            AgentInput(name="risky_opinion", type="string", description="高弹性情景研究观察", required=False, source="state", state_field="risky_opinion", producer_hint="risky_analyst_v2"),
            AgentInput(name="safe_opinion", type="string", description="防御情景研究观察", required=False, source="state", state_field="safe_opinion", producer_hint="safe_analyst_v2"),
            AgentInput(name="neutral_opinion", type="string", description="基准情景研究观察", required=False, source="state", state_field="neutral_opinion", producer_hint="neutral_analyst_v2"),
        ],
        outputs=[
            AgentOutput(name="risk_assessment", type="string", description="稳健性审阅与风险审阅报告"),
            AgentOutput(name="risk_debate_state", type="dict", description="风险多情景研究状态（包含 judge_decision）"),
        ],
        requires_tools=False,
        output_field="risk_assessment",
        report_label="【风险审阅结论 v2】",
        workflow_stage="manager",
        growth_role="optimizer",
        growth_outputs=["risk_assessment", "risk_debate_state", "final_trade_decision"],
        memory_scope_hint="pattern",
        review_level="manual_required",
        growth_source_type="manager_decision",
        maturity_level="stable",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["assistant", "workflow", "agent"],
    )

    # 管理者类型
    manager_type = "risk"
    
    # 输出字段名
    output_field = "risk_assessment"
    
    # 是否需要辩论
    enable_debate = True

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）
        
        Args:
            state: 工作流状态（用于提取模板变量）
        
        Returns:
            系统提示词
        """
        logger.info("🔍 [RiskManagerV2] 开始构建系统提示词")
        
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
            agent_type="managers_v2",
            agent_name="risk_manager_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # ✅ 关键：指定获取系统提示词（包含output_format）
        )

        if prompt:
            # 🔥 按硬约束"system prompt 必须将格式要求放在最前面"，
            # 将 schema 契约前置到 prompt 最前面，确保 LLM 优先看到格式与合规约束，
            # 不依赖数据库迁移即可立即生效。
            prompt = RISK_ASSESSMENT_SCHEMA_PROMPT + prompt
            logger.info(f"📝 系统提示词长度: {len(prompt)} 字符（含 schema 契约）")
            logger.info(f"📝 系统提示词前500字符:\n{prompt[:500]}...")

            # 检查是否包含输出格式要求
            if "output_format" in prompt.lower() or "JSON格式" in prompt or "json" in prompt.lower():
                logger.info("✅ 系统提示词包含【输出格式要求】")
            else:
                logger.warning("⚠️ 系统提示词可能不包含【输出格式要求】（可能使用旧版提示词）")

            logger.debug(f"✅ 从模板系统获取风险评估师系统提示词")
            return prompt

        logger.warning("⚠️ 从模板系统获取系统提示词失败，使用默认提示词")

        # 默认提示词（合规版本）— 同样前置 schema 契约，保证 fallback 路径也受约束
        return RISK_ASSESSMENT_SCHEMA_PROMPT + """你是一位风险评估师，负责综合各方稳健性审阅并形成风险审阅结论。

    **分析风格**: 客观、克制、以稳健性为核心，强调判断边界、约束条件、失效触发与后续观察。

**核心职责**:
    1. 综合高弹性、防御、基准情景三方的稳健性审阅意见。
    2. 识别当前研究结论的关键风险、脆弱点与信息缺口。
    3. 说明哪些条件会支持结论上修、维持或下修。
    4. 形成风险审阅结论与后续观察重点。
    5. 给出判断约束，而不是具体操作建议。

**分析原则**:
    - 客观综合三方观点，基于证据说明当前结论是否足够稳健。
    - 不输出买卖、加减仓、仓位比例、目标价、价格区间、止损止盈或执行节奏。
    - 可以说明风险来源、观察信号与结论失效条件，但不得扩展为操作建议。
    - 所有结论必须严格基于提供材料，不得补造信息。
    - 使用中文输出。

**工具使用指导**:

    基于提供的风险观点与综合研究结论进行风险审阅审阅。
    从稳健性角度评估所有风险信息。

**免责声明**：
    本风险审阅结论仅供信息参考，不构成投资建议或交易承诺。请结合自身情况独立判断。"""

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
            inputs: 输入数据（投资计划、各方观点等）
            debate_summary: 辩论总结
            state: 当前状态
            
        Returns:
            用户提示词
        """
        logger.info("🔍 [RiskManagerV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        logger.info(f"📝 输入字段: {list(inputs.keys())}")
        
        # 检查各方风险观点
        risky_opinion = inputs.get("risky_opinion", "")
        safe_opinion = inputs.get("safe_opinion", "")
        neutral_opinion = inputs.get("neutral_opinion", "")
        investment_plan = inputs.get("investment_plan", "")
        
        # 转换为字符串（如果不是）
        risky_opinion_str = str(risky_opinion) if risky_opinion else ""
        safe_opinion_str = str(safe_opinion) if safe_opinion else ""
        neutral_opinion_str = str(neutral_opinion) if neutral_opinion else ""
        investment_plan_str = str(investment_plan) if investment_plan else ""
        
        logger.info(f"🔥 高弹性情景观点类型: {type(risky_opinion)}, 长度: {len(risky_opinion_str)} 字符")
        logger.info(f"🛡️ 防御情景观点类型: {type(safe_opinion)}, 长度: {len(safe_opinion_str)} 字符")
        logger.info(f"⚖️ 基准情景观点类型: {type(neutral_opinion)}, 长度: {len(neutral_opinion_str)} 字符")
        logger.info(f"📋 投资计划类型: {type(investment_plan)}, 长度: {len(investment_plan_str)} 字符")
        
        # 获取公司名称
        company_name = self._get_company_name(ticker, state)
        logger.info(f"🏢 公司名称: {company_name}")
        
        # 🆕 提取报告内容（如果是字典，取 content 字段）
        def extract_content(report):
            """从报告中提取纯文本内容"""
            if isinstance(report, dict):
                return report.get('content', str(report))
            return str(report) if report else ""
        
        risky_opinion_content = extract_content(inputs.get("risky_opinion"))
        safe_opinion_content = extract_content(inputs.get("safe_opinion"))
        neutral_opinion_content = extract_content(inputs.get("neutral_opinion"))
        investment_plan_content = extract_content(inputs.get("investment_plan"))
        
        logger.info(f"🔥 高弹性情景观点内容长度: {len(risky_opinion_content)} 字符")
        logger.info(f"🛡️ 防御情景观点内容长度: {len(safe_opinion_content)} 字符")
        logger.info(f"⚖️ 基准情景观点内容长度: {len(neutral_opinion_content)} 字符")
        logger.info(f"📋 投资计划内容长度: {len(investment_plan_content)} 字符")
        
        # 准备模板变量
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
            "investment_plan": investment_plan_content,  # ✅ 只传递内容，不传递字典
            "risky_opinion": risky_opinion_content,  # ✅ 只传递内容，不传递字典
            "safe_opinion": safe_opinion_content,  # ✅ 只传递内容，不传递字典
            "neutral_opinion": neutral_opinion_content,  # ✅ 只传递内容，不传递字典
            "debate_summary": debate_summary or "",
        }
        
        # 添加其他输入到模板变量
        for key, value in inputs.items():
            if key not in ["investment_plan", "risky_opinion", "safe_opinion", "neutral_opinion"]:
                template_variables[key] = extract_content(value) if value else ""
        
        # 使用基类的通用方法获取用户提示词（基类会自动从 state 中提取系统变量）
        prompt = self._get_prompt_from_template(
            agent_type="managers_v2",
            agent_name="risk_manager_v2",
            variables=template_variables,
            state=state,  # 🆕 传递 state，基类会自动提取系统变量
            context=state,
            fallback_prompt=None,
            prompt_type="user"  # 🆕 指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取风险评估师用户提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：使用默认用户提示词
        logger.info("⚠️ 使用降级用户提示词")
        return f"""请基于 {company_name}（{ticker}）的综合研究结论与三方稳健性审阅意见，形成风险审阅结论：

📊 **基本信息**：
- 股票代码：{ticker}
- 公司名称：{company_name}
- 分析日期：{analysis_date}

    【风险审阅后的综合研究结论】
{investment_plan_content}

【高弹性情景研究观察】
{risky_opinion_content}

【防御情景研究观察】
{safe_opinion_content}

【基准情景研究观察】
{neutral_opinion_content}

【多情景研究总结】
{debate_summary or ''}

请基于以上信息：

1. 提炼当前研究结论是否足够稳健。
2. 说明关键风险、判断边界、结论上修或下修的触发条件。
3. 给出后续观察事项与资料缺口。
4. 明确不要直接给出具体操作建议、仓位安排、目标价、价格区间、止损止盈或执行节奏。

输出目标是形成风险审阅结论，而不是具体操作建议。"""

    def _get_required_inputs(self) -> List[str]:
        """
        获取需要的输入列表
        
        Returns:
            输入字段名列表
        """
        return [
            "investment_plan",
            "risky_opinion",
            "safe_opinion",
            "neutral_opinion"
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

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行风险管理决策（含 schema 校验）

        重写父类方法以添加 risk_debate_state 和 final_trade_decision 输出。
        本方法在父类输出后立即用 RiskAssessmentOutput schema 校验 LLM 输出：
        - 校验通过：把 dict 序列化为 JSON 字符串存入 risk_assessment（下游消费者不变），
          并直接从 validated dict 取 final_trade_decision（跳过 _extract_final_trade_decision）。
        - 校验失败：保留原始文本作为 risk_assessment，同时写入
          risk_assessment_validation_status / risk_assessment_validation_error 字段显式上报，
          final_trade_decision 走 _extract_final_trade_decision 兜底逻辑兼容。
        """
        import json

        # 调用父类方法获取基本输出
        result = super().execute(state)

        # 🛡️ Q1: 父类执行失败（超时/空响应等异常包装 dict）时直接透传，
        # 不做 schema 校验与文本化——否则 {'error','success':False} 会被 _extract_text
        # 字符串化后写回 state，最终以裸 dict 形态混入报告（见 engine/report_formatter 的失败形态处理）
        _raw_output = result.get(self.output_field)
        if isinstance(_raw_output, dict) and (
            _raw_output.get("success") is False
            or (
                _raw_output.get("success") is True
                and not str(_raw_output.get("content") or "").strip()
            )
        ):
            logger.warning(
                f"⚠️ [RiskManagerV2] 父类执行失败（{_raw_output.get('error')}），"
                f"跳过 schema 校验，失败形态直接透传给下游渲染层"
            )
            return result

        # 提取风险评估原始文本
        risk_assessment_raw = result.get(self.output_field)
        risk_assessment_text = self._extract_text(risk_assessment_raw)

        # 🔥 新增：schema 校验（让错误显式化，不再静默兜底）
        validated_dict, validation_error = self._validate_risk_assessment(risk_assessment_text)

        if validation_error is None:
            # ✅ 校验通过：存储为 JSON 字符串（保持 type=string 兼容下游消费者）
            logger.info("✅ [RiskManagerV2] schema 校验通过")
            result[self.output_field] = json.dumps(validated_dict, ensure_ascii=False)
            # 直接从 validated dict 取 final_trade_decision（schema 已保证字段存在且合规）
            final_trade_decision_dict = validated_dict.get("final_trade_decision", {})
            final_trade_decision_markdown = self._format_final_trade_decision_markdown(final_trade_decision_dict)
            # risk_score 在 JSON 顶层，挂到 final_trade_decision 便于前端展示
            final_trade_decision = {
                **final_trade_decision_dict,
                "risk_score": validated_dict.get("risk_score"),
                "content": final_trade_decision_markdown,
            }

            # 🔥 P2: 执行断言（非阻塞），合并结果到 validation_status
            assertion_result = self._run_assertions(
                raw_text=risk_assessment_text, parsed=validated_dict
            )
            assertion_violations_dump = [v.model_dump() for v in assertion_result.violations]
            if assertion_violations_dump:
                result["risk_assessment_assertion_violations"] = assertion_violations_dump

            if assertion_result.has_error_violation:
                # error 级别断言违规 → 降级 validation_status 为 failed
                logger.warning(
                    f"⚠️ [RiskManagerV2] 断言 error 违规 {assertion_result.error_count} 条，降级 validation_status"
                )
                result["risk_assessment_validation_status"] = "failed"
                result["risk_assessment_validation_error"] = (
                    f"断言违规: {assertion_result.error_count} 条 error"
                )
                self._record_trace_validation(
                    validation_status="failed",
                    validation_error=result["risk_assessment_validation_error"],
                    validation_details={
                        "risk_level": validated_dict.get("risk_level"),
                        "risk_score": validated_dict.get("risk_score"),
                        "assertion_violations": assertion_violations_dump,
                    },
                )
            else:
                # 仅 warning 或无违规 → 保持 passed
                result["risk_assessment_validation_status"] = "passed"
                self._record_trace_validation(
                    validation_status="passed",
                    validation_details={
                        "risk_level": validated_dict.get("risk_level"),
                        "risk_score": validated_dict.get("risk_score"),
                        "assertion_violations": assertion_violations_dump,
                    },
                )
        else:
            # ❌ 校验失败：显式上报（不静默兜底），保留原始输出供排查
            logger.error(f"❌ [RiskManagerV2] schema 校验失败: {validation_error}")
            logger.error(f"❌ [RiskManagerV2] 原始输出前 500 字符: {risk_assessment_text[:500]}")
            result[self.output_field] = risk_assessment_text
            result["risk_assessment_validation_status"] = "failed"
            result["risk_assessment_validation_error"] = validation_error

            # 🔥 P2: 校验失败时也执行断言（用于累积命中统计，但不改变已 failed 的状态）
            assertion_result = self._run_assertions(
                raw_text=risk_assessment_text, parsed=None
            )
            assertion_violations_dump = [v.model_dump() for v in assertion_result.violations]
            self._record_trace_validation(
                validation_status="failed",
                validation_error=validation_error,
                validation_details={
                    "raw_output_preview": risk_assessment_text[:500],
                    "assertion_violations": assertion_violations_dump,
                },
            )
            # 走原有 _extract_final_trade_decision 兜底逻辑（兼容历史 LLM 输出格式）
            final_trade_decision_dict = self._extract_final_trade_decision(risk_assessment_text)
            final_trade_decision_markdown = self._format_final_trade_decision_markdown(final_trade_decision_dict)
            final_trade_decision = {
                **final_trade_decision_dict,
                "content": final_trade_decision_markdown,
            }

        # 从 state 中获取现有的 risk_debate_state（保持原逻辑不变）
        existing_risk_state = state.get("risk_debate_state", {})

        # 构建新的 risk_debate_state，包含 judge_decision
        new_risk_state = {
            "judge_decision": risk_assessment_text,  # ✅ 关键：保留原始 LLM 输出文本
            "history": existing_risk_state.get("history", ""),
            "risky_history": existing_risk_state.get("risky_history", ""),
            "safe_history": existing_risk_state.get("safe_history", ""),
            "neutral_history": existing_risk_state.get("neutral_history", ""),
            "latest_speaker": "Judge",
            "current_risky_response": existing_risk_state.get("current_risky_response", ""),
            "current_safe_response": existing_risk_state.get("current_safe_response", ""),
            "current_neutral_response": existing_risk_state.get("current_neutral_response", ""),
            "count": existing_risk_state.get("count", 0),
        }

        return {
            **result,
            "risk_debate_state": new_risk_state,
            "final_trade_decision": final_trade_decision,  # ✅ 最终研究结论（含字典字段 + Markdown content）
        }

    def _validate_risk_assessment(self, text: str) -> tuple:
        """
        校验 LLM 输出是否符合 RiskAssessmentOutput schema。

        Args:
            text: LLM 输出的风险评估文本（可能是纯 JSON、markdown 代码块包裹的 JSON、或纯文本）

        Returns:
            (validated_dict, None): 校验通过，dict 可直接序列化为 JSON
            (None, error_msg): 校验失败，error_msg 描述失败原因
        """
        import json
        import re

        if not text or not text.strip():
            return None, "输出为空"

        # 兼容 markdown 代码块包裹的 JSON（```json ... ``` 或 ``` ... ```）
        text = text.strip()
        json_str = text
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()

        # 解析 JSON
        try:
            json_obj = json.loads(json_str)
        except json.JSONDecodeError as e:
            return None, f"JSON 解析失败: {e}"

        if not isinstance(json_obj, dict):
            return None, f"JSON 顶层不是对象，实际类型: {type(json_obj).__name__}"

        # pydantic schema 校验（含合规术语枚举约束、数值范围约束）
        try:
            validated = RiskAssessmentOutput(**json_obj)
            return validated.model_dump(), None
        except ValidationError as e:
            return None, f"Schema 校验失败: {e}"

    def _extract_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for k in ("content", "markdown", "text", "message", "report"):
                v = value.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return str(value).strip()

    def _extract_final_trade_decision(self, risk_assessment_text: str) -> Dict[str, Any]:
        """
        从 LLM 输出的 JSON 中提取 final_trade_decision 字段

        Args:
            risk_assessment_text: LLM 输出的风险评估文本（可能包含 JSON）

        Returns:
            final_trade_decision 字典，如果提取失败则返回默认值
        """
        import json
        import re

        if not risk_assessment_text:
            logger.warning("⚠️ [RiskManagerV2] risk_assessment_text 为空，无法提取 final_trade_decision")
            return self._get_default_final_decision()

        try:
            # 尝试提取 JSON 代码块
            json_obj = None

            if "```json" in risk_assessment_text:
                json_match = re.search(r'```json\s*(.*?)\s*```', risk_assessment_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                    json_obj = json.loads(json_str)
            elif risk_assessment_text.strip().startswith("{"):
                json_obj = json.loads(risk_assessment_text)

            if json_obj and isinstance(json_obj, dict):
                # 提取 final_trade_decision 字段
                final_decision = json_obj.get("final_trade_decision", {})

                if final_decision and isinstance(final_decision, dict):
                    # 确保 confidence 是 0-1 的小数（前端期望）
                    confidence = final_decision.get("confidence", 0.5)
                    if isinstance(confidence, (int, float)) and confidence > 1:
                        # 如果 LLM 返回的是 0-100 的整数，转换为 0-1 的小数
                        final_decision["confidence"] = confidence / 100.0
                    
                    # 🔥🔥🔥 关键修复：从顶层 JSON 中提取 risk_score 并添加到 final_decision 中
                    # risk_score 在 JSON 的顶层，不在 final_trade_decision 中
                    risk_score = json_obj.get("risk_score")
                    if risk_score is not None:
                        # 确保 risk_score 是 0-1 范围的浮点数
                        if isinstance(risk_score, (int, float)):
                            if risk_score > 1:
                                # 如果是 0-100 的整数，转换为 0-1 的小数
                                risk_score = risk_score / 100.0
                            final_decision["risk_score"] = float(risk_score)
                            logger.info(f"✅✅✅ [RiskManagerV2] 从顶层 JSON 提取 risk_score 并添加到 final_trade_decision: {final_decision['risk_score']}")
                        else:
                            logger.warning(f"⚠️ [RiskManagerV2] risk_score 格式不正确: {risk_score}")
                    else:
                        logger.warning("⚠️ [RiskManagerV2] 顶层 JSON 中没有 risk_score 字段")
                    
                    # 🔥 修复：优先从 action 字段获取，如果没有则从 analysis_view 字段获取
                    action = final_decision.get("action")
                    if not action:
                        # 如果 action 不存在，尝试从 analysis_view 获取
                        analysis_view = final_decision.get("analysis_view", "")
                        if analysis_view:
                            # analysis_view 可能是旧术语（看涨/看跌/中性）或合规术语，直接使用后由下方 action_mapping 统一映射
                            action = analysis_view
                            final_decision["action"] = action
                            logger.info(f"📝 [RiskManagerV2] 从 analysis_view 字段提取 action: {action}")
                    
                    if action:
                        # 合规术语映射：统一映射到"乐观/审慎/中性"
                        # 禁止使用"看涨/看跌/买入/卖出"等交易指令或市场观点术语
                        action_mapping = {
                            "买入": "乐观",
                            "卖出": "审慎",
                            "持有": "中性",
                            "加仓": "乐观",
                            "减仓": "审慎",
                            "清仓": "审慎",
                            "看涨": "乐观",  # 兼容 LLM 可能仍输出旧术语
                            "看跌": "审慎",
                            "乐观": "乐观",  # 已是合规术语，保持不变
                            "审慎": "审慎",
                            "中性": "中性",
                        }
                        # 确保使用合规研究结论术语
                        if action in action_mapping:
                            final_decision["action"] = action_mapping[action]
                            logger.info(f"📝 [RiskManagerV2] 映射 action: {action} -> {action_mapping[action]}")
                        # 如果已经是合规术语（乐观/审慎/中性），保持不变
                    else:
                        # 如果都没有，使用默认值
                        final_decision["action"] = "中性"
                        logger.warning("⚠️ [RiskManagerV2] final_trade_decision 中没有 action 或 analysis_view 字段，使用默认值'中性'")
                    
                    logger.info(f"✅ [RiskManagerV2] 成功提取 final_trade_decision: action={final_decision.get('action')}, confidence={final_decision.get('confidence')}, risk_score={final_decision.get('risk_score')}")
                    return final_decision
                else:
                    # 如果没有 final_trade_decision 字段，从顶层字段构建
                    logger.warning("⚠️ [RiskManagerV2] JSON 中没有 final_trade_decision 字段，从顶层字段构建")
                    # confidence 返回 0-1 的小数（前端期望）
                    risk_score = json_obj.get("risk_score", 0.5)
                    investment_adjustment = json_obj.get("investment_adjustment", "中性")
                    # 合规术语映射：统一映射到"乐观/审慎/中性"
                    action_mapping = {
                        "买入": "乐观",
                        "卖出": "审慎",
                        "持有": "中性",
                        "看涨": "乐观",
                        "看跌": "审慎",
                        "乐观": "乐观",
                        "审慎": "审慎",
                        "中性": "中性",
                    }
                    market_view = action_mapping.get(investment_adjustment, investment_adjustment)
                    return {
                        "action": market_view,  # 使用合规研究结论术语
                        "confidence": 1.0 - risk_score if risk_score <= 1 else (100 - risk_score) / 100.0,
                        "price_analysis_range": None,
                        "risk_reference_price": None,
                        "risk_exposure_ratio": "5%",
                        "reasoning": json_obj.get("reasoning", ""),
                        "summary": f"风险等级: {json_obj.get('risk_level', '中')}",
                        "risk_warning": ", ".join(json_obj.get("key_risks", [])[:3]) if json_obj.get("key_risks") else ""
                    }
            else:
                logger.warning("⚠️ [RiskManagerV2] 无法解析 JSON，返回默认 final_trade_decision")
                return self._get_default_final_decision()

        except Exception as e:
            logger.warning(f"⚠️ [RiskManagerV2] 提取 final_trade_decision 失败: {e}")
            return self._get_default_final_decision()

    def _get_default_final_decision(self) -> Dict[str, Any]:
        """返回默认的 final_trade_decision（合规版本）"""
        return {
            "action": "中性",  # 合规研究结论术语
            "confidence": 0.5,  # 0-1 的小数（前端期望）
            "price_analysis_range": None,
            "risk_reference_price": None,
            "risk_exposure_ratio": "5%",
            "reasoning": "风险评估数据不足，建议谨慎观望",
            "summary": "数据不足，建议观望",
            "risk_warning": "请等待更多分析数据"
        }
    
    def _format_final_trade_decision_markdown(self, decision: Dict[str, Any]) -> str:
        """
        将 final_trade_decision 字典格式化为 Markdown 格式
        
        Args:
            decision: final_trade_decision 字典
            
        Returns:
            格式化的 Markdown 字符串，每个字段分行显示
        """
        if not decision:
            return "## 最终研究结论\n\n数据不足，无法生成研究结论。"
        
        lines = ["## 最终研究结论\n"]
        
        # 字段映射（中文名称，合规版本）
        field_names = {
            "action": "**研究结论倾向**",
            "confidence": "**信心度**",
            "price_analysis_range": "**价格分析区间**",
            "risk_reference_price": "**风险控制参考价位**",
            "risk_exposure_ratio": "**风险敞口分析**",
            "reasoning": "**分析推理**",
            "summary": "**分析摘要**",
            "risk_warning": "**风险提示**"
        }

        # 格式化每个字段
        action = decision.get("action", "")
        if action:
            # 合规术语映射：统一映射到"乐观/审慎/中性"，禁止使用"看涨/看跌/买入/卖出"等术语
            action_mapping = {
                "买入": "乐观",
                "卖出": "审慎",
                "持有": "中性",
                "看涨": "乐观",
                "看跌": "审慎",
                "乐观": "乐观",
                "审慎": "审慎",
                "中性": "中性",
            }
            market_view = action_mapping.get(action, action)
            lines.append(f"{field_names.get('action', '**研究结论倾向**')}: {market_view}（仅供参考，不构成交易建议）")
        
        confidence = decision.get("confidence")
        if confidence is not None:
            # 如果是 0-1 的小数，转换为百分比显示
            if isinstance(confidence, float) and 0 <= confidence <= 1:
                confidence_display = f"{confidence * 100:.0f}%"
            elif isinstance(confidence, (int, float)) and confidence > 1:
                # 如果是 0-100 的整数，直接显示百分比
                confidence_display = f"{int(confidence)}%"
            else:
                confidence_display = str(confidence)
            lines.append(f"{field_names.get('confidence', '**信心度**')}: {confidence_display}")
        
        price_analysis_range = decision.get("price_analysis_range") or decision.get("target_price")
        if price_analysis_range is not None:
            lines.append(f"{field_names.get('price_analysis_range', '**价格分析区间**')}: ¥{price_analysis_range}（仅供参考，不构成价格预测）")

        risk_reference_price = decision.get("risk_reference_price") or decision.get("stop_loss")
        if risk_reference_price is not None:
            lines.append(f"{field_names.get('risk_reference_price', '**风险控制参考价位**')}: ¥{risk_reference_price}（仅供参考，不构成交易建议）")

        risk_exposure_ratio = decision.get("risk_exposure_ratio") or decision.get("position_ratio")
        if risk_exposure_ratio:
            lines.append(f"{field_names.get('risk_exposure_ratio', '**风险敞口分析**')}: {risk_exposure_ratio}（仅供参考，不构成交易建议）")
        
        reasoning = decision.get("reasoning")
        if reasoning:
            lines.append(f"\n{field_names.get('reasoning', '**分析推理**')}:\n\n{reasoning}")
        
        summary = decision.get("summary")
        if summary:
            lines.append(f"\n{field_names.get('summary', '**分析摘要**')}:\n\n{summary}")
        
        risk_warning = decision.get("risk_warning")
        if risk_warning:
            lines.append(f"\n{field_names.get('risk_warning', '**风险提示**')}:\n\n{risk_warning}")
        
        # 添加免责声明
        lines.append("\n**免责声明**：")
        lines.append("本分析报告仅供参考，不构成交易建议。所有市场观点、价格区间、风险评估均为分析参考，")
        lines.append("不构成具体操作建议。投资有风险，决策需谨慎。投资者应根据自身情况，结合")
        lines.append("专业投资顾问意见，独立做出投资判断。")
        
        return "\n".join(lines)
