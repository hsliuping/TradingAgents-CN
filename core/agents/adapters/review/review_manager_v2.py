"""
复盘总结师 v2.0 (复盘分析)

基于ManagerAgent基类实现的复盘总结师
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
class ReviewManagerV2(ManagerAgent):
    """
    复盘总结师 v2.0 (复盘分析)
    
    功能：
    - 综合所有分析维度
    - 生成完整复盘报告
    - 给出改进建议
    
    工作流程：
    1. 读取各维度分析结果
    2. 使用LLM综合总结
    3. 生成复盘报告和改进建议
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("review_manager_v2", llm)

        result = agent.execute({
            "trade_info": {...},
            "timing_analysis": "...",
            "position_analysis": "...",
            "emotion_analysis": "...",
            "attribution_analysis": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="review_manager_v2",
        name="复盘总结师 v2.0",
        description="综合所有分析维度，生成完整复盘报告和改进建议",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    manager_type = "review_manager"
    output_field = "review_summary"
    enable_debate = False

    def __init__(self, *args, **kwargs):
        """初始化复盘总结师 v2.0"""
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

    def _build_system_prompt(self) -> str:
        """构建系统提示词（包含交易计划规则）"""
        fallback_prompt = """您是一位专业的复盘总结师 v2.0。

您的职责是综合各维度分析，生成完整的复盘报告。

**总结要点**：
1. 整体评价 - 综合评分和总体评价
2. 优点识别 - 本次交易的优点
3. 不足分析 - 本次交易的不足
4. 改进建议 - 具体的改进措施
5. 经验总结 - 可复用的经验教训

请使用中文，基于真实数据进行客观总结。

输出格式要求：
请给出JSON格式的复盘报告：
```json
{
    "overall_score": 85,
    "timing_score": 80,
    "position_score": 90,
    "discipline_score": 85,
    "summary": "2-3句话的综合评价（必须是字符串，不能是对象）",
    "strengths": ["优点1", "优点2", "优点3"],
    "weaknesses": ["不足1", "不足2", "不足3"],
    "suggestions": ["建议1", "建议2", "建议3"],
    "lessons": "经验教训总结（必须是字符串）"
}
```

**重要提示**：
1. overall_score、timing_score、position_score、discipline_score 必须是 1-10 的整数
2. overall_score 应该是 timing_score、position_score、discipline_score 的平均值（四舍五入）
3. summary 和 lessons 必须是字符串，不能是对象或数组
4. strengths、weaknesses、suggestions 必须是字符串数组
5. 请根据实际分析给出真实的评分，不要使用示例中的默认值
6. 不要在输出中包含日期（如"2025年4月5日"），日期由系统自动生成"""

        # 🆕 从 state 获取交易计划（如果有）
        trading_plan = None
        if self._current_state:
            trading_plan = self._current_state.get('trading_plan')

        # 🆕 构建交易计划规则文本
        trading_plan_section = ''
        if trading_plan:
            plan_name = trading_plan.get('plan_name', '未命名计划')
            trading_plan_section = f"""

=== 交易计划合规性 ===
本次交易关联了交易计划：**{plan_name}**

请在复盘报告中增加"交易计划合规性"部分，总结：
1. 各维度分析中发现的规则违反情况
2. 合规性总体评价
3. 针对规则违反的改进建议"""

        if get_agent_prompt:
            try:
                # 🆕 传递交易计划规则文本作为变量
                variables = {
                    'trading_plan_section': trading_plan_section
                }

                prompt = get_agent_prompt(
                    agent_type="reviewers_v2",
                    agent_name="review_manager_v2",
                    variables=variables,
                    preference_id="neutral",
                    fallback_prompt=fallback_prompt
                )
                if prompt:
                    has_plan = "（包含交易计划规则）" if trading_plan else "（无交易计划）"
                    logger.info(f"✅ 从模板系统获取复盘总结师提示词 {has_plan} (长度: {len(prompt)})")
                    logger.info(f"📝 [系统提示词] 完整内容:\n{prompt}")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")

        logger.info(f"⚠️ 使用降级提示词 (长度: {len(fallback_prompt + trading_plan_section)})")
        logger.info(f"📝 [降级提示词] 完整内容:\n{fallback_prompt + trading_plan_section}")
        return fallback_prompt + trading_plan_section

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        inputs: Dict[str, str],
        debate_summary: str,
        state: Dict[str, Any]
    ) -> str:
        """构建用户提示词（只包含分析数据，不包含交易计划规则）

        注意：交易计划规则已经在系统提示词中注入，这里只需要提供分析数据。
        """
        trade_info = state.get("trade_info", {})
        code = trade_info.get("code", ticker)

        # 提取各维度分析（在 f-string 外进行切片）
        timing = state.get("timing_analysis", "无时机分析")
        position = state.get("position_analysis", "无仓位分析")
        emotion = state.get("emotion_analysis", "无情绪分析")
        attribution = state.get("attribution_analysis", "无归因分析")

        # 截断长文本（避免 token 过多）
        timing_text = timing[:1500] if isinstance(timing, str) else str(timing)[:1500]
        position_text = position[:1500] if isinstance(position, str) else str(position)[:1500]
        emotion_text = emotion[:1500] if isinstance(emotion, str) else str(emotion)[:1500]
        attribution_text = attribution[:1500] if isinstance(attribution, str) else str(attribution)[:1500]

        user_prompt = f"""请综合以下分析，生成复盘报告：

=== 交易信息 ===
- 股票代码: {code}
- 盈亏金额: {trade_info.get('pnl', 0):.2f}元
- 收益率: {trade_info.get('return_rate', 0):.2%}
- 持仓周期: {trade_info.get('holding_period', 0)}天

=== 时机分析 ===
{timing_text}

=== 仓位分析 ===
{position_text}

=== 情绪分析 ===
{emotion_text}

=== 归因分析 ===
{attribution_text}

请给出JSON格式的复盘报告。"""

        logger.info(f"📝 [用户提示词] 完整内容:\n{user_prompt}")
        return user_prompt

    def _get_required_inputs(self) -> List[str]:
        """获取需要的输入列表"""
        return [
            "timing_analysis",
            "position_analysis",
            "emotion_analysis",
            "attribution_analysis"
        ]

