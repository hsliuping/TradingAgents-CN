"""
研究整合员 Agent v2.0

基于 TraderAgent 基类实现的研究整合员。
根据研究分析观点生成研究整合意见。
"""

import logging
from typing import Any, Dict, List, Optional

from ..trader import TraderAgent
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
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError):
    logger.warning("无法导入get_agent_prompt，将使用默认提示词")
    get_agent_prompt = None

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class TraderV2(TraderAgent):
    """
    研究整合员 v2.0
    
    功能：
    - 根据研究分析观点生成研究整合意见
    - 提炼关键信号、约束条件和风险提示
    - 汇总后续观察重点
    
    工作流程：
    1. 读取投资计划和所有分析报告
    2. 分析研究信号
    3. 生成研究整合意见
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("trader_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "investment_plan": {...},
            "market_report": "...",
            "risk_assessment": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="trader_v2",
        name="研究整合员 v2.0",
        description="根据研究分析观点生成研究整合意见",
        category=AgentCategory.TRADER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 研究整合员不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_advice", type="string", description="研究分析观点"),
        ],
        outputs=[
            AgentOutput(name="trader_investment_plan", type="string", description="研究整合意见"),
        ],
        requires_tools=False,
        output_field="trader_investment_plan",
        report_label="【研究整合意见 v2】",
    )

    # 输出字段名（与报告格式化器期望的字段名一致）
    output_field = "trader_investment_plan"
    
    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）
        
        Args:
            state: 工作流状态（用于提取模板变量）
        
        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        logger.info("🔍 [TraderV2] 开始构建系统提示词")
        
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
        
        prompt = self._get_prompt_from_template(
            agent_type="trader_v2",
            agent_name="trader_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
        if prompt:
            logger.debug("✅ 从模板系统获取研究整合员系统提示词")
            return prompt
        
        # 默认系统提示词（合规版本）
        return """你是一位研究整合员，负责把研究经理结论与多维报告整理成用户可读的研究简报。

    ## 你的职责

    1. **研究摘要**：把当前研究判断翻译成清晰、克制、易理解的结论摘要。
    2. **关键证据**：提炼支持或削弱判断的核心信号，不堆砌细节。
    3. **情景框架**：概括偏多、偏空、中性三种情景分别取决于哪些事实变化。
    4. **信息缺口**：说明现在仍不确定、仍需验证的关键问题。
    5. **观察清单**：列出接下来需要重点跟踪的公开信息和验证事项。

    ## 分析原则

    - **只做研究整合**：输出帮助用户更新认知，不输出交易动作。
    - **强调不确定性**：必须说明信息缺口、关键假设和判断调整条件。
    - **用户可读**：让用户看懂“为什么这样看”以及“接下来观察什么”。
    - **禁止交易化表达**：不得输出目标价、价格区间、关键价位、止损止盈、仓位比例、建仓节奏或操作策略。
    - **缺失材料要明说**：如果研究结论、任一分析报告或历史记录缺失，必须明确写出“材料未提供”或“仍待验证”，不得自行补造。

    ## 重要说明

    - **风险治理不在本阶段**：风险经理会在后续补充风险治理视角。
    - **基于已有数据**：你只能使用提供的研究报告与研究结论，不能补造未提供的信息。

    **免责声明**：
    本研究简报仅供信息参考，不构成交易建议或投资承诺。请结合自身情况独立判断。"""
    
    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        investment_plan: Dict[str, Any],
        all_reports: Dict[str, Any],
        historical_trades: Optional[List[Dict[str, Any]]],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 的实现）
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            investment_plan: 投资计划
            all_reports: 所有报告字典
            historical_trades: 历史交易记录
            state: 工作流状态
            
        Returns:
            用户提示词
        """
        logger.info("🔍 [TraderV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        company_name = ticker
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                company_name = self._get_company_name(ticker, market_info)
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        
        # 🆕 提取报告内容（如果是字典，取 content 字段）
        def extract_content(report):
            """从报告中提取纯文本内容"""
            if isinstance(report, dict):
                return report.get('content', str(report))
            return str(report) if report else ""
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        # 🔑 注意：风险评估（risk_assessment）不在研究整合阶段，它在研究整合之后由风险经理进行
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
            "current_date": analysis_date,
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            # 研究结论（转换为字符串）
            "investment_plan": extract_content(investment_plan) if investment_plan else "",
            # 🔑 可用的分析报告（不包括 risk_assessment）
            "market_report": extract_content(all_reports.get("market_report", "")),
            "fundamentals_report": extract_content(all_reports.get("fundamentals_report", "")),
            "news_report": extract_content(all_reports.get("news_report", "")),
            "sentiment_report": extract_content(all_reports.get("sentiment_report", "")),
            # 历史交易记录（转换为字符串）
            "historical_trades": "\n".join([str(trade) for trade in historical_trades[:3]]) if historical_trades else "",
        }
        
        # 🔑 添加其他报告到模板变量（不包括 risk_assessment）
        # 这些报告包括：sector_report, index_report, bull_report, bear_report 等
        excluded_keys = ["risk_assessment", "market_report", "fundamentals_report", "news_report", "sentiment_report"]
        for key, value in all_reports.items():
            if key not in excluded_keys:
                template_variables[f"report_{key}"] = extract_content(value)
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="trader_v2",
            agent_name="trader_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取研究整合员 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        market_name = state.get("market_name", "")
        industry = state.get("industry", "")
        current_price = state.get("current_price", "")

        target_line = f"{company_name}（{ticker}）"
        if market_name:
            target_line = f"{company_name}（{ticker}，{market_name}）"

        # 降级：使用默认用户提示词（不包含 risk_assessment）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        prompt = f"""基于提供的研究材料生成研究整合简报。
    可用资源：
    - 分析目标：{target_line}
    - 分析日期：{analysis_date}
    - 货币单位：{currency_name}（{currency_symbol}）
    - 当前价格上下文：{current_price or '材料未提供'}
    - 所属行业：{industry or '材料未提供'}
    - 当前研究结论：{extract_content(investment_plan) if investment_plan else '材料未提供'}
    - 市场分析报告：{extract_content(all_reports.get("market_report", "")) or '材料未提供'}
    - 基本面分析报告：{extract_content(all_reports.get("fundamentals_report", "")) or '材料未提供'}
    - 新闻分析报告：{extract_content(all_reports.get("news_report", "")) or '材料未提供'}
    - 情绪分析报告：{extract_content(all_reports.get("sentiment_report", "")) or '材料未提供'}
    - 板块分析报告：{extract_content(all_reports.get("sector_report", "")) or '材料未提供'}
    - 大盘分析报告：{extract_content(all_reports.get("index_report", "")) or '材料未提供'}
    - 看涨研究报告：{extract_content(all_reports.get("bull_report", "")) or '材料未提供'}
    - 看跌研究报告：{extract_content(all_reports.get("bear_report", "")) or '材料未提供'}
    - 历史交易记录：{chr(10).join([str(trade) for trade in historical_trades[:3]]) if historical_trades else '材料未提供'}

    任务重点：
    - 基于上述研究结论和各类分析报告，生成研究摘要、核心依据、情景框架、关键不确定性、后续观察事项和风险提示。
    - 先概括共识，再提炼最关键的证据冲突、信息缺口和判断调整条件。
    - 如果任一资源为空、材料不足或没有明确证据，必须直接写“材料未提供”或“仍待验证”，不得使用模型记忆补全。
    - 情景框架与后续观察事项只能写研究条件变化，不得改写成价格触发、仓位动作、止损止盈或执行节奏。

    严格禁止：
    - 不得输出价格区间、目标价、关键验证位、止损止盈、仓位比例、建仓节奏或执行策略。
    - 不得把观察条件写成“达到某价位后执行什么动作”。
    - 输出应帮助用户理解研究逻辑，而不是告诉用户怎么交易。

    输出格式：
    请使用 Markdown 输出，并严格包含以下标题：
    - `## 研究摘要`
    - `## 核心依据`
    - `## 情景框架`
    - `## 关键不确定性`
    - `## 后续观察事项`
    - `## 风险提示`
    """
        
        return prompt
    
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

