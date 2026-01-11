"""
中性风险分析师 v2.0

基于 ResearcherAgent 基类的中性风险分析师实现。
从中性角度评估交易计划，平衡收益与风险，寻求最优解。
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
class NeutralAnalystV2(ResearcherAgent):
    """
    中性风险分析师 v2.0
    
    功能：
    - 从中性角度评估交易计划
    - 平衡收益与风险
    - 寻求最优风险收益比
    - 提供客观理性的建议
    
    工作流程：
    1. 读取投资计划和市场分析
    2. 使用LLM从中性角度评估风险
    3. 生成中性风险观点
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent
        
        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("neutral_analyst_v2", llm)
        
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
        id="neutral_analyst_v2",
        name="中性风险分析师 v2.0",
        description="从中性角度评估交易计划，平衡收益与风险，寻求最优解",
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
            AgentInput(name="risky_opinion", type="string", description="激进风险观点", required=False),
            AgentInput(name="safe_opinion", type="string", description="保守风险观点", required=False),
        ],
        outputs=[
            AgentOutput(name="neutral_opinion", type="string", description="中性风险观点"),
        ],
        requires_tools=False,
        output_field="neutral_opinion",
        report_label="【中性风险评估】",
    )

    # 研究立场（风险分析师使用 "neutral"）
    stance = "neutral"

    # 输出字段名
    output_field = "neutral_opinion"
    
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词

        Returns:
            系统提示词
        """
        # 风险分析师不需要模板变量（不依赖股票信息）
        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="neutral_analyst_v2",
            variables={},
            context=None,
            fallback_prompt=None
        )
        if prompt:
            logger.debug("✅ 从模板系统获取中性风险分析师系统提示词")
            return prompt

        # 降级：使用默认提示词
        return """你是一位中性的风险分析师。

你的角色特点：
- ⚖️ 客观中立，平衡收益与风险
- 📊 数据驱动，理性分析
- 🎯 追求最优风险收益比
- 🔍 全面考虑各种因素

你的任务是：
1. 从中性角度评估投资计划的风险收益比
2. 平衡激进和保守的观点
3. 寻找最优的风险管理策略
4. 提供客观理性的操作建议

评估要点：
- 风险收益比的平衡
- 概率加权的期望收益
- 合理的仓位和止损设置
- 市场环境的综合判断

要求：
- 保持客观中立
- 用数据和逻辑支持你的观点
- 综合考虑多方面因素
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
            "risky_opinion": state.get("risky_opinion", ""),
            "safe_opinion": state.get("safe_opinion", ""),
            "market_report": state.get("market_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "news_report": state.get("news_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "index_report": state.get("index_report", ""),
            "sector_report": state.get("sector_report", ""),
        }

        # 降级提示词（如果模板系统不可用）
        fallback_prompt = f"""请从中性角度评估以下投资计划：

股票代码：{ticker}
分析日期：{analysis_date}

【投资计划】
{template_variables['investment_plan']}

【看涨观点】
{template_variables['bull_opinion']}

【看跌观点】
{template_variables['bear_opinion']}

【激进风险观点】
{template_variables['risky_opinion']}

【保守风险观点】
{template_variables['safe_opinion']}
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
请从中性风险分析师的角度，结合以上所有分析报告：

1. **风险收益比评估**
   - 结合技术面、基本面、新闻面，评估上涨空间和下跌风险
   - 分析市场情绪和资金流向的影响
   - 评估大盘和行业环境的支持或阻力
   - 计算概率加权的期望收益

2. **观点平衡分析**
   - 综合激进和保守的观点，找出合理的中间路线
   - 评估激进观点的合理性和风险
   - 评估保守观点的必要性和机会成本
   - 提出平衡的风险管理策略

3. **情景分析**
   - 分析最可能的情景（基准情景）
   - 分析乐观情景和悲观情景
   - 评估各情景的概率和对应的收益/损失
   - 计算期望收益和风险

4. **平衡操作建议**
   - 建议合理的仓位（基于风险收益比）
   - 建议合理的止损和止盈（基于技术面和波动率）
   - 建议合理的目标价（基于估值和市场环境）
   - 建议合理的交易策略（如分批建仓、动态调整）

5. **中性风险评分**（1-10分，5分表示风险收益完美平衡）
   - 1-3分：风险过高，不建议操作
   - 4-6分：风险收益平衡，可以操作
   - 7-10分：收益潜力大，风险可控，建议操作
   - 给出明确的数字评分和理由

**重要提示**：
- 保持客观中立，用数据和逻辑支持你的观点
- 平衡考虑上涨机会和下行风险
- 综合多方面因素，给出最优的风险管理策略
- 使用中文撰写报告"""

        # 打印模板变量（调试用）
        logger.info(f"📊 [中性风险分析师] 模板变量:")
        for key, value in template_variables.items():
            if isinstance(value, str) and len(value) > 100:
                logger.info(f"  - {key}: {value[:100]}...")
            else:
                logger.info(f"  - {key}: {value}")

        # 使用基类的通用方法获取用户提示词（会从 context/state 中提取 preference_id）
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="neutral_analyst_v2",
            variables=template_variables,
            context=state,
            fallback_prompt=fallback_prompt
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取中性风险分析师用户提示词 (长度: {len(prompt)})")
            return prompt

        # 降级：使用硬编码提示词
        logger.info(f"📝 [中性风险分析师] 使用降级提示词 (长度: {len(fallback_prompt)})")
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
            "risky_opinion",
            "safe_opinion",
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
        执行中性风险分析
        
        Args:
            state: 包含以下键的状态字典:
                - ticker: 股票代码
                - analysis_date: 分析日期
                - investment_plan: 投资计划
                - bull_opinion: 看涨观点（可选）
                - bear_opinion: 看跌观点（可选）
                - risky_opinion: 激进风险观点（可选）
                - safe_opinion: 保守风险观点（可选）
                
        Returns:
            更新后的状态，包含:
                - neutral_opinion: 中性风险观点
        """
        ticker = state.get("ticker", "")
        analysis_date = state.get("analysis_date", "")
        
        logger.info(f"⚖️ 中性风险分析师开始评估 {ticker} @ {analysis_date}")
        
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
            
            logger.info(f"✅ 中性风险分析完成")
            
            # 只返回新增字段
            return {
                "neutral_opinion": opinion
            }
            
        except Exception as e:
            logger.error(f"❌ 中性风险分析失败: {e}", exc_info=True)
            return {
                "neutral_opinion": f"中性风险分析失败: {str(e)}"
            }

