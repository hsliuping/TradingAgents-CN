"""
保守风险分析师 v2.0

基于 ResearcherAgent 基类的保守风险分析师实现。
从保守角度评估交易计划，优先资本保护，规避潜在风险。
支持多轮辩论和缓存系统。
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
class SafeAnalystV2(ResearcherAgent):
    """
    保守风险分析师 v2.0

    功能：
    - 从保守角度评估交易计划
    - 优先考虑资本保护
    - 规避潜在风险
    - 寻找防御性策略
    - 支持多轮辩论（与激进、中性分析师辩论）
    - 支持缓存系统（避免重复分析）

    工作流程：
    1. 读取投资计划和市场分析
    2. 读取辩论历史和对手观点
    3. 使用LLM从保守角度评估风险并反驳对手
    4. 生成保守风险观点
    5. 更新辩论状态

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
            "bear_opinion": "...",
            "risk_debate_state": {
                "history": "...",
                "safe_history": "...",
                "current_risky_response": "...",
                "current_neutral_response": "...",
                "count": 0
            }
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="safe_analyst_v2",
        name="保守风险分析师 v2.0",
        description="从保守角度评估交易计划，优先资本保护，规避潜在风险，支持多轮辩论",
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
            AgentInput(name="risk_debate_state", type="dict", description="辩论状态", required=False),
        ],
        outputs=[
            AgentOutput(name="safe_opinion", type="string", description="保守风险观点"),
            AgentOutput(name="risk_debate_state", type="dict", description="更新后的辩论状态"),
        ],
        requires_tools=False,
        output_field="safe_opinion",
        report_label="【保守风险评估】",
    )

    # 研究立场（风险分析师使用 "safe"）
    stance = "safe"

    # 输出字段名
    output_field = "safe_opinion"

    # 🆕 辩论历史字段（用于多轮辩论）
    history_field = "safe_history"
    opponent_history_fields = ["risky_history", "neutral_history"]
    
    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词

        Args:
            state: 工作流状态（可选，用于提取变量如 company_name, ticker 等）

        Returns:
            系统提示词
        """
        # 风险分析师不需要模板变量（不依赖股票信息）
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        logger.info("🔍 [SafeAnalystV2] 开始构建系统提示词")
        
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="safe_analyst_v2",
            variables={},  # 系统提示词不需要变量（参考 research_manager_v2）
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context") if state else None,  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
        if prompt:
            logger.debug("✅ 从模板系统获取保守风险分析师系统提示词")
            return prompt

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
        """构建用户提示词（从模板系统获取并渲染）"""
        # 🆕 获取辩论状态
        risk_debate_state = state.get("risk_debate_state", {})
        history = risk_debate_state.get("history", "")
        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        # 准备模板变量（从 state 中提取所有数据）
        template_variables = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "investment_plan": state.get("investment_plan", "") or state.get("trader_investment_plan", ""),
            "bull_opinion": state.get("bull_opinion", ""),
            "bear_opinion": state.get("bear_opinion", ""),
            "market_report": state.get("market_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "news_report": state.get("news_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "index_report": state.get("index_report", ""),
            "sector_report": state.get("sector_report", ""),
            # 🆕 辩论相关变量
            "history": history,
            "current_risky_response": current_risky_response,
            "current_neutral_response": current_neutral_response,
        }

        # 📊 记录输入数据长度
        logger.info(f"📊 [Safe Analyst] 输入数据长度统计:")
        logger.info(f"  - market_report: {len(template_variables['market_report']):,} 字符")
        logger.info(f"  - sentiment_report: {len(template_variables['sentiment_report']):,} 字符")
        logger.info(f"  - news_report: {len(template_variables['news_report']):,} 字符")
        logger.info(f"  - fundamentals_report: {len(template_variables['fundamentals_report']):,} 字符")
        logger.info(f"  - investment_plan: {len(template_variables['investment_plan']):,} 字符")
        logger.info(f"  - history: {len(history):,} 字符")
        total_length = (len(template_variables['market_report']) + len(template_variables['sentiment_report']) +
                       len(template_variables['news_report']) + len(template_variables['fundamentals_report']) +
                       len(template_variables['investment_plan']) + len(history) +
                       len(current_risky_response) + len(current_neutral_response))
        logger.info(f"  - 总Prompt长度: {total_length:,} 字符 (~{total_length//4:,} tokens)")

        # 降级提示词（如果模板系统不可用）- 参考旧版实现
        fallback_prompt = f"""以下是交易员的决策：
{template_variables['investment_plan']}

将以下来源的见解纳入您的论点：
市场研究报告：{template_variables['market_report']}
社交媒体情绪报告：{template_variables['sentiment_report']}
最新世界事务报告：{template_variables['news_report']}
公司基本面报告：{template_variables['fundamentals_report']}

当前对话历史：{history}
激进分析师的最后回应：{current_risky_response}
中性分析师的最后回应：{current_neutral_response}

请提出您的保守观点，强调为什么低风险方法是最安全的。"""

        # 打印模板变量（调试用）
        logger.info(f"📊 [保守风险分析师] 模板变量:")
        for key, value in template_variables.items():
            if isinstance(value, str) and len(value) > 100:
                logger.info(f"  - {key}: {value[:100]}...")
            else:
                logger.info(f"  - {key}: {value}")

        # 使用基类的通用方法获取用户提示词（会从 context/state 中提取 preference_id）
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="safe_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context") if isinstance(state, dict) else state,  # 从 state 中获取 context
            fallback_prompt=fallback_prompt,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取保守风险分析师用户提示词 (长度: {len(prompt)})")
            return prompt

        # 降级：使用硬编码提示词
        logger.info(f"📝 [保守风险分析师] 使用降级提示词 (长度: {len(fallback_prompt)})")
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
        执行保守风险分析（支持多轮辩论）

        Args:
            state: 包含以下键的状态字典:
                - ticker: 股票代码
                - analysis_date: 分析日期
                - investment_plan: 投资计划
                - bull_opinion: 看涨观点（可选）
                - bear_opinion: 看跌观点（可选）
                - risk_debate_state: 辩论状态（可选）

        Returns:
            更新后的状态，包含:
                - safe_opinion: 保守风险观点
                - risk_debate_state: 更新后的辩论状态
        """
        ticker = state.get("ticker", "") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date", "") or state.get("trade_date", "")

        logger.info(f"🛡️ 保守风险分析师开始评估 {ticker} @ {analysis_date}")

        # 🆕 获取辩论状态
        risk_debate_state = state.get("risk_debate_state", {})
        history = risk_debate_state.get("history", "")
        safe_history = risk_debate_state.get("safe_history", "")

        try:
            # 构建提示词
            system_prompt = self._build_system_prompt(state)
            user_prompt = self._build_user_prompt(ticker, analysis_date, state)

            # 调用LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")

            logger.info(f"⏱️ [Safe Analyst] 开始调用LLM...")
            import time
            llm_start_time = time.time()

            if self._llm:
                response = self._llm.invoke(messages)
                opinion = response.content
            else:
                raise ValueError("LLM not initialized")

            llm_elapsed = time.time() - llm_start_time
            logger.info(f"⏱️ [Safe Analyst] LLM调用完成，耗时: {llm_elapsed:.2f}秒")

            # 🆕 格式化论点（参考旧版）
            argument = f"Safe Analyst: {opinion}"

            # 🆕 更新辩论状态
            new_count = risk_debate_state.get("count", 0) + 1
            logger.info(f"🛡️ [保守风险分析师] 发言完成，计数: {risk_debate_state.get('count', 0)} -> {new_count}")

            new_risk_debate_state = {
                "history": history + "\n" + argument,
                "risky_history": risk_debate_state.get("risky_history", ""),
                "safe_history": safe_history + "\n" + argument,
                "neutral_history": risk_debate_state.get("neutral_history", ""),
                "latest_speaker": "Safe",
                "current_risky_response": risk_debate_state.get("current_risky_response", ""),
                "current_safe_response": argument,
                "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
                "count": new_count,
            }

            logger.info(f"✅ 保守风险分析完成")

            # 返回新增字段和更新后的辩论状态
            return {
                "safe_opinion": opinion,
                "risk_debate_state": new_risk_debate_state
            }

        except Exception as e:
            logger.error(f"❌ 保守风险分析失败: {e}", exc_info=True)
            return {
                "safe_opinion": f"保守风险分析失败: {str(e)}",
                "risk_debate_state": risk_debate_state  # 保持原状态
            }

