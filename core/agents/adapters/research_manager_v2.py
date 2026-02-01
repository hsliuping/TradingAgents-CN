"""
研究经理Agent v2.0

基于ManagerAgent基类实现的研究经理
综合看涨和看跌观点，做出最终分析结果
"""

import logging
from typing import Any, Dict, List, Optional

from ..manager import ManagerAgent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入工具函数
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None

try:
    from tradingagents.utils.template_client import get_agent_prompt, get_user_prompt
except (ImportError, KeyError):
    logger.warning("无法导入get_agent_prompt/get_user_prompt，将使用默认提示词")
    get_agent_prompt = None
    get_user_prompt = None

# 不再需要直接导入 get_agent_prompt/get_user_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class ResearchManagerV2(ManagerAgent):
    """
    研究经理 v2.0
    
    功能：
    - 综合看涨和看跌观点
    - 主持辩论（可选）
    - 做出最终分析结果
    - 生成投资计划
    
    工作流程：
    1. 读取看涨报告和看跌报告
    2. 主持辩论（可选）
    3. 综合研判
    4. 生成投资分析观点（看涨/中性/看跌）
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("research_manager_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "bull_report": "...",
            "bear_report": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="research_manager_v2",
        name="研究经理 v2.0",
        description="综合看涨和看跌观点，做出最终分析结果",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 管理者不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="bull_report", type="string", description="看涨观点报告"),
            AgentInput(name="bear_report", type="string", description="看跌观点报告"),
        ],
        outputs=[
            AgentOutput(name="investment_advice", type="string", description="投资分析观点"),
        ],
        requires_tools=False,
        output_field="investment_advice",
        report_label="【投资分析观点 v2】",
    )
    
    # 管理者类型
    manager_type = "research"
    
    # 输出字段名
    output_field = "investment_plan"

    # 是否启用辩论
    enable_debate = True

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行研究经理决策

        重写父类方法以添加 investment_debate_state 输出，
        确保与报告格式化器兼容
        """
        logger.info("=" * 80)
        logger.info("🔍 [ResearchManagerV2] 开始执行投资决策")
        logger.info("=" * 80)

        # 🔍 检查输入数据
        ticker = state.get("ticker", "未知")
        bull_report = state.get("bull_report", "")
        bear_report = state.get("bear_report", "")

        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📈 看涨报告类型: {type(bull_report)}, 长度: {len(str(bull_report))} 字符")
        logger.info(f"📉 看跌报告类型: {type(bear_report)}, 长度: {len(str(bear_report))} 字符")

        # 转换为字符串（如果不是）
        bull_report_str = str(bull_report) if bull_report else ""
        bear_report_str = str(bear_report) if bear_report else ""

        if bull_report_str and len(bull_report_str) > 10:
            logger.info(f"📈 看涨报告前200字符: {bull_report_str[:200]}...")
        else:
            logger.warning("⚠️ 看涨报告为空或过短！")

        if bear_report_str and len(bear_report_str) > 10:
            logger.info(f"📉 看跌报告前200字符: {bear_report_str[:200]}...")
        else:
            logger.warning("⚠️ 看跌报告为空或过短！")

        # 调用父类方法获取基本输出
        logger.info("🚀 调用父类 execute 方法...")
        result = super().execute(state)
        logger.info("✅ 父类 execute 方法执行完成")

        # 提取决策内容
        decision_value = result.get(self.output_field, "")
        logger.info(f"📝 决策输出字段: {self.output_field}")
        logger.info(f"📝 决策内容类型: {type(decision_value)}")
        logger.info(f"📝 决策内容长度: {len(str(decision_value))} 字符")

        # 🔥 修复：如果是字典（包含 content 字段），提取 content
        if isinstance(decision_value, dict):
            decision_content = decision_value.get("content", "")
            logger.info(f"📝 从字典中提取 content: {len(decision_content)} 字符")
        else:
            decision_content = decision_value
            logger.info(f"📝 直接使用决策内容: {len(decision_content)} 字符")

        # 从 state 中获取现有的 investment_debate_state（如果有）
        existing_debate_state = state.get("investment_debate_state", {})

        # 构建新的 investment_debate_state，包含 judge_decision
        new_debate_state = {
            "judge_decision": decision_content,  # ✅ 关键：添加 judge_decision 字段
            "history": existing_debate_state.get("history", ""),
            "bull_history": existing_debate_state.get("bull_history", ""),
            "bear_history": existing_debate_state.get("bear_history", ""),
            "current_response": decision_content,
            "count": existing_debate_state.get("count", 0),
        }

        logger.info("✅ [ResearchManagerV2] 投资决策执行完成")
        logger.info("=" * 80)

        # 返回包含 investment_debate_state 的结果
        return {
            **result,
            "investment_debate_state": new_debate_state,
        }
    
    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）

        Args:
            state: 工作流状态（用于提取模板变量）

        Returns:
            系统提示词
        """
        logger.info("🔍 [ResearchManagerV2] 开始构建系统提示词")
        
        if state is None:
            state = {}
        
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        # 注意：虽然系统提示词通常不需要变量，但某些模板可能需要 ticker、current_date 等
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        template_variables = {}
        
        # 如果 state 中有 ticker 和 analysis_date，提取它们（系统提示词模板可能需要）
        if "ticker" in state:
            template_variables["ticker"] = state["ticker"]
        if "analysis_date" in state or "trade_date" in state:
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            if analysis_date:
                # 确保日期格式正确
                if isinstance(analysis_date, str) and len(analysis_date) > 10:
                    analysis_date = analysis_date.split()[0]
                template_variables["current_date"] = analysis_date
                template_variables["analysis_date"] = analysis_date

        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="managers_v2",  # ✅ 修复：使用 v2 类型
            agent_name="research_manager_v2",  # ✅ 修复：使用 v2 名称
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # ✅ 关键：指定获取系统提示词（包含output_format）
        )

        # 检查是否成功获取提示词
        if prompt:
            logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
            logger.info(f"📝 系统提示词前500字符:\n{prompt[:500]}...")

            # 检查是否包含价格分析区间指导
            if "价格分析区间" in prompt:
                logger.info("✅ 系统提示词包含【价格分析区间】指导")
            else:
                logger.warning("⚠️ 系统提示词不包含【价格分析区间】指导（可能使用旧版提示词）")

            logger.debug(f"✅ 从模板系统获取研究经理系统提示词")
            return prompt
        else:
            logger.warning("⚠️ 从模板系统获取系统提示词失败，使用默认提示词")
        
        # 默认提示词（合规版本）
        return """你是一位中性的研究经理，需要综合看涨和看跌观点做出分析。

**分析风格**: 中性的分析风格，客观评估，平衡分析，提供理性判断

**核心职责**:
1. 综合分析看涨和看跌观点
2. 权衡双方的理由和证据
3. 做出中性、理性的市场分析
4. 给出明确的市场观点（看涨/看跌/中性）

**分析原则**:
- 客观权衡看涨和看跌观点，基于证据做出理性分析
- 平衡的风险收益比分析
- 客观、理性、基于证据
- 详细说明分析理由
- 使用中文输出

**工具使用指导**:

基于提供的分析报告进行中性的综合分析。
从中性角度评估所有信息。

**免责声明**：
本分析报告仅供参考，不构成交易建议。所有市场观点、价格区间均为分析参考，
不构成交易操作建议。投资有风险，决策需谨慎。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        inputs: Dict[str, Any],
        debate_summary: Optional[str],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            inputs: 收集的输入字典
            debate_summary: 辩论总结
            state: 工作流状态

        Returns:
            用户提示词
        """
        logger.info("🔍 [ResearchManagerV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        logger.info(f"📝 输入字段: {list(inputs.keys())}")

        # 检查看涨和看跌报告
        bull_report = inputs.get("bull_report", "")
        bear_report = inputs.get("bear_report", "")

        # 转换为字符串（如果不是）
        bull_report_str = str(bull_report) if bull_report else ""
        bear_report_str = str(bear_report) if bear_report else ""

        logger.info(f"📈 看涨报告类型: {type(bull_report)}, 长度: {len(bull_report_str)} 字符")
        logger.info(f"📉 看跌报告类型: {type(bear_report)}, 长度: {len(bear_report_str)} 字符")

        if bull_report_str and len(bull_report_str) > 10:
            # 检查是否包含价格信息
            if "价位" in bull_report_str or "价格" in bull_report_str or "¥" in bull_report_str:
                logger.info("✅ 看涨报告包含价格信息")
            else:
                logger.warning("⚠️ 看涨报告可能不包含价格信息")
        else:
            logger.warning("⚠️ 看涨报告为空或过短！")

        if bear_report_str and len(bear_report_str) > 10:
            # 检查是否包含价格信息
            if "价位" in bear_report_str or "价格" in bear_report_str or "¥" in bear_report_str:
                logger.info("✅ 看跌报告包含价格信息")
            else:
                logger.warning("⚠️ 看跌报告可能不包含价格信息")
        else:
            logger.warning("⚠️ 看跌报告为空或过短！")

        # 获取公司名称
        if StockUtils:
            market_info = StockUtils.get_market_info(ticker)
            company_name = self._get_company_name(ticker, market_info)
        else:
            company_name = ticker
        
        # 从 state 中获取当前价格
        current_price = state.get("current_price", "未知")
        logger.info(f"💰 当前价格: {current_price} (来源: state)")

        # 🆕 提取报告内容（如果是字典，取 content 字段）
        def extract_content(report):
            """从报告中提取纯文本内容"""
            if isinstance(report, dict):
                return report.get('content', str(report))
            return str(report) if report else "无"

        bull_report_content = extract_content(inputs.get("bull_report"))
        bear_report_content = extract_content(inputs.get("bear_report"))

        logger.info(f"📈 看涨报告内容长度: {len(bull_report_content)} 字符")
        logger.info(f"📉 看跌报告内容长度: {len(bear_report_content)} 字符")

        # 🆕 检测辩论模式并获取辩论历史
        debate_history = ""
        is_debate_mode = "investment_debate_state" in state and isinstance(state.get("investment_debate_state"), dict)

        if is_debate_mode:
            debate_state = state.get("investment_debate_state", {})
            full_history = debate_state.get("history", "")
            bull_history = debate_state.get("bull_history", "")
            bear_history = debate_state.get("bear_history", "")

            if full_history:
                debate_history = f"\n【完整辩论历史】\n{full_history}\n"
                logger.info(f"💬 [辩论模式] 读取到辩论历史，长度: {len(full_history)} 字符")
            else:
                logger.info("💬 [辩论模式] 辩论历史为空")
        else:
            logger.info("📝 [单次分析模式] 无辩论历史")

        # 准备模板变量
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
            "current_price": current_price,  # ✅ 添加当前价格
            "bull_report": bull_report_content,  # ✅ 只传递内容，不传递字典
            "bear_report": bear_report_content,  # ✅ 只传递内容，不传递字典
            "debate_summary": debate_summary or "无辩论总结",
            "debate_history": debate_history,  # 🆕 添加辩论历史
        }

        # 添加其他输入到模板变量
        for key, value in inputs.items():
            if key not in ["bull_report", "bear_report"]:
                template_variables[key] = str(value) if value else ""

        # 使用基类的通用方法获取用户提示词（基类会自动从 state 中提取系统变量）
        prompt = self._get_prompt_from_template(
            agent_type="managers_v2",  # ✅ 修复：使用 v2 类型
            agent_name="research_manager_v2",  # ✅ 修复：使用 v2 名称
            variables=template_variables,
            state=state,  # 🆕 传递 state，基类会自动提取系统变量
            context=state,
            fallback_prompt=None,
            prompt_type="user"  # 🆕 指定获取用户提示词
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取研究经理用户提示词 (长度: {len(prompt)})")
            return prompt
        
        # 🆕 判断交易风格（用于权重设置）
        trading_style = state.get("trading_style")  # 从state获取交易风格（如果有）
        
        # 降级：使用默认提示词
        prompt = f"""请综合分析 {company_name}（{ticker}）的投资机会：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}

"""
        
        # 🆕 根据交易风格设置看涨/看跌观点的权重
        bull_report = inputs.get("bull_report", "")
        bear_report = inputs.get("bear_report", "")
        
        if trading_style == "short":
            # 短线：看涨和看跌观点权重相等（各50%）
            prompt += f"""【看涨观点】（权重50%，请重点关注）
{bull_report}

【看跌观点】（权重50%，请重点关注）
{bear_report}
"""
        elif trading_style == "long":
            # 中长线：看涨和看跌观点权重相等（各50%）
            prompt += f"""【看涨观点】（权重50%，请重点关注）
{bull_report}

【看跌观点】（权重50%，请重点关注）
{bear_report}
"""
        else:
            # 默认：看涨和看跌观点权重相等
            if bull_report:
                prompt += f"\n【看涨观点】\n{bull_report}\n"
            if bear_report:
                prompt += f"\n【看跌观点】\n{bear_report}\n"
        
        # 添加辩论总结
        if debate_summary:
            prompt += f"\n【辩论总结】\n{debate_summary}\n"
        
        # 添加其他输入
        for key, value in inputs.items():
            if key not in ["bull_report", "bear_report"]:
                prompt += f"\n【{key}】\n{value}\n"
        
        prompt += """
请基于以上信息，综合分析并给出市场观点。

**权重说明**：
- 看涨观点和看跌观点权重相等（各50%），请同等重视
- 请客观权衡双方观点，基于证据做出理性分析

**⏰ 时间上下文说明**：
- 当前分析日期：{analysis_date}
- 如果分析中提到"等待财报"或"等待年报"，请注意：
  * 不要指定具体年份（如"等待2024年年报"）
  * 直接说"等待年报发布"或"等待下一期财报"
  * 或根据当前月份智能判断（1-4月等待上一年度年报，5-12月等待本年度年报）

**免责声明**：
本分析报告仅供参考，不构成交易建议。所有市场观点、价格区间均为分析参考，
不构成交易操作建议。投资有风险，决策需谨慎。
""".format(analysis_date=analysis_date)

        logger.info(f"📝 用户提示词总长度: {len(prompt)} 字符")
        logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")

        # 检查是否包含分析步骤指导
        if "分析步骤" in prompt and "提取关键数据" in prompt:
            logger.info("✅ 用户提示词包含【分析步骤】指导")
        else:
            logger.warning("⚠️ 用户提示词不包含【分析步骤】指导")

        return prompt
    
    def _get_required_inputs(self) -> List[str]:
        """
        获取需要的输入列表
        
        Returns:
            输入字段名列表
        """
        return [
            "bull_report",
            "bear_report",
        ]
    
    def _get_company_name(self, ticker: str, market_info: dict) -> str:
        """获取公司名称"""
        try:
            if market_info['is_china']:
                from tradingagents.dataflows.interface import get_china_stock_info_unified
                stock_info = get_china_stock_info_unified(ticker)
                if stock_info and "股票名称:" in stock_info:
                    return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            elif market_info['is_hk']:
                from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                return get_hk_company_name_improved(ticker)
            elif market_info['is_us']:
                us_stock_names = {
                    'AAPL': '苹果公司', 'TSLA': '特斯拉', 'NVDA': '英伟达',
                    'MSFT': '微软', 'GOOGL': '谷歌', 'AMZN': '亚马逊',
                }
                return us_stock_names.get(ticker.upper(), f"美股{ticker}")
        except Exception as e:
            logger.warning(f"获取公司名称失败: {e}")
        
        return f"股票{ticker}"

