"""
操作建议师 v2.0 (持仓分析)

基于ManagerAgent基类实现的操作建议师
"""

import logging
from typing import Dict, Any, List

from ...manager import ManagerAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier
from ...registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None


@register_agent
class ActionAdvisorV2(ManagerAgent):
    """
    操作建议师 v2.0 (持仓分析)
    
    功能：
    - 综合技术面、基本面、风险评估
    - 给出持仓操作建议
    - 设置目标价位和止损止盈
    
    工作流程：
    1. 读取各维度分析结果
    2. 使用LLM综合决策
    3. 生成操作建议
    
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
        name="操作建议师 v2.0",
        description="综合各维度分析，给出持仓操作建议",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具
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
        
        # 从模板系统获取提示词
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="position_analysis_v2",
                    agent_name="pa_advisor_v2",
                    variables=variables,
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取操作建议师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        # 降级：使用默认提示词
        return """您是一位专业的投资顾问。

您的职责是综合各维度分析，给出持仓操作建议。

决策要点：
1. 操作建议 - 持有/加仓/减仓/清仓
2. 操作比例 - 建议操作的仓位比例
3. 目标价位 - 目标买入/卖出价格
4. 止损止盈 - 止损价位和止盈价位
5. 风险提示 - 主要风险点

请使用中文，基于真实数据进行决策。

输出格式要求：
请给出JSON格式的操作建议：
```json
{
    "action": "持有|加仓|减仓|清仓",
    "action_ratio": 0-100的百分比,
    "target_price": 目标价位,
    "stop_loss_price": 止损价位,
    "confidence": 0-100的信心度,
    "risk_level": "低|中|高",
    "summary": "综合评价",
    "reasoning": "操作依据",
    "risk_warning": "风险提示"
}
```"""
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行操作建议（覆盖基类方法，以便传递state给_build_system_prompt）
        """
        logger.info(f"开始执行操作建议师: {self.agent_id}")

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
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            if self._llm:
                response = self._llm.invoke(messages)
                decision = self._parse_response(response.content)
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.manager_type}_decision"
            result = {
                output_key: decision
            }

            # 7. 保存辩论历史（如果有）
            if self.enable_debate and hasattr(self, 'debate_history') and self.debate_history:
                result[f"{self.agent_id}_debate_history"] = self.debate_history

            logger.info(f"操作建议师 {self.agent_id} 执行成功")
            return result

        except Exception as e:
            logger.error(f"操作建议师 {self.agent_id} 执行失败: {e}", exc_info=True)
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
        risk_raw = state.get("risk_analysis", "无风险评估")
        
        # 提取内容并限制长度
        technical = extract_content(technical_raw, "无技术面分析")
        fundamental = extract_content(fundamental_raw, "无基本面分析")
        risk = extract_content(risk_raw, "无风险评估")
        
        # 确保是字符串并限制长度（避免f-string中的切片问题）
        technical_text = (technical[:1500] if isinstance(technical, str) else str(technical)[:1500])
        fundamental_text = (fundamental[:1500] if isinstance(fundamental, str) else str(fundamental)[:1500])
        risk_text = (risk[:1500] if isinstance(risk, str) else str(risk)[:1500])
        
        return f"""请综合以下分析，给出持仓操作建议：

=== 持仓信息 ===
- 股票: {code} {name}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2%}

=== 技术面分析 ===
{technical_text}

=== 基本面分析 ===
{fundamental_text}

=== 风险评估 ===
{risk_text}

=== 用户目标 ===
- 目标收益: {user_goal.get('target_return', 10)}%
- 止损线: {user_goal.get('stop_loss', -10)}%

请给出JSON格式的操作建议。"""

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

