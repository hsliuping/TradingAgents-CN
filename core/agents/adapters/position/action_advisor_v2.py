"""
持仓研究整合师 v2.0 (持仓分析)

基于ManagerAgent基类实现的持仓研究整合师
"""

import logging
import re
from typing import Dict, Any, List

from ...manager import ManagerAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ...registry import register_agent
from app.utils.compliance import sanitize_position_text_block, sanitize_text_block

logger = logging.getLogger(__name__)

_LEGACY_EXECUTION_PROMPT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bstop_loss\b",
        r"\btake_profit\b",
        r"risk_reference(?:_price)?",
        r"profit_reference(?:_price)?",
        r"price_monitoring",
        r"recommended_action",
        r"价格分析区间",
        r"止损参考价|第一目标价|第二目标价",
        r"请给出JSON格式的操作建议",
        r"操作建议师",
        r"2000-5000字",
    )
]


def _contains_legacy_execution_prompt_terms(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _LEGACY_EXECUTION_PROMPT_PATTERNS)


def _summarize_position_research_input(value: Any, fallback: str) -> str:
    """将上游分析压缩为可用于整合提示词的研究摘要。"""
    cleaned = sanitize_position_text_block(value, fallback="")
    if not cleaned:
        secondary = sanitize_text_block(value, fallback="")
        cleaned = sanitize_position_text_block(secondary, fallback="") if secondary else ""
    normalized = re.sub(r"\s+", " ", cleaned).strip(" ；")
    return normalized[:600] if normalized else fallback

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class ActionAdvisorV2(ManagerAgent):
    """
    持仓研究整合师 v2.0 (持仓分析)

    功能：
    - 综合技术面、基本面、风险评估
    - 形成持仓研究判断
    - 汇总风险边界与后续观察事项

    工作流程：
    1. 读取各维度分析结果
    2. 使用LLM综合整合
    3. 生成持仓研究观察
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("pa_advisor_v2", llm)

        result = agent.execute({
            "position_info": {...},
            "technical_analysis": "...",
            "fundamental_analysis": "...",
            "risk_analysis": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="pa_advisor_v2",
        name="持仓研究整合师 v2.0",
        description="综合各维度分析，形成持仓研究判断与观察事项",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="position_info", type="object", description="持仓信息详情", required=False),
            AgentInput(name="technical_analysis", type="string", description="技术面分析结果", required=False),
            AgentInput(name="fundamental_analysis", type="string", description="基本面分析结果", required=False),
            AgentInput(name="risk_analysis", type="string", description="风险评估结果", required=False),
        ],
        outputs=[
            AgentOutput(name="action_advice", type="string", description="持仓研究观察"),
        ],
        growth_role="optimizer",
        growth_outputs=["action_advice"],
        memory_scope_hint="research_asset",
        review_level="manual_required",
        growth_source_type="manager_decision",
    )

    # 管理者类型
    manager_type = "position_advisor"
    
    # 输出字段名
    output_field = "action_advice"
    
    # 是否启用辩论（持仓分析不需要辩论）
    enable_debate = False

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词
        
        Args:
            state: 工作流状态（可选，用于提取变量）
        
        Returns:
            系统提示词
        """
        # 准备模板变量（如果有state）
        variables = {}
        if state:
            position_info = state.get("position_info", {})
            code = position_info.get("code", "")
            name = position_info.get("name", "N/A")
            market = position_info.get("market", "CN")
            
            from datetime import datetime
            variables = {
                "code": code,
                "name": name,
                "ticker": code,  # 兼容旧模板的变量名
                "company_name": name,  # 兼容旧模板的变量名
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "market_name": "A股" if market == "CN" else "港股" if market == "HK" else "美股",
                "market": market,
                # 货币符号
                "currency_symbol": "¥",
                "currency_name": "人民币",
            }
        
        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="position_analysis_v2",
            agent_name="pa_advisor_v2",
            variables=variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context") if state else state,  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # ✅ 关键：指定获取系统提示词（包含output_format）
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取持仓分析观点师提示词 (长度: {len(prompt)})")
            # 检查模板是否仍残留执行性语义
            if "confidence" in prompt.lower():
                logger.info(f"📊 [ActionAdvisorV2] ✅ 提示词中包含confidence字段要求")
            else:
                logger.warning(f"⚠️ [ActionAdvisorV2] ❌ 提示词中不包含confidence字段要求！")
            if _contains_legacy_execution_prompt_terms(prompt):
                logger.warning("⚠️ [ActionAdvisorV2] 提示词中仍包含执行性术语，请检查模板内容")
            if "observation_factors" in prompt.lower() or "观察事项" in prompt:
                logger.info("📊 [ActionAdvisorV2] ✅ 提示词中包含观察事项字段要求")
            else:
                logger.warning("⚠️ [ActionAdvisorV2] ❌ 提示词中不包含观察事项字段要求！")
            
            # 打印提示词的最后500字符（通常JSON格式要求在这里）
            logger.info(f"📊 [ActionAdvisorV2] 提示词最后500字符:\n{prompt[-500:]}")
            return prompt
        
        # 降级：使用默认提示词（合规版本）
        return """您是一位专业的持仓研究整合师。

您的职责是综合技术面、基本面和风险评估结果，形成非执行性的持仓研究判断。

分析要点：
1. 综合研究判断 - 当前持仓处于偏强/中性/偏弱/待验证的哪种研究状态
2. 核心证据 - 支撑当前判断的主要事实与逻辑
3. 风险边界 - 当前最值得警惕的风险来源与情景变化
4. 潜在催化 - 可能改变研究判断的经营、行业或政策因素
5. 后续观察事项 - 未来需要持续验证的公开信号

严格要求：
- 禁止输出买入、卖出、持有、加仓、减仓、清仓等执行性建议。
- 禁止输出目标价、止损止盈、价格区间、仓位比例、建议数量或建议金额。
- 禁止输出任何评分、打分、几分制、置信打分等排序式表达。
- 禁止使用“站稳”“突破”“跌破”“放量”“缩量”“右侧介入”“左侧介入”等隐性交易触发语。
- 只输出研究判断、风险提示、催化因素和观察事项。

请使用中文，基于真实数据进行客观分析。

输出格式要求：
请给出JSON格式的持仓研究结论：
```json
{
    "user_view": {
        "conclusion": "1到2句白话短句，直接说明当前持仓状态，不超过36字；不得出现技术面、基本面、PB、ROE、均线、MACD、RSI、KDJ等术语",
        "position_context": "结合浮盈浮亏、持有时间、成本与现价关系解释这笔持仓当前意味着什么，不超过55字；不要写成研究腔长句",
        "key_points": ["核心依据1，完整短句", "核心依据2，完整短句", "核心依据3，完整短句"],
        "risk_focus": ["风险提示1，完整短句", "风险提示2，完整短句", "风险提示3，完整短句"],
        "watch_items": ["后续观察点1，完整短句", "后续观察点2，完整短句", "后续观察点3，完整短句"],
        "uncertainty_note": "一句话说明还缺哪些公开信息验证，不超过45字"
    },
    "analysis_summary": {
        "overall_view": "综合研究概述",
        "key_points": ["关键点1", "关键点2"]
    },
    "neutral_operation_advice": {
        "recommended_analysis_view": "偏强|中性|偏弱|待验证",
        "confidence": 0-100的整数（表示研究判断稳定度，不代表交易把握）, 
        "core_judgment": "当前持仓所处研究阶段与核心判断",
        "reasoning": ["依据1", "依据2"],
        "analysis_points": ["观察要点1", "观察要点2"],
        "specific_suggestions": [
            {
                "action": "继续跟踪",
                "reason": "说明当前最应优先跟踪的公开信号"
            }
        ],
        "risk_reminder": "主要风险提示"
    },
    "risk_assessment": "详细风险评估（300-500字）",
    "opportunity_assessment": "详细催化与改善条件（300-500字）",
    "specific_plan": {
        "immediate_step": "下一步应优先核对的事实或披露",
        "observation_factors": ["后续观察事项1", "后续观察事项2"]
    }
}
```

**重要提示**：
1. **user_view 是给前端主界面直接展示的用户版内容，必须严格按结构输出，不得把内容堆进 conclusion 一个字段里。** key_points、risk_focus、watch_items 必须各自独立输出为字符串数组，conclusion 只写 1-2 句核心判断。
2. user_view.conclusion 和 user_view.position_context 必须使用白话中文，不得出现“技术面”“基本面”“PB”“ROE”“均线”“MACD”“RSI”“KDJ”“站稳”“突破”“支撑位”“阻力位”“右侧介入”“放量”等术语或触发语
3. user_view.key_points、risk_focus、watch_items 每组最多3条，每条必须是完整短句；宁可少写也不要输出半句、截断句或长段落
4. key_points 不得写“当前判断主要基于已披露信息”“请持续关注”“后续重点观察”等空话，必须写具体依据
5. **confidence** 字段是必需的，必须是0-100的整数，表示研究判断稳定度，不代表交易把握
6. 严禁输出加仓、减仓、清仓、买卖、目标价、价格区间、止损止盈、仓位比例等执行性内容
7. 请根据综合分析给出真实的 confidence 值，不要使用默认值
8. specific_suggestions 和 observation_factors 必须是可继续验证的公开信号、研究动作或信息核查事项，不得写成交易动作
9. 严禁输出“评分”“站稳”“突破”“放量”“右侧介入”等会被用户理解为交易触发条件的表达
10. **user_view 的六个字段（conclusion、position_context、key_points、risk_focus、watch_items、uncertainty_note）缺一不可，必须全部输出。** 即使内容简短也要输出，禁止省略或合并到其他字段。

**免责声明**：
本分析仅用于研究辅助与风险提示，不构成任何交易建议或执行指令。"""

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行持仓分析观点（覆盖基类方法，以便传递state给_build_system_prompt）
        """
        logger.info(f"开始执行持仓分析观点师: {self.agent_id}")

        try:
            # 1. 提取输入参数（兼容多种参数名）
            ticker = state.get("ticker") or state.get("company_of_interest")

            # 🆕 支持交易复盘场景：从 trade_info 中提取 code
            if not ticker and "trade_info" in state:
                trade_info = state.get("trade_info", {})
                if isinstance(trade_info, dict):
                    ticker = trade_info.get("code")
            
            # 🆕 支持持仓分析场景：从 position_info 中提取 code
            if not ticker and "position_info" in state:
                position_info = state.get("position_info", {})
                if isinstance(position_info, dict):
                    ticker = position_info.get("code")

            analysis_date = state.get("analysis_date") or state.get("trade_date") or state.get("end_date")

            # 🆕 支持交易复盘场景：使用当前日期作为分析日期
            if not analysis_date:
                from datetime import datetime
                analysis_date = datetime.now().strftime("%Y-%m-%d")

            if not ticker:
                raise ValueError("Missing required parameters: ticker")
            
            # 2. 收集所需的输入
            inputs = self._collect_inputs(state)
            
            if not inputs:
                raise ValueError("No inputs available for decision making")
            
            # 🔧 持仓研究观察员只需要风格偏好（neutral/aggressive/conservative），不需要考虑缓存场景
            # 将 preference_id 设置到 state["context"] 中，确保 _build_system_prompt 和 _build_user_prompt 使用同一个 preference_id
            user_preference = state.get("user_preference", "neutral")
            preference_id = user_preference  # 持仓研究观察员只需要风格偏好，不需要缓存场景
            
            # 更新 state["context"] 中的 preference_id
            context = state.get("context")
            if context:
                if isinstance(context, dict):
                    context = {**context, "preference_id": preference_id}
                else:
                    # 如果是对象，创建字典包装
                    context_dict = {"user_id": getattr(context, "user_id", None)}
                    context_dict["preference_id"] = preference_id
                    context = context_dict
            else:
                context = {"preference_id": preference_id}
            
            # 将更新后的 context 设置回 state，确保后续方法都能使用
            state["context"] = context
            logger.info(f"🔧 [持仓研究观察员] 在 execute 中生成 preference_id: {preference_id}")
            
            # 3. 如果启用辩论，进行辩论
            if self.enable_debate:
                debate_summary = self._conduct_debate(inputs, state)
            else:
                debate_summary = None
            
            # 4. 构建提示词（传递state给_build_system_prompt）
            system_prompt = self._build_system_prompt(state)
            user_prompt = self._build_user_prompt(ticker, analysis_date, inputs, debate_summary, state)
            
            # 5. 调用LLM做决策
            from langchain_core.messages import SystemMessage, HumanMessage
            system_prompt = self._apply_global_trading_advice_guard(system_prompt)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")            
            
            if self._llm:
                logger.info(f"📊 [ActionAdvisorV2] 调用LLM生成持仓研究观察...")
                
                # 打印用户提示词，检查是否包含JSON格式要求
                logger.info(f"📊 [ActionAdvisorV2] 用户提示词长度: {len(user_prompt)}")
                logger.info(f"📊 [ActionAdvisorV2] 用户提示词最后500字符:\n{user_prompt[-500:]}")
                if "confidence" in user_prompt.lower():
                    logger.info(f"📊 [ActionAdvisorV2] ✅ 用户提示词中包含confidence字段要求")
                else:
                    logger.warning(f"⚠️ [ActionAdvisorV2] ❌ 用户提示词中不包含confidence字段要求！")
                if _contains_legacy_execution_prompt_terms(user_prompt):
                    logger.warning("⚠️ [ActionAdvisorV2] 用户提示词中仍包含执行性术语，请检查降级提示词")
                if "observation_factors" in user_prompt.lower() or "观察事项" in user_prompt:
                    logger.info("📊 [ActionAdvisorV2] ✅ 用户提示词中包含观察事项字段要求")
                else:
                    logger.warning("⚠️ [ActionAdvisorV2] ❌ 用户提示词中不包含观察事项字段要求！")
                
                response = self._llm.invoke(messages)
                logger.info(f"📊 [ActionAdvisorV2] LLM响应成功，内容长度: {len(response.content)}")
                logger.info(f"📊 [ActionAdvisorV2] LLM响应前500字符: {response.content[:500]}")
                
                decision = self._parse_response(response.content)
                logger.info(f"📊 [ActionAdvisorV2] 解析后的decision类型: {type(decision)}, 字段: {list(decision.keys()) if isinstance(decision, dict) else 'N/A'}")
                
                # 注意：decision是{"content": response_string, "success": True}格式
                # confidence字段在content字符串的JSON中，将在portfolio_service.py中解析
                if isinstance(decision, dict) and "content" in decision:
                    content_preview = decision.get("content", "")[:200]
                    logger.info(f"📊 [ActionAdvisorV2] content预览: {content_preview}")
                    if "confidence" in decision.get("content", "").lower():
                        logger.info(f"📊 [ActionAdvisorV2] ✅ content中可能包含confidence字段")
                    else:
                        logger.warning(f"⚠️ [ActionAdvisorV2] ⚠️ content中可能不包含confidence字段")
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.manager_type}_decision"
            result = {
                output_key: decision
            }
            
            logger.info(f"📊 [ActionAdvisorV2] 输出到state，key: {output_key}")

            # 7. 保存辩论历史（如果有）
            if self.enable_debate and hasattr(self, 'debate_history') and self.debate_history:
                result[f"{self.agent_id}_debate_history"] = self.debate_history

            logger.info(f"✅ [ActionAdvisorV2] 持仓研究观察员 {self.agent_id} 执行成功")
            return result

        except Exception as e:
            logger.error(f"持仓研究观察员 {self.agent_id} 执行失败: {e}", exc_info=True)
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.manager_type}_decision"
            return {
                output_key: {
                    "error": str(e),
                    "success": False
                }
            }

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        inputs: Dict[str, str],
        debate_summary: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        Args:
            ticker: 股票代码（从position_info中提取）
            analysis_date: 分析日期
            inputs: 各类分析结果（technical_analysis, fundamental_analysis等）
            debate_summary: 辩论总结（持仓分析不使用）
            state: 当前状态
            
        Returns:
            用户提示词
        """
        position_info = state.get("position_info", {})
        user_goal = state.get("user_goal", {})
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        # 🔧 持仓研究观察员只需要风格偏好（neutral/aggressive/conservative），不需要考虑缓存场景
        # preference_id 已经在 execute 方法中生成并设置到 state["context"] 中
        # 这里直接从 context 中获取，确保与 _build_system_prompt 使用同一个 preference_id
        context = state.get("context")
        if context:
            if isinstance(context, dict):
                preference_id = context.get("preference_id", "neutral")
            else:
                preference_id = getattr(context, "preference_id", "neutral")
        else:
            # 降级：如果没有 context，使用默认值（这种情况不应该发生）
            user_preference = state.get("user_preference", "neutral")
            preference_id = user_preference
            logger.warning(f"⚠️ [持仓研究观察员] context 不存在，使用降级 preference_id: {preference_id}")
        
        logger.info(f"🔧 [持仓研究观察员] 从 context 获取 preference_id: {preference_id}")
        
        # 提取各维度分析（处理可能是字典的情况）
        def extract_content(value, default: str = "无分析"):
            """提取分析内容，支持字典和字符串格式"""
            if isinstance(value, dict):
                # 如果是字典，优先提取content字段，否则提取error字段，最后转为字符串
                return value.get("content", value.get("error", str(value)))
            elif isinstance(value, str):
                return value
            else:
                return str(value) if value else default
        
        technical_raw = state.get("technical_analysis", "无技术面分析")
        fundamental_raw = state.get("fundamental_analysis", "无基本面分析")
        risk_raw = state.get("risk_analysis", "无风险审阅")
        
        # 提取内容并限制长度
        technical = _summarize_position_research_input(
            extract_content(technical_raw, "无技术面分析"),
            fallback="技术面当前仍缺少稳定、可直接引用的研究摘要。",
        )
        fundamental = _summarize_position_research_input(
            extract_content(fundamental_raw, "无基本面分析"),
            fallback="基本面当前仍缺少稳定、可直接引用的研究摘要。",
        )
        risk = _summarize_position_research_input(
            extract_content(risk_raw, "无风险评估"),
            fallback="风险层面当前仍缺少稳定、可直接引用的研究摘要。",
        )
        
        # 准备模板变量（支持多种变量名映射，兼容不同模板）
        from datetime import datetime
        variables = {
            # 标准变量名
            "code": code,
            "name": name,
            "ticker": code,  # 兼容旧模板的变量名
            "company_name": name,  # 兼容旧模板的变量名
            "cost_price": f"{position_info.get('cost_price', 0):.2f}",
            "current_price": f"{position_info.get('current_price', 0):.2f}",
            # 🔧 修复：unrealized_pnl_pct 在数据源中已经是百分比格式（如 6.05），不需要再用 :.2% 格式化
            "unrealized_pnl_pct": f"{position_info.get('unrealized_pnl_pct', 0):.2f}%",
            # 日期相关
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "analysis_date": analysis_date,
            # 货币符号
            "currency_symbol": "¥",
            "currency_name": "人民币",
            # 🔧 新增：技术面、基本面和风险分析结果
            "technical_analysis": technical[:800] if technical else "",
            "fundamental_analysis": fundamental[:800] if fundamental else "",
            "risk_analysis": risk[:800] if risk else "",
            # 用户背景参考
            "target_return": str(user_goal.get('target_return', 10)),
            "stop_loss": str(user_goal.get('stop_loss', -10)),
        }
        
        # 尝试从数据库加载模板（preference_id 已经在 execute 方法中设置到 context 中）
        try:
            # 从 state 中提取 context（已经包含 preference_id）
            context = state.get("context") if state else None
            
            logger.info(f"🔧 [持仓研究观察员] 传递 preference_id 到模板系统: {preference_id}")

            prompt = self._get_prompt_from_template(
                agent_type="position_analysis_v2",  # 持仓分析Agent类型 v2.0（与工作流ID一致）
                agent_name="pa_advisor_v2",    # 持仓研究观察员v2.0
                variables=variables,
                context=context,  # context 已经包含 preference_id（只有风格偏好，没有缓存场景）
                fallback_prompt=None
            )
            if prompt:
                logger.info(f"✅ [持仓研究观察员] 从数据库加载提示词模板 (风格: {preference_id}, 长度: {len(prompt)})")
                return prompt
        except Exception as e:
            logger.warning(f"⚠️ [持仓研究观察员] 从数据库加载提示词失败: {e}，使用降级提示词")
        
        # 🆕 计算各维度分析的权重（持仓分析场景）
        # 持仓分析中，技术面、基本面、风险审阅的权重可以根据持仓类型调整
        # 默认权重：技术面40%、基本面30%、风险审阅30%
        analysis_reports = {
            "technical_analysis": technical,
            "fundamental_analysis": fundamental,
            "risk_analysis": risk,
        }
        
        # 过滤掉空报告
        selected_analyses = {
            k: v for k, v in analysis_reports.items()
            if v and isinstance(v, str) and len(v.strip()) > 0
        }
        
        # 持仓分析的权重配置（固定权重，不依赖交易风格）
        if len(selected_analyses) == 3:
            # 如果三个维度都有，使用预设权重
            weights = {
                "technical_analysis": 0.40,   # 技术面 40%
                "fundamental_analysis": 0.30,  # 基本面 30%
                "risk_analysis": 0.30,        # 风险审阅 30%
            }
        elif len(selected_analyses) == 2:
            # 如果只有两个维度，平均分配
            weights = {k: 0.50 for k in selected_analyses.keys()}
        else:
            # 如果只有一个维度，权重100%
            weights = {k: 1.0 for k in selected_analyses.keys()}
        
        # 确保是字符串并限制长度（避免f-string中的切片问题）
        technical_text = (technical[:800] if isinstance(technical, str) else str(technical)[:800])
        fundamental_text = (fundamental[:800] if isinstance(fundamental, str) else str(fundamental)[:800])
        risk_text = (risk[:800] if isinstance(risk, str) else str(risk)[:800])
        
        # 🆕 格式化带权重的分析报告
        analysis_labels = {
            "technical_analysis": "技术面分析",
            "fundamental_analysis": "基本面分析",
            "risk_analysis": "风险审阅",
        }
        
        # 按权重排序
        sorted_analyses = sorted(
            weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 构建带权重的分析报告文本
        analysis_parts = []
        for analysis_key, weight in sorted_analyses:
            if analysis_key in selected_analyses:
                label = analysis_labels.get(analysis_key, analysis_key)
                weight_pct = int(weight * 100)
                if analysis_key == "technical_analysis":
                    content = technical_text
                elif analysis_key == "fundamental_analysis":
                    content = fundamental_text
                else:
                    content = risk_text
                analysis_parts.append(f"=== {label}（权重{weight_pct}%，请重点关注） ===\n{content}\n")
        
        weighted_analyses_text = "\n".join(analysis_parts)
        
        return f"""请综合以下分析，形成持仓研究判断：

=== 持仓信息 ===
- 股票: {code} {name}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2f}%

{weighted_analyses_text}

**权重说明**：
- 请重点关注高权重分析，这些分析对研究判断更重要
- 在综合判断时，请根据权重给予相应的关注度

=== 持仓背景参考 ===
- 收益预期参考: {user_goal.get('target_return', 10)}%
- 可承受波动参考: {user_goal.get('stop_loss', -10)}%
- 上述信息仅用于理解持仓背景，不得据此输出任何执行建议

请给出JSON格式的持仓研究结论：
```json
{{
    "user_view": {{
        "conclusion": "一句话结论，白话短句",
        "position_context": "持仓影响说明，白话短句",
        "key_points": ["核心依据1，完整短句", "核心依据2，完整短句", "核心依据3，完整短句"],
        "risk_focus": ["风险提示1，完整短句", "风险提示2，完整短句", "风险提示3，完整短句"],
        "watch_items": ["后续观察点1，完整短句", "后续观察点2，完整短句", "后续观察点3，完整短句"],
        "uncertainty_note": "不确定性说明，白话短句"
    }},
    "analysis_summary": {{
        "overall_view": "综合研究概述",
        "key_points": ["关键点1", "关键点2"]
    }},
    "neutral_operation_advice": {{
        "recommended_analysis_view": "偏强|中性|偏弱|待验证",
        "confidence": 0-100的整数（研究判断稳定度，不代表交易把握）, 
        "core_judgment": "当前持仓所处研究阶段与核心判断",
        "reasoning": ["理由1", "理由2"],
        "analysis_points": ["分析要点1", "分析要点2"],
        "specific_suggestions": [
            {{
                "action": "继续跟踪",
                "reason": "说明当前最应优先跟踪的公开信号"
            }}
        ],
        "risk_reminder": "主要风险提示"
    }},
    "risk_assessment": "详细风险审阅",
    "opportunity_assessment": "详细催化与改善条件",
    "specific_plan": {{
        "immediate_step": "下一步应优先核对的事实或披露",
        "observation_factors": ["后续观察事项1", "后续观察事项2"]
    }}
}}
```

**重要提示**：
1. **user_view 是给前端主界面直接展示的用户版内容，必须严格按结构输出，不得把内容堆进 conclusion 一个字段里。** key_points、risk_focus、watch_items 必须各自独立输出为字符串数组，conclusion 只写 1-2 句核心判断。
2. user_view.conclusion 和 user_view.position_context 必须使用白话中文，不得出现“技术面”“基本面”“PB”“ROE”“均线”“MACD”“RSI”“KDJ”“站稳”“突破”“支撑位”“阻力位”“右侧介入”“放量”等术语或触发语
3. user_view.key_points、risk_focus、watch_items 每组最多3条，每条必须是完整短句；宁可少写也不要输出半句、截断句或长段落
4. 如果某条内容会以“将”“让”“获”“并”“但”“与”“或”“则”“需”等字结尾，说明句子不完整，必须重写，不得直接输出
5. key_points 不得写“当前判断主要基于已披露信息”“请持续关注”“后续重点观察”等空话，必须写具体依据
6. **confidence** 字段是必需的，必须是0-100的整数，表示研究判断稳定度，不代表交易把握
7. 严禁输出加仓、减仓、清仓、买卖、目标价、价格区间、止损止盈、仓位比例等执行性内容
8. 请根据综合分析给出真实的 confidence 值，不要使用默认值
9. specific_suggestions 和 observation_factors 必须是可继续验证的公开信号、研究动作或信息核查事项，不得写成交易动作
10. 严禁输出“评分”“站稳”“突破”“放量”“右侧介入”等会被用户理解为交易触发条件的表达
11. **user_view 的六个字段（conclusion、position_context、key_points、risk_focus、watch_items、uncertainty_note）缺一不可，必须全部输出。** 即使内容简短也要输出，禁止省略或合并到其他字段。"""

    def _get_required_inputs(self) -> List[str]:
        """
        获取需要的输入列表
        
        Returns:
            输入字段名列表
        """
        return [
            "technical_analysis",
            "fundamental_analysis",
            "risk_analysis"
        ]
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM响应（使用基类默认实现，返回原始文本）
        
        Args:
            response: LLM响应文本
            
        Returns:
            包含content字段的字典
        """
        # 使用基类默认实现，返回原始文本（让portfolio_service.py负责JSON解析）
        # 这样保持向后兼容，不会破坏现有逻辑
        return {
            "content": response,
            "success": True
        }

