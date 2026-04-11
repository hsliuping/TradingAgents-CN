"""
风险管理者 v2.0

基于ManagerAgent基类实现的风险管理者
"""

import logging
from typing import Dict, Any, List, Optional

from core.agents.manager import ManagerAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

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
    风险管理者 v2.0
    
    功能：
    - 主持风险辩论
    - 综合多方风险观点
    - 形成最终风险评估
    
    工作流程：
    1. 读取投资计划和各方风险观点
    2. 主持风险辩论（可选）
    3. 综合研判风险
    4. 生成风险评估报告
    
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
        name="风险管理者 v2.0",
        description="主持风险辩论，综合多方观点，形成最终风险评估",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 管理者不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="投资计划"),
            AgentInput(name="risky_opinion", type="string", description="激进风险观点", required=False),
            AgentInput(name="safe_opinion", type="string", description="保守风险观点", required=False),
            AgentInput(name="neutral_opinion", type="string", description="中性风险观点", required=False),
        ],
        outputs=[
            AgentOutput(name="risk_assessment", type="string", description="风险评估报告"),
            AgentOutput(name="risk_debate_state", type="dict", description="风险辩论状态（包含 judge_decision）"),
        ],
        requires_tools=False,
        output_field="risk_assessment",
        report_label="【风险评估 v2】",
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
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
        logger.info(f"📝 系统提示词前500字符:\n{prompt[:500]}...")
        
        # 检查是否包含输出格式要求
        if "output_format" in prompt.lower() or "JSON格式" in prompt or "json" in prompt.lower():
            logger.info("✅ 系统提示词包含【输出格式要求】")
        else:
            logger.warning("⚠️ 系统提示词可能不包含【输出格式要求】（可能使用旧版提示词）")
        
        if prompt:
            logger.debug(f"✅ 从模板系统获取风险管理者系统提示词")
            return prompt
        
        # 默认提示词（合规版本）
        return """你是一位中性的风险治理经理，负责把研究结论与风险分歧整理成最终的综合研究结论。

    **分析风格**: 客观、克制、基于证据，强调关键风险、信息缺口与判断调整条件。

    **核心职责**:
    1. 综合激进、保守、中性三方风险观点，识别最关键的风险分歧。
    2. 判断哪些风险已经较明确，哪些风险仍需继续验证。
    3. 形成风险等级、关键风险清单、研究谨慎度要求与后续观察重点。
    4. 在兼容字段 `final_trade_decision` 中输出“综合研究结论”，而不是交易决策。

    **分析原则**:
    - 不得输出交易建议、执行方案、目标价、止损止盈、仓位比例或价格触发动作。
    - 风险治理建议只能表达为研究谨慎度、验证要求与后续观察事项。
    - 所有结论必须严格基于提供内容，不得补造信息。
    - 使用中文输出。

    **免责声明**：
    本研究结论仅供信息参考，不构成交易建议或投资承诺。请结合自身情况独立判断。"""

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
        
        logger.info(f"🔥 激进观点类型: {type(risky_opinion)}, 长度: {len(risky_opinion_str)} 字符")
        logger.info(f"🛡️ 保守观点类型: {type(safe_opinion)}, 长度: {len(safe_opinion_str)} 字符")
        logger.info(f"⚖️ 中性观点类型: {type(neutral_opinion)}, 长度: {len(neutral_opinion_str)} 字符")
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
        
        logger.info(f"🔥 激进观点内容长度: {len(risky_opinion_content)} 字符")
        logger.info(f"🛡️ 保守观点内容长度: {len(safe_opinion_content)} 字符")
        logger.info(f"⚖️ 中性观点内容长度: {len(neutral_opinion_content)} 字符")
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
            logger.info(f"✅ 从模板系统获取风险管理者用户提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：使用默认用户提示词（优化后：只包含任务描述和数据，不包含格式要求）
        logger.info("⚠️ 使用降级用户提示词")
        return f"""请综合分析 {company_name}（{ticker}）的研究风险与判断稳健性：

📊 **基本信息**：
- 股票代码：{ticker}
- 公司名称：{company_name}
- 分析日期：{analysis_date}

【投资计划】
{investment_plan_content}

【激进风险观点】
{risky_opinion_content}

【保守风险观点】
{safe_opinion_content}

【中性风险观点】
{neutral_opinion_content}

【风险辩论总结】
{debate_summary or ''}

请基于以上信息输出风险治理结论，不得给出交易建议。

**任务要求**：
- 给出风险等级与关键风险来源，说明这些风险为什么重要。
- 区分哪些风险已有较充分证据，哪些仍存在明显信息缺口。
- 给出研究谨慎度要求、判断调整条件与后续观察事项。
- 在 `final_trade_decision` 字段中继续输出兼容对象，但其语义必须是“综合研究结论”，不是交易决策。

**严格禁止**：
- 不得输出价格区间、关键价位、风险控制参考价、仓位比例、执行策略或动作建议。
- 不得把风险治理写成买卖、加减仓、止损止盈方案。

**输出格式**：
请使用 JSON 输出，字段如下：
```json
{{
    "risk_level": "低|中|高",
    "risk_score": 0.0-1.0,
    "reasoning": "200-500字，说明风险评估逻辑与关键分歧",
    "key_risks": ["关键风险1", "关键风险2", "关键风险3"],
    "risk_control": "研究谨慎度与验证要求，不能包含执行动作",
    "investment_adjustment": "研究判断调整原则，不能包含交易动作",
    "final_trade_decision": {{
        "analysis_view": "看涨|中性|看跌",
        "confidence": 0-100,
        "summary": "50-120字的综合研究摘要",
        "reasoning": "200-500字，说明综合研究判断为何成立",
        "core_evidence": ["核心依据1", "核心依据2", "核心依据3"],
        "uncertainties": ["关键不确定性1", "关键不确定性2"],
        "invalidation_conditions": ["判断下修或失效前提1", "判断下修或失效前提2"],
        "watch_items": ["后续观察事项1", "后续观察事项2", "后续观察事项3"],
        "risk_warning": "100字以内的关键风险提示"
    }}
}}
```
"""

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
        执行风险管理决策

        重写父类方法以添加 risk_debate_state 和 final_trade_decision 输出
        """
        import json
        import re

        # 调用父类方法获取基本输出
        result = super().execute(state)

        # 提取风险评估内容
        risk_assessment_raw = result.get(self.output_field)
        risk_assessment_text = self._extract_text(risk_assessment_raw)

        # 🔥 新增：从 LLM 输出中提取 final_trade_decision
        final_trade_decision_dict = self._extract_final_trade_decision(risk_assessment_text)
        
        # 🔥 新增：将 final_trade_decision 格式化为 Markdown
        final_trade_decision_markdown = self._format_final_trade_decision_markdown(final_trade_decision_dict)
        
        # 构建包含原始字典和格式化 Markdown 的结构
        final_trade_decision = {
            **final_trade_decision_dict,  # 保留原始字典字段（用于程序处理）
            "content": final_trade_decision_markdown  # 添加格式化的 Markdown 内容（用于前端显示）
        }

        # 从 state 中获取现有的 risk_debate_state（如果有）
        existing_risk_state = state.get("risk_debate_state", {})
        
        # 构建新的 risk_debate_state，包含 judge_decision
        new_risk_state = {
            "judge_decision": risk_assessment_text,  # ✅ 关键：添加 judge_decision 字段
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

        # 🔥 修改：输出 final_trade_decision（由 LLM 生成，不再是拼接）
        return {
            **result,
            "risk_debate_state": new_risk_state,
            "final_trade_decision": final_trade_decision,  # ✅ 新增：最终分析结果（包含字典和 Markdown）
        }
    
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
                            # analysis_view 已经是市场观点术语（看涨/看跌/中性），直接使用
                            action = analysis_view
                            final_decision["action"] = action
                            logger.info(f"📝 [RiskManagerV2] 从 analysis_view 字段提取 action: {action}")
                    
                    if action:
                        action_mapping = {
                            "买入": "看涨",
                            "卖出": "看跌",
                            "持有": "中性",
                            "加仓": "看涨",
                            "减仓": "看跌",
                            "清仓": "看跌"
                        }
                        # 确保使用市场观点术语
                        if action in action_mapping:
                            final_decision["action"] = action_mapping[action]
                            logger.info(f"📝 [RiskManagerV2] 映射 action: {action} -> {action_mapping[action]}")
                        # 如果已经是市场观点（看涨/看跌/中性），保持不变
                    else:
                        # 如果都没有，使用默认值
                        final_decision["action"] = "中性"
                        logger.warning("⚠️ [RiskManagerV2] final_trade_decision 中没有 action 或 analysis_view 字段，使用默认值'中性'")

                    final_decision["analysis_view"] = final_decision.get("analysis_view") or final_decision.get("action", "中性")
                    for legacy_field in (
                        "target_price",
                        "price_analysis_range",
                        "risk_reference_price",
                        "risk_control_reference",
                        "stop_loss",
                        "risk_exposure_ratio",
                        "position_ratio",
                    ):
                        final_decision.pop(legacy_field, None)
                    
                    logger.info(f"✅ [RiskManagerV2] 成功提取 final_trade_decision: action={final_decision.get('action')}, confidence={final_decision.get('confidence')}, risk_score={final_decision.get('risk_score')}")
                    return final_decision
                else:
                    # 如果没有 final_trade_decision 字段，从顶层字段构建
                    logger.warning("⚠️ [RiskManagerV2] JSON 中没有 final_trade_decision 字段，从顶层字段构建")
                    # confidence 返回 0-1 的小数（前端期望）
                    risk_score = json_obj.get("risk_score", 0.5)
                    # 确保使用市场观点术语
                    investment_adjustment = json_obj.get("investment_adjustment", "中性")
                    action_mapping = {
                        "买入": "看涨",
                        "卖出": "看跌",
                        "持有": "中性"
                    }
                    market_view = action_mapping.get(investment_adjustment, investment_adjustment)
                    return {
                        "action": market_view,  # 使用市场观点术语
                        "analysis_view": market_view,
                        "confidence": 1.0 - risk_score if risk_score <= 1 else (100 - risk_score) / 100.0,
                        "reasoning": json_obj.get("reasoning", ""),
                        "summary": f"风险等级: {json_obj.get('risk_level', '中')}",
                        "core_evidence": json_obj.get("key_risks", [])[:3] if isinstance(json_obj.get("key_risks"), list) else [],
                        "uncertainties": [],
                        "invalidation_conditions": [],
                        "watch_items": [],
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
            "action": "中性",  # 市场观点术语
            "analysis_view": "中性",
            "confidence": 0.5,  # 0-1 的小数（前端期望）
            "reasoning": "风险评估数据不足，当前仅能保留中性研究观察，建议等待更多证据。",
            "summary": "当前证据不足，建议继续跟踪而非形成确定性结论。",
            "core_evidence": [],
            "uncertainties": [],
            "invalidation_conditions": [],
            "watch_items": ["继续跟踪后续披露与关键风险变化。"],
            "risk_warning": "请等待更多分析数据与后续披露。"
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
            return "## 综合研究结论\n\n数据不足，暂无法形成完整研究结论。"
        
        lines = ["## 综合研究结论\n"]
        
        field_names = {
            "action": "**研究判断**",
            "confidence": "**信心度**",
            "reasoning": "**研究推理**",
            "summary": "**结论摘要**",
            "risk_warning": "**风险提示**"
        }
        
        action = decision.get("analysis_view") or decision.get("action", "")
        if action:
            action_mapping = {
                "买入": "看涨",
                "卖出": "看跌",
                "持有": "中性"
            }
            market_view = action_mapping.get(action, action)
            lines.append(f"{field_names.get('action', '**研究判断**')}: {market_view}（仅供研究参考，不构成交易建议）")
        
        confidence = decision.get("confidence")
        if confidence is not None:
            if isinstance(confidence, float) and 0 <= confidence <= 1:
                confidence_display = f"{confidence * 100:.0f}%"
            elif isinstance(confidence, (int, float)) and confidence > 1:
                confidence_display = f"{int(confidence)}%"
            else:
                confidence_display = str(confidence)
            lines.append(f"{field_names.get('confidence', '**信心度**')}: {confidence_display}")
        
        reasoning = decision.get("reasoning")
        if reasoning:
            lines.append(f"\n{field_names.get('reasoning', '**研究推理**')}:\n\n{reasoning}")
        
        summary = decision.get("summary")
        if summary:
            lines.append(f"\n{field_names.get('summary', '**结论摘要**')}:\n\n{summary}")
        
        for title, field_name in (
            ("核心依据", "core_evidence"),
            ("关键不确定性", "uncertainties"),
            ("判断调整条件", "invalidation_conditions"),
            ("后续观察事项", "watch_items"),
        ):
            items = decision.get(field_name)
            if isinstance(items, list) and items:
                lines.append(f"\n**{title}**:")
                for item in items:
                    if item:
                        lines.append(f"- {item}")
        
        risk_warning = decision.get("risk_warning")
        if risk_warning:
            lines.append(f"\n{field_names.get('risk_warning', '**风险提示**')}:\n\n{risk_warning}")
        
        # 添加免责声明
        lines.append("\n**免责声明**：")
        lines.append("本研究简报仅供信息参考，不构成交易建议或投资承诺。所有研究判断与风险提示均基于当前信息，")
        lines.append("请结合自身情况独立判断。投资有风险，决策需谨慎。必要时请咨询专业顾问。")
        
        return "\n".join(lines)
