"""
风险管理者 v2.0

基于ManagerAgent基类实现的风险管理者
"""

import logging
from typing import Dict, Any, List

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

    def _build_system_prompt(self) -> str:
        """
        构建系统提示词
        
        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="managers_v2",
            agent_name="risk_manager_v2",
            variables={},
            context=None,
            fallback_prompt=None
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取风险管理者提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：使用默认提示词
        return """您是一位专业的风险管理者。

您的职责是主持风险辩论，综合多方观点，形成最终的风险评估。

工作要点：
1. 倾听各方的风险观点（激进、保守、中性）
2. 识别关键风险因素
3. 评估风险的可能性和影响
4. 提出风险控制建议
5. 形成最终的风险评估报告

请使用中文，保持客观和专业。"""

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
            ticker: 股票代码
            analysis_date: 分析日期
            inputs: 输入数据（投资计划、各方观点等）
            debate_summary: 辩论总结
            state: 当前状态
            
        Returns:
            用户提示词
        """
        company_name = self._get_company_name(ticker, state)
        
        # 构建输入列表
        inputs_text = ""
        for input_name, input_content in inputs.items():
            if input_content:
                inputs_text += f"\n=== {input_name} ===\n{input_content}\n"
        
        # 构建辩论部分
        debate_text = ""
        if debate_summary:
            debate_text = f"\n=== 辩论总结 ===\n{debate_summary}\n"
        
        return f"""请综合以下信息，对股票 {ticker}（{company_name}）进行风险评估：

=== 分析日期 ===
{analysis_date}

=== 投资计划和各方观点 ===
{inputs_text}
{debate_text}

请撰写详细的风险评估报告，包括：
1. 关键风险因素识别
2. 风险可能性和影响评估
3. 风险控制建议
4. 最终风险评级
5. 投资建议调整"""

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
        final_trade_decision = self._extract_final_trade_decision(risk_assessment_text)

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
            "final_trade_decision": final_trade_decision,  # ✅ 新增：最终交易决策
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
                    logger.info(f"✅ [RiskManagerV2] 成功提取 final_trade_decision: action={final_decision.get('action')}, confidence={final_decision.get('confidence')}")
                    return final_decision
                else:
                    # 如果没有 final_trade_decision 字段，从顶层字段构建
                    logger.warning("⚠️ [RiskManagerV2] JSON 中没有 final_trade_decision 字段，从顶层字段构建")
                    # confidence 返回 0-1 的小数（前端期望）
                    risk_score = json_obj.get("risk_score", 0.5)
                    return {
                        "action": json_obj.get("investment_adjustment", "持有"),
                        "confidence": 1.0 - risk_score if risk_score <= 1 else (100 - risk_score) / 100.0,
                        "target_price": None,
                        "stop_loss": None,
                        "position_ratio": "5%",
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
        """返回默认的 final_trade_decision"""
        return {
            "action": "持有",
            "confidence": 0.5,  # 0-1 的小数（前端期望）
            "target_price": None,
            "stop_loss": None,
            "position_ratio": "5%",
            "reasoning": "风险评估数据不足，建议谨慎持有",
            "summary": "数据不足，建议观望",
            "risk_warning": "请等待更多分析数据"
        }
