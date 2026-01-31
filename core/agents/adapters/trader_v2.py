"""
交易员Agent v2.0

基于TraderAgent基类实现的交易员
根据投资分析观点生成交易分析计划
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
    交易员 v2.0
    
    功能：
    - 根据投资分析观点生成交易分析计划
    - 分析价格区间、仓位配置、风险控制参考价位
    - 考虑风险控制和资金管理
    
    工作流程：
    1. 读取投资计划和所有分析报告
    2. 分析交易参数
    3. 生成交易分析计划
    
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
        name="交易员 v2.0",
        description="根据投资分析观点生成交易分析计划",
        category=AgentCategory.TRADER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 交易员不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_advice", type="string", description="投资分析观点"),
        ],
        outputs=[
            AgentOutput(name="trader_investment_plan", type="string", description="交易分析计划"),
        ],
        requires_tools=False,
        output_field="trader_investment_plan",
        report_label="【交易分析计划 v2】",
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
            logger.debug("✅ 从模板系统获取交易员系统提示词")
            return prompt
        
        # 默认系统提示词（合规版本）
        return """你是一位专业的投资分析师，负责根据投资分析观点生成交易分析计划。

## 你的职责

1. **市场观点分析**：根据投资计划分析市场观点（看涨/看跌/中性）
2. **价格分析区间**：基于技术面和基本面分析价格区间（不构成目标价）
3. **仓位分析**：分析合理的仓位配置（不构成操作建议）
4. **风险控制参考**：提供风险控制参考价位（仅供参考）
5. **收益预期参考**：提供收益预期参考价位（仅供参考）

## 分析原则

- **基于投资分析观点**：参考投资计划中的市场观点（看涨/看跌/中性）进行分析
- **客观的风险分析**：提供风险控制参考价位，不构成操作建议
- **明确的分析参数**：提供清晰的价格分析区间、仓位分析、风险参考价位
- **考虑市场流动性**：分析交易执行的可行性
- **资金管理分析**：基于投资计划中的仓位分析进行资金配置分析

## 重要说明

- **风险评估不在本阶段**：风险评估是在交易分析计划制定之后由风险经理进行的，你不需要进行风险评估
- **基于已有数据**：你只能使用提供的分析报告（市场分析、基本面分析、新闻分析、板块分析、大盘分析、看涨报告、看跌报告）来制定交易分析计划
- **遵循投资计划**：投资计划中的 market_view、price_analysis_range、position_analysis 等字段是你的主要参考依据

**免责声明**：
本分析报告仅供参考，不构成投资建议。所有价格区间、市场观点均为分析参考，
不构成买卖操作建议。投资有风险，决策需谨慎。"""
    
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
        # 🔑 注意：风险评估（risk_assessment）不在交易分析计划阶段，它在交易分析计划之后由风险经理进行
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
            "current_date": analysis_date,
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            # 投资计划（转换为字符串）
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
            logger.info(f"✅ 从模板系统获取交易员 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认用户提示词（不包含 risk_assessment）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        prompt = f"""请为 {company_name}（{ticker}）生成交易分析计划：

## 基本信息
- **股票代码**：{ticker}
- **公司名称**：{company_name}
- **分析日期**：{analysis_date}
- **货币单位**：{currency_name}（{currency_symbol}）

## 投资计划

{extract_content(investment_plan) if investment_plan else "无投资计划"}

## 可用分析报告

### 1. 市场分析报告
{extract_content(all_reports.get("market_report", "")) or "无市场分析报告"}

### 2. 基本面分析报告
{extract_content(all_reports.get("fundamentals_report", "")) or "无基本面分析报告"}

### 3. 新闻分析报告
{extract_content(all_reports.get("news_report", "")) or "无新闻分析报告"}

### 4. 板块分析报告
{extract_content(all_reports.get("sector_report", "")) or "无板块分析报告"}

### 5. 大盘分析报告
{extract_content(all_reports.get("index_report", "")) or "无大盘分析报告"}

### 6. 看涨研究报告
{extract_content(all_reports.get("bull_report", "")) or "无看涨研究报告"}

### 7. 看跌研究报告
{extract_content(all_reports.get("bear_report", "")) or "无看跌研究报告"}

## 历史交易记录（如有）

{chr(10).join([str(trade) for trade in historical_trades[:3]]) if historical_trades else "无历史交易记录"}

## 任务要求

请基于上述投资计划和各类分析报告，生成详细的交易分析计划，包括：

1. **市场观点**：看涨/看跌/中性（参考投资计划中的 market_view）
2. **价格分析区间**：基于技术面和基本面的价格分析区间（参考投资计划中的 price_analysis_range，不构成目标价）
3. **仓位分析**：基于风险收益比的仓位分析（参考投资计划中的 position_analysis，不构成操作建议）
4. **风险控制参考价位**：风险控制参考价位（仅供参考，不构成操作建议）
5. **收益预期参考价位**：收益预期参考价位（仅供参考，不构成操作建议）
6. **执行策略分析**：市价单还是限价单的分析，分批建仓还是一次性建仓的分析
7. **风险提示**：交易执行中需要注意的风险点

**重要提示**：
- 必须严格按照投资计划中的 market_view 来确定市场观点
- 价格分析区间应参考投资计划中的 price_analysis_range，但可以根据当前市场价格进行分析
- 仓位分析应参考投资计划中的 position_analysis
- 风险控制参考价位和收益预期参考价位应基于技术分析和风险控制原则提供（仅供参考）
- 使用 {currency_name}（{currency_symbol}）作为货币单位

**免责声明**：
本分析报告仅供参考，不构成投资建议。所有价格区间、市场观点均为分析参考，
不构成买卖操作建议。投资有风险，决策需谨慎。投资者应根据自身情况，结合
专业投资顾问意见，独立做出投资决策。"""
        
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

