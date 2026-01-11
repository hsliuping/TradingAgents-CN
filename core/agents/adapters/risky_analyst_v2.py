"""
激进风险分析师 v2.0

基于 ResearcherAgent 基类的激进风险分析师实现。
从激进角度评估交易计划，关注高收益机会，容忍较高风险。
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

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class RiskyAnalystV2(ResearcherAgent):
    """
    激进风险分析师 v2.0
    
    功能：
    - 从激进角度评估交易计划
    - 关注高收益机会
    - 容忍较高风险
    - 寻找进攻性策略
    
    工作流程：
    1. 读取投资计划和市场分析
    2. 使用LLM从激进角度评估风险
    3. 生成激进风险观点
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent
        
        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("risky_analyst_v2", llm)
        
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
        id="risky_analyst_v2",
        name="激进风险分析师 v2.0",
        description="从激进角度评估交易计划，关注高收益机会，容忍较高风险",
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
            AgentOutput(name="risky_opinion", type="string", description="激进风险观点"),
        ],
        requires_tools=False,
        output_field="risky_opinion",
        report_label="【激进风险评估】",
    )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="risky_analyst_v2",
            variables={},
            context=None,
            fallback_prompt=None
        )
        if prompt:
            logger.debug("✅ 从模板系统获取激进风险分析师系统提示词")
            return prompt

        # 降级：使用默认提示词
        return """你是一位激进的风险分析师。

你的角色特点：
- 🔥 激进进取，追求高收益
- 💰 愿意承担较高风险以获取超额回报
- 🚀 关注市场机会和上涨潜力
- ⚡ 倾向于积极的交易策略

你的任务是：
1. 从激进角度评估投资计划的收益潜力
2. 分析可能的高收益机会
3. 评估风险是否值得承担
4. 提出更激进的操作建议（如加大仓位、提高目标价等）

评估要点：
- 上涨空间和收益潜力
- 市场情绪和动量
- 突破机会和催化剂
- 风险收益比（偏向收益）

要求：
- 保持激进但不失理性
- 用数据支持你的观点
- 使用中文撰写报告"""

    def _build_user_prompt(self, ticker: str, analysis_date: str, state: Dict[str, Any]) -> str:
        """构建用户提示词"""
        investment_plan = state.get("investment_plan", "")
        bull_opinion = state.get("bull_opinion", "")
        bear_opinion = state.get("bear_opinion", "")

        prompt = f"""请从激进角度评估以下投资计划：

股票代码：{ticker}
分析日期：{analysis_date}

投资计划：
{investment_plan}

看涨观点：
{bull_opinion}

看跌观点：
{bear_opinion}

请从激进风险分析师的角度：
1. 评估该计划的收益潜力（重点关注上涨空间）
2. 分析可能的高收益机会
3. 评估当前风险是否值得承担
4. 提出更激进的操作建议（如建议加大仓位、提高目标价等）
5. 给出激进风险评分（1-10分，10分表示风险完全可接受）

请以激进但理性的态度撰写分析报告。"""

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
        执行激进风险分析
        
        Args:
            state: 包含以下键的状态字典:
                - ticker: 股票代码
                - analysis_date: 分析日期
                - investment_plan: 投资计划
                - bull_opinion: 看涨观点（可选）
                - bear_opinion: 看跌观点（可选）
                
        Returns:
            更新后的状态，包含:
                - risky_opinion: 激进风险观点
        """
        ticker = state.get("ticker", "")
        analysis_date = state.get("analysis_date", "")
        
        logger.info(f"🔥 激进风险分析师开始评估 {ticker} @ {analysis_date}")
        
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
            
            logger.info(f"✅ 激进风险分析完成")
            
            # 只返回新增字段
            return {
                "risky_opinion": opinion
            }
            
        except Exception as e:
            logger.error(f"❌ 激进风险分析失败: {e}", exc_info=True)
            return {
                "risky_opinion": f"激进风险分析失败: {str(e)}"
            }

