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
            AgentOutput(name="final_trade_decision", type="string", description="最终交易决策"),
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
        # 从模板系统获取提示词
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="managers_v2",
                    agent_name="risk_manager_v2",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取风险管理者提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
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

        重写父类方法以添加 risk_debate_state 和 final_trade_decision 输出，
        确保与报告格式化器兼容
        """
        # 调用父类方法获取基本输出
        result = super().execute(state)

        # 提取风险评估内容
        risk_assessment_raw = result.get(self.output_field)
        risk_assessment_text = self._extract_text(risk_assessment_raw)
        final_decision_text = self._format_final_decision(risk_assessment_text)

        # 从 state 中获取现有的 risk_debate_state（如果有）
        existing_risk_state = state.get("risk_debate_state", {})

        # 构建新的 risk_debate_state，包含 judge_decision
        new_risk_state = {
            "judge_decision": final_decision_text,  # ✅ 关键：添加 judge_decision 字段
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

        # 返回包含 risk_debate_state 和 final_trade_decision 的结果
        return {
            **result,
            "risk_debate_state": new_risk_state,
            "final_trade_decision": final_decision_text,
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

    def _format_final_decision(self, risk_assessment_text: str) -> str:
        if not risk_assessment_text:
            return "风险评估未完成，无法生成最终交易决策"
        return risk_assessment_text
