"""
仓位分析师 v2.0 (复盘分析)

基于ResearcherAgent基类实现的仓位分析师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier
from ...registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt, get_user_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None
    get_user_prompt = None


@register_agent
class PositionAnalystV2(ResearcherAgent):
    """
    仓位分析师 v2.0 (复盘分析)
    
    功能：
    - 分析仓位控制和加减仓策略
    - 评估仓位与风险的匹配度
    - 分析资金利用效率
    
    工作流程：
    1. 读取交易信息和仓位历史
    2. 使用LLM分析仓位管理
    3. 生成仓位分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("position_analyst_v2", llm)

        result = agent.execute({
            "trade_info": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="position_analyst_v2",
        name="仓位分析师 v2.0",
        description="分析仓位控制和加减仓策略的合理性",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )

    researcher_type = "review_position"
    stance = "neutral"
    output_field = "position_analysis"

    def __init__(self, *args, **kwargs):
        """初始化仓位分析师 v2.0"""
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

    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（包含交易计划规则）
        
        Args:
            stance: 研究立场
            state: 工作流状态（可选，用于提取变量如 company_name, ticker 等）
        """
        # 降级提示词（当模板系统不可用时使用）
        fallback_prompt = """您是一位专业的仓位分析师 v2.0。

您的职责是分析仓位管理的合理性。

**分析要点**：
1. 初始仓位 - 首次建仓比例是否合理
2. 加减仓策略 - 加减仓时机和比例
3. 风险匹配 - 仓位与风险的匹配度
4. 资金效率 - 资金利用效率
5. 仓位评分 - 0-100分的仓位管理评分

**重要约束**：
- 必须使用用户提示词中提供的真实数据（股票代码、股票名称、收益金额、收益率等）
- 不要在报告中编造或硬编码任何数据
- 报告中的所有数字必须与提示词中提供的数据完全一致
- 不要生成日期信息（如"分析日期：2025年4月5日"），日期由系统自动生成

请使用中文，基于真实数据进行客观分析。"""

        # 🆕 从 state 获取交易计划（如果有）
        trading_plan = None
        if self._current_state:
            trading_plan = self._current_state.get('trading_plan')

        # 🆕 构建交易计划规则文本
        trading_plan_section = ''
        if trading_plan:
            plan_name = trading_plan.get('plan_name', '未命名计划')
            position_rules = trading_plan.get('rules', {}).get('position', {})
            single_stock_limit = position_rules.get('single_stock_limit')
            max_stocks = position_rules.get('max_stocks')

            if single_stock_limit or max_stocks:
                trading_plan_section = f"""

=== 关联的交易计划 ===
本次交易关联了交易计划：**{plan_name}**

**仓位规则**：
- 单只股票上限: {single_stock_limit}%
- 最大持股数: {max_stocks}只

**请在分析中重点检查**：
1. 仓位是否超过单只股票上限
2. 加减仓操作是否合理
3. 如有违反规则的地方，请明确指出"""

        # 使用基类的通用方法从模板系统获取提示词（支持注入交易计划规则，参考 research_manager_v2）
        logger.info("🔍 [PositionAnalystV2] 开始构建系统提示词")
        
        variables = {'trading_plan_section': trading_plan_section} if trading_plan_section else {}
        prompt = self._get_prompt_from_template(
            agent_type="reviewers_v2",
            agent_name="position_analyst_v2",
            variables=variables,  # 特殊变量：trading_plan_section（如果有）
            state=self._current_state if self._current_state else state,  # 🔑 传递 state，基类会自动提取系统变量
            context=self._current_state.get("context") if self._current_state else (state.get("context") if state else None),  # 从 state 中获取 context
            fallback_prompt=fallback_prompt,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
        if prompt:
            has_plan = "（包含交易计划规则）" if trading_plan else "（无交易计划）"
            logger.info(f"✅ 从模板系统获取仓位分析师提示词 {has_plan} (长度: {len(prompt)})")
            return prompt

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
        """构建用户提示词（从模板系统获取并渲染）

        注意：交易计划规则已经在系统提示词中注入，这里只需要提供交易数据。
        """
        trade_info = state.get("trade_info", {})
        code = trade_info.get("code", ticker)
        name = trade_info.get("name", code)  # 获取股票名称，如果没有则使用代码
        trades = trade_info.get("trades", [])

        # 分析仓位变化
        position_changes = []
        current_position = 0
        for t in trades:
            side = t.get("side", "")
            qty = t.get("quantity", 0)
            if side == "buy":
                current_position += qty
            else:
                current_position -= qty
            position_changes.append(
                f"- {t.get('date', 'N/A')}: {side} {qty}股, 当前持仓: {current_position}股"
            )
        position_str = "\n".join(position_changes) if position_changes else "无仓位变化"

        # 格式化收益信息
        realized_pnl = trade_info.get('realized_pnl', 0)
        realized_pnl_pct = trade_info.get('realized_pnl_pct', 0)
        # 🆕 获取浮动盈亏（持仓中时）
        unrealized_pnl = trade_info.get('unrealized_pnl', 0)
        unrealized_pnl_pct = trade_info.get('unrealized_pnl_pct', 0)
        is_holding = trade_info.get('is_holding', False)
        
        # 🆕 计算总盈亏（已实现 + 浮动）
        total_pnl = realized_pnl + unrealized_pnl if is_holding else realized_pnl
        total_pnl_pct = realized_pnl_pct + unrealized_pnl_pct if is_holding else realized_pnl_pct
        
        pnl_sign = "+" if total_pnl >= 0 else ""
        unrealized_sign = "+" if unrealized_pnl >= 0 else ""

        # 准备模板变量
        template_variables = {
            'code': code,
            'name': name,
            'trade_count': len(trades),
            'pnl_sign': pnl_sign,
            'realized_pnl': f"{realized_pnl:.2f}",
            'realized_pnl_pct': f"{realized_pnl_pct:.2f}",
            # 🆕 添加浮动盈亏和总盈亏
            'unrealized_pnl': f"{unrealized_pnl:.2f}",
            'unrealized_pnl_pct': f"{unrealized_pnl_pct:.2f}",
            'unrealized_sign': unrealized_sign,
            'total_pnl': f"{total_pnl:.2f}",
            'total_pnl_pct': f"{total_pnl_pct:.2f}",
            'is_holding': "是" if is_holding else "否",
            'position_changes': position_str
        }

        # 🆕 构建收益信息文本（包含浮动盈亏）- 用于模板变量
        if is_holding and unrealized_pnl != 0:
            pnl_info_text = f"{pnl_sign}{total_pnl:.2f}元 (已实现: {realized_pnl:+.2f}元, 浮动: {unrealized_sign}{unrealized_pnl:.2f}元)"
            return_info_text = f"{pnl_sign}{total_pnl_pct:.2f}% (已实现: {realized_pnl_pct:+.2f}%, 浮动: {unrealized_sign}{unrealized_pnl_pct:.2f}%)"
        else:
            pnl_info_text = f"{pnl_sign}{total_pnl:.2f}元"
            return_info_text = f"{pnl_sign}{total_pnl_pct:.2f}%"
        
        template_variables['pnl_info'] = pnl_info_text
        template_variables['return_info'] = return_info_text
        template_variables['holding_status'] = f"{'持仓中' if is_holding else '已平仓'}"
        
        # 降级提示词（如果模板系统不可用）
        fallback_prompt = f"""请分析以下交易的仓位管理：

=== 交易信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 交易次数: {len(trades)}
- 盈亏金额: {pnl_info_text}
- 收益率: {return_info_text}
- 持仓状态: {'持仓中' if is_holding else '已平仓'}

=== 仓位变化 ===
{position_str}

**重要提示**：
- 请在报告标题中使用上述提供的股票代码和股票名称
- 报告中的所有数据（收益金额、收益率等）必须与上述提供的数据完全一致
- 不要编造或修改任何数据

请撰写详细的仓位分析报告，包括：
1. 初始仓位评估
2. 加减仓策略分析
3. 仓位与风险匹配度
4. 资金利用效率
5. 仓位管理评分（0-100分）"""

        # 打印模板变量（调试用）
        logger.info(f"📊 [仓位分析师] 模板变量:")
        for key, value in template_variables.items():
            logger.info(f"  - {key}: {value}")

        # 尝试从模板系统获取用户提示词
        if get_user_prompt:
            try:
                prompt = get_user_prompt(
                    agent_type="reviewers_v2",
                    agent_name="position_analyst_v2",
                    variables=template_variables,
                    preference_id="neutral",
                    fallback_prompt=fallback_prompt
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取仓位分析师用户提示词 (长度: {len(prompt)})")
                    logger.info(f"📝 [仓位分析师] 最终用户提示词:\n{prompt}")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取用户提示词失败: {e}")

        # 降级：使用硬编码提示词
        logger.info(f"📝 [仓位分析师] 使用降级提示词:\n{fallback_prompt}")
        return fallback_prompt

    def _get_required_reports(self) -> List[str]:
        """获取需要的数据列表"""
        return ["trade_info"]

