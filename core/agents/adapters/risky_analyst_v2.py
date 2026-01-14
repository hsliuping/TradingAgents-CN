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

    # 研究立场（风险分析师使用 "risky"）
    stance = "risky"

    # 输出字段名
    output_field = "risky_opinion"
    
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词

        Returns:
            系统提示词
        """
        # 风险分析师不需要模板变量（不依赖股票信息）
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        logger.info("🔍 [RiskyAnalystV2] 开始构建系统提示词")
        
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="risky_analyst_v2",
            variables={},  # 系统提示词不需要变量（参考 research_manager_v2）
            context=None,
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
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
        """构建用户提示词（从模板系统获取并渲染）"""
        # 准备模板变量（从 state 中提取所有数据）
        template_variables = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "investment_plan": state.get("investment_plan", ""),
            "bull_opinion": state.get("bull_opinion", ""),
            "bear_opinion": state.get("bear_opinion", ""),
            "market_report": state.get("market_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "news_report": state.get("news_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "index_report": state.get("index_report", ""),
            "sector_report": state.get("sector_report", ""),
        }

        # 降级提示词（如果模板系统不可用）
        fallback_prompt = f"""请从激进角度评估以下投资计划：

股票代码：{ticker}
分析日期：{analysis_date}

【投资计划】
{template_variables['investment_plan']}

【看涨观点】
{template_variables['bull_opinion']}

【看跌观点】
{template_variables['bear_opinion']}
"""

        # 添加具体分析报告（如果有）
        if template_variables['index_report']:
            fallback_prompt += f"""
【大盘环境分析】
{template_variables['index_report']}
"""

        if template_variables['sector_report']:
            fallback_prompt += f"""
【行业板块分析】
{template_variables['sector_report']}
"""

        if template_variables['market_report']:
            fallback_prompt += f"""
【市场技术分析】
{template_variables['market_report']}
"""

        if template_variables['fundamentals_report']:
            fallback_prompt += f"""
【基本面分析】
{template_variables['fundamentals_report']}
"""

        if template_variables['news_report']:
            fallback_prompt += f"""
【新闻事件分析】
{template_variables['news_report']}
"""

        if template_variables['sentiment_report']:
            fallback_prompt += f"""
【市场情绪分析】
{template_variables['sentiment_report']}
"""

        # 添加分析要求
        fallback_prompt += """
请从激进风险分析师的角度，结合以上所有分析报告：

1. **收益潜力评估**（重点关注上涨空间）
   - 结合技术面、基本面、新闻面，评估上涨催化剂
   - 分析市场情绪和资金流向是否支持上涨
   - 评估大盘和行业环境是否有利

2. **高收益机会分析**
   - 识别可能的突破机会和爆发点
   - 分析短期和中期的收益潜力
   - 评估风险收益比是否值得激进操作

3. **风险承受性评估**
   - 评估当前风险是否在可接受范围内
   - 分析最坏情况下的损失是否可控
   - 判断是否值得为高收益承担这些风险

4. **激进操作建议**
   - 建议是否加大仓位（如从5%提高到8-10%）
   - 建议是否提高目标价（基于技术面和基本面）
   - 建议是否缩小止损空间（提高风险容忍度）
   - 建议是否采用更激进的交易策略

5. **激进风险评分**（1-10分，10分表示风险完全可接受，建议全力以赴）
   - 综合考虑收益潜力、风险水平、市场环境
   - 给出明确的数字评分和理由

**重要提示**：
- 保持激进但不失理性，用数据和逻辑支持你的观点
- 重点关注上涨机会，但也要客观评估风险
- 如果发现重大利好或突破信号，要大胆提出激进建议
- 使用中文撰写报告"""

        # 打印模板变量（调试用）
        logger.info(f"📊 [激进风险分析师] 模板变量:")
        for key, value in template_variables.items():
            if isinstance(value, str) and len(value) > 100:
                logger.info(f"  - {key}: {value[:100]}...")
            else:
                logger.info(f"  - {key}: {value}")

        # 使用基类的通用方法获取用户提示词（会从 context/state 中提取 preference_id）
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="risky_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context") if isinstance(state, dict) else state,  # 从 state 中获取 context
            fallback_prompt=fallback_prompt,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取激进风险分析师用户提示词 (长度: {len(prompt)})")
            return prompt

        # 降级：使用硬编码提示词
        logger.info(f"📝 [激进风险分析师] 使用降级提示词 (长度: {len(fallback_prompt)})")
        return fallback_prompt

    def _get_required_reports(self) -> list:
        """
        获取需要的报告列表

        Returns:
            报告字段名列表
        """
        return [
            # 必需的报告
            "investment_plan",
            "bull_opinion",
            "bear_opinion",
            # 🆕 可选的分析报告（提供更多上下文）
            "market_report",
            "fundamentals_report",
            "news_report",
            "sentiment_report",
            "index_report",
            "sector_report",
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

