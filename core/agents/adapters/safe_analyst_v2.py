"""
保守风险分析师 v2.0

基于 ResearcherAgent 基类的保守风险分析师实现。
从保守角度评估交易计划，优先资本保护，规避潜在风险。
"""

import logging
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage

from ..researcher import ResearcherAgent
from ..registry import register_agent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError):
    logger.warning("无法导入get_agent_prompt，将使用默认提示词")
    get_agent_prompt = None


@register_agent
class SafeAnalystV2(ResearcherAgent):
    """
    保守风险分析师 v2.0
    
    功能：
    - 从保守角度评估交易计划
    - 优先考虑资本保护
    - 规避潜在风险
    - 寻找防御性策略
    
    工作流程：
    1. 读取投资计划和市场分析
    2. 使用LLM从保守角度评估风险
    3. 生成保守风险观点
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent
        
        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("safe_analyst_v2", llm)
        
        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "investment_plan": "...",
            "bull_opinion": "...",
            "bear_opinion": "..."
        })
    """
    
    # Agent元数据
    metadata = AgentMetadata(
        id="safe_analyst_v2",
        name="保守风险分析师 v2.0",
        description="从保守角度评估交易计划，优先资本保护，规避潜在风险",
        category=AgentCategory.RISK,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 风险分析师不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="投资计划"),
            AgentInput(name="bull_opinion", type="string", description="看涨观点", required=False),
            AgentInput(name="bear_opinion", type="string", description="看跌观点", required=False),
        ],
        outputs=[
            AgentOutput(name="safe_opinion", type="string", description="保守风险观点"),
        ],
        requires_tools=False,
        output_field="safe_opinion",
        report_label="【保守风险评估】",
    )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        # 尝试从模板系统获取
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="debators_v2",
                    agent_name="safe_analyst_v2",
                    variables={},
                    preference_id="conservative",  # 保守风险分析师使用 conservative 偏好
                    fallback_prompt=None
                )

                if prompt:
                    logger.debug(f"✅ 从模板系统获取保守风险分析师系统提示词")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ 从模板系统获取提示词失败: {e}，使用默认提示词")

        # 降级：使用默认提示词
        return """你是一位保守的风险分析师。

你的角色特点：
- 🛡️ 稳健保守，优先保护资本
- 🔒 风险厌恶，宁可错过机会也不愿承担过高风险
- 📉 关注下行风险和潜在损失
- ⚠️ 倾向于谨慎的交易策略

你的任务是：
1. 从保守角度评估投资计划的风险
2. 识别所有潜在的风险因素
3. 评估最坏情况下的损失
4. 提出更保守的操作建议（如减小仓位、设置严格止损等）

评估要点：
- 下行风险和最大回撤
- 市场不确定性
- 潜在的黑天鹅事件
- 风险收益比（偏向风险）

要求：
- 保持保守但不失客观
- 用数据支持你的观点
- 使用中文撰写报告"""

    def _build_user_prompt(self, ticker: str, analysis_date: str, state: Dict[str, Any]) -> str:
        """构建用户提示词"""
        investment_plan = state.get("investment_plan", "")
        bull_opinion = state.get("bull_opinion", "")
        bear_opinion = state.get("bear_opinion", "")

        prompt = f"""请从保守角度评估以下投资计划：

股票代码：{ticker}
分析日期：{analysis_date}

投资计划：
{investment_plan}

看涨观点：
{bull_opinion}

看跌观点：
{bear_opinion}

请从保守风险分析师的角度：
1. 评估该计划的风险（重点关注下行风险）
2. 识别所有潜在的风险因素
3. 分析最坏情况下的可能损失
4. 提出更保守的操作建议（如建议减小仓位、设置严格止损等）
5. 给出保守风险评分（1-10分，10分表示风险完全不可接受）

请以保守但客观的态度撰写分析报告。"""

        return prompt

    def _get_required_reports(self) -> list:
        """
        获取需要的报告列表

        Returns:
            报告字段名列表
        """
        return [
            "investment_plan",
            "bull_opinion",
            "bear_opinion",
        ]
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行保守风险分析
        
        Args:
            state: 包含以下键的状态字典:
                - ticker: 股票代码
                - analysis_date: 分析日期
                - investment_plan: 投资计划
                - bull_opinion: 看涨观点（可选）
                - bear_opinion: 看跌观点（可选）
                
        Returns:
            更新后的状态，包含:
                - safe_opinion: 保守风险观点
        """
        ticker = state.get("ticker", "")
        analysis_date = state.get("analysis_date", "")
        
        logger.info(f"🛡️ 保守风险分析师开始评估 {ticker} @ {analysis_date}")
        
        try:
            # 构建提示词
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(ticker, analysis_date, state)
            
            # 调用LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            if self._llm:
                response = self._llm.invoke(messages)
                opinion = response.content
            else:
                raise ValueError("LLM not initialized")
            
            logger.info(f"✅ 保守风险分析完成")
            
            # 只返回新增字段
            return {
                "safe_opinion": opinion
            }
            
        except Exception as e:
            logger.error(f"❌ 保守风险分析失败: {e}", exc_info=True)
            return {
                "safe_opinion": f"保守风险分析失败: {str(e)}"
            }

