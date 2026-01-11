"""
交易员Agent v2.0

基于TraderAgent基类实现的交易员
根据投资计划生成具体的交易指令
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
    - 根据投资计划生成具体交易指令
    - 确定买入价格、数量、止损位、止盈位
    - 考虑风险控制和资金管理
    
    工作流程：
    1. 读取投资计划和所有分析报告
    2. 确定交易参数
    3. 生成具体交易指令
    
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
        description="根据投资计划生成具体的交易指令",
        category=AgentCategory.TRADER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 交易员不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_advice", type="string", description="投资建议"),
        ],
        outputs=[
            AgentOutput(name="trader_investment_plan", type="string", description="交易计划"),
        ],
        requires_tools=False,
        output_field="trader_investment_plan",
        report_label="【交易计划 v2】",
    )

    # 输出字段名（与报告格式化器期望的字段名一致）
    output_field = "trader_investment_plan"
    
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词
        
        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="trader_v2",
            agent_name="trader_v2",
            variables={},
            context=None,
            fallback_prompt=None
        )
        if prompt:
            logger.debug("✅ 从模板系统获取交易员系统提示词")
            return prompt
        
        # 默认提示词
        return """你是一位专业交易员，需要根据投资计划生成具体的交易指令。

你的职责：
1. 根据投资计划确定交易方向（买入/卖出/持有）
2. 确定买入价格（市价/限价）
3. 确定交易数量（考虑资金管理）
4. 设置止损位（控制风险）
5. 设置止盈位（锁定利润）

交易要求：
- 严格执行投资计划
- 合理的风险控制
- 明确的交易参数
- 考虑市场流动性
- 使用中文输出

输出格式：
请以结构化的方式输出交易计划，包括：
- 交易方向（买入/卖出/持有）
- 建议价格
- 交易数量
- 止损位
- 止盈位
- 风险提示
"""
    
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
        构建用户提示词
        
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
        # 获取公司名称和市场信息
        if StockUtils:
            market_info = StockUtils.get_market_info(ticker)
            company_name = self._get_company_name(ticker, market_info)
            currency = market_info['currency_name']
            currency_symbol = market_info['currency_symbol']
        else:
            company_name = ticker
            currency = "人民币"
            currency_symbol = "¥"
        
        # 构建提示词
        prompt = f"""请为 {company_name}（{ticker}）生成交易计划：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}
货币单位：{currency}（{currency_symbol}）

"""
        
        # 添加投资计划
        prompt += f"\n【投资计划】\n"
        if isinstance(investment_plan, dict):
            for key, value in investment_plan.items():
                prompt += f"{key}: {value}\n"
        else:
            prompt += f"{investment_plan}\n"
        
        # 添加风险评估
        if "risk_assessment" in all_reports:
            prompt += f"\n【风险评估】\n{all_reports['risk_assessment']}\n"
        
        # 添加市场分析
        if "market_report" in all_reports:
            prompt += f"\n【市场分析】\n{all_reports['market_report']}\n"
        
        # 添加历史交易记录
        if historical_trades:
            prompt += f"\n【历史交易】\n"
            for i, trade in enumerate(historical_trades[:3], 1):  # 只显示最近3笔
                prompt += f"{i}. {trade}\n"
        
        # 添加其他报告摘要
        other_reports = [k for k in all_reports.keys() if k not in ["risk_assessment", "market_report"]]
        if other_reports:
            prompt += f"\n【其他参考报告】\n"
            for key in other_reports[:3]:  # 只显示前3个
                value = all_reports[key]
                if isinstance(value, str):
                    prompt += f"{key}: {value[:200]}...\n"
                else:
                    prompt += f"{key}: {value}\n"
        
        prompt += f"\n请给出具体的交易指令（买入价、数量、止损、止盈），货币单位使用{currency}。"
        
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

