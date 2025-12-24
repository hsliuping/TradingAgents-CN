"""
时机分析师 v2.0 (复盘分析)

基于ResearcherAgent基类实现的时机分析师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
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
class TimingAnalystV2(ResearcherAgent):
    """
    时机分析师 v2.0 (复盘分析)
    
    功能：
    - 分析买入卖出时机
    - 评估交易时机选择的合理性
    - 与理论最优买卖点对比
    
    工作流程：
    1. 读取交易信息和市场数据
    2. 使用LLM分析时机选择
    3. 生成时机分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("timing_analyst_v2", llm)

        result = agent.execute({
            "trade_info": {...},
            "market_data": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="timing_analyst_v2",
        name="时机分析师 v2.0",
        description="分析买入卖出时机，评估交易时机选择的合理性",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    researcher_type = "review_timing"
    stance = "neutral"
    output_field = "timing_analysis"

    def __init__(self, *args, **kwargs):
        """初始化时机分析师 v2.0"""
        super().__init__(*args, **kwargs)
        self._current_state = None  # 用于在 _build_system_prompt() 中访问 state

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行分析（重写以支持交易计划规则注入）"""
        # 保存 state 到实例变量，以便在 _build_system_prompt() 中访问
        self._current_state = state
        try:
            # 调用父类的 execute() 方法
            return super().execute(state)
        finally:
            # 清理实例变量
            self._current_state = None

    def _build_system_prompt(self, stance: str) -> str:
        """构建系统提示词（包含交易计划规则）"""
        # 降级提示词（当模板系统不可用时使用）
        fallback_prompt = """您是一位专业的时机分析师 v2.0。

您的职责是分析交易时机的选择是否合理。

**分析要点**：
1. 买入时机 - 是否处于相对低位
2. 卖出时机 - 是否处于相对高位
3. 与最优点差距 - 与理论最优买卖点的差距
4. 持仓周期 - 持仓时间是否合理
5. 时机评分 - 1-10分的时机选择评分

请使用中文，基于真实数据进行客观分析。"""

        # 🆕 从 state 获取交易计划（如果有）
        trading_plan = None
        if self._current_state:
            trading_plan = self._current_state.get('trading_plan')

        # 🆕 构建交易计划规则文本
        trading_plan_section = ''
        if trading_plan:
            plan_name = trading_plan.get('plan_name', '未命名计划')
            timing_rules = trading_plan.get('rules', {}).get('timing', {})
            entry_signals = timing_rules.get('entry_signals', [])
            exit_signals = timing_rules.get('exit_signals', [])

            if entry_signals or exit_signals:
                trading_plan_section = f"""

=== 关联的交易计划 ===
本次交易关联了交易计划：**{plan_name}**

**择时规则**：
- 入场信号: {'; '.join(entry_signals) if entry_signals else '无'}
- 出场信号: {'; '.join(exit_signals) if exit_signals else '无'}

**请在分析中重点检查**：
1. 买入时机是否符合入场信号要求
2. 卖出时机是否符合出场信号要求
3. 如有违反规则的地方，请明确指出"""

        if get_agent_prompt:
            try:
                # 🆕 传递交易计划规则文本作为变量
                variables = {
                    'trading_plan_section': trading_plan_section
                }

                prompt = get_agent_prompt(
                    agent_type="reviewers_v2",
                    agent_name="timing_analyst_v2",
                    variables=variables,
                    preference_id="neutral",
                    fallback_prompt=fallback_prompt
                )
                if prompt:
                    has_plan = "（包含交易计划规则）" if trading_plan else "（无交易计划）"
                    logger.info(f"✅ 从模板系统获取时机分析师提示词 {has_plan} (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")

        # 降级提示词也要包含交易计划规则
        return fallback_prompt + trading_plan_section

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """构建用户提示词（只包含交易数据，不包含交易计划规则）

        注意：交易计划规则已经在系统提示词中注入，这里只需要提供交易数据。
        """
        trade_info = state.get("trade_info", {})
        market_data = state.get("market_data", {})

        code = trade_info.get("code", ticker)
        trades = trade_info.get("trades", [])

        # 格式化交易记录
        trade_list = []
        for t in trades:
            trade_list.append(
                f"- {t.get('date', 'N/A')}: {t.get('side', 'N/A')} "
                f"{t.get('quantity', 0)}股 @ {t.get('price', 0):.2f}"
            )
        trade_str = "\n".join(trade_list) if trade_list else "无交易记录"

        # 构建提示词（只包含交易数据）
        prompt = f"""请分析以下交易的时机选择：

=== 交易信息 ===
- 股票代码: {code}
- 持仓周期: {trade_info.get('holding_period', 0)}天
- 收益率: {trade_info.get('pnl', 0):.2%}

=== 交易记录 ===
{trade_str}

=== 市场数据 ===
{market_data.get('summary', '无市场数据')}

请撰写详细的时机分析报告，包括：
1. 买入时机评估
2. 卖出时机评估
3. 与最优点的差距
4. 持仓周期合理性
5. 时机选择评分（1-10分）"""

        return prompt

    def _get_required_reports(self) -> List[str]:
        """获取需要的数据列表"""
        return ["trade_info", "market_data"]

