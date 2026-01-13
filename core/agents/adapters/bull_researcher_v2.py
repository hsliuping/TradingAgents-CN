"""
看涨研究员Agent v2.0

基于ResearcherAgent基类实现的看涨研究员
从看涨角度综合分析多个报告
"""

import logging
from typing import Any, Dict, List, Optional

from ..researcher import ResearcherAgent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent
from ..utils.weight_calculator import calculate_report_weights, format_weighted_reports_prompt

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
    logger.warning("无法导入模板系统函数，将使用默认提示词")
    get_agent_prompt = None
    get_user_prompt = None

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class BullResearcherV2(ResearcherAgent):
    """
    看涨研究员 v2.0
    
    功能：
    - 从看涨角度综合分析多个报告
    - 找出所有支持买入的理由
    - 生成看涨观点报告
    
    工作流程：
    1. 读取市场报告、新闻报告、基本面报告等
    2. 从看涨角度综合分析
    3. 生成看涨观点报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("bull_researcher_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15",
            "market_report": "...",
            "news_report": "...",
            "fundamentals_report": "..."
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="bull_researcher_v2",
        name="看涨研究员 v2.0",
        description="从看涨角度综合分析多个报告，找出支持买入的理由",
        category=AgentCategory.RESEARCHER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 研究员不需要工具
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False),
        ],
        outputs=[
            AgentOutput(name="bull_report", type="string", description="看涨观点报告"),
        ],
        requires_tools=False,
        output_field="bull_report",
        report_label="【看涨观点 v2】",
    )
    
    # 研究员类型
    researcher_type = "bull"
    
    # 输出字段名
    output_field = "bull_report"
    
    # 研究立场
    stance = "bull"
    
    def _build_system_prompt(self, stance: str) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 研究立场（bull）
            
        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词
        template_variables = {"stance": stance}
        prompt = self._get_prompt_from_template(
            agent_type="researchers_v2",
            agent_name="bull_researcher_v2",
            variables=template_variables,
            context=None,
            fallback_prompt=None
        )
        if prompt:
            logger.debug("✅ 从模板系统获取看涨研究员系统提示词")
            return prompt
        
        # 默认提示词
        return """你是一位看涨研究员，需要从看涨的角度综合分析。

你的职责：
1. 综合分析市场报告、新闻报告、基本面报告等
2. 从看涨角度找出所有支持买入的理由
3. 强调积极因素和上涨潜力
4. 给出看涨观点和建议

分析要求：
- 客观但偏向看涨
- 突出积极因素
- 找出上涨催化剂
- 给出明确的看涨理由
- 使用中文输出

输出格式：
请以结构化的方式输出看涨观点报告，包括：
- 看涨理由（至少3条）
- 上涨催化剂
- 风险提示（客观）
- 综合判断
"""
    
    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, Any],
        historical_context: Optional[str],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（从模板系统获取）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            reports: 收集的报告字典
            historical_context: 历史上下文
            state: 工作流状态

        Returns:
            用户提示词
        """
        # 获取公司名称
        if StockUtils:
            market_info = StockUtils.get_market_info(ticker)
            company_name = self._get_company_name(ticker, market_info)
        else:
            company_name = ticker

        # 🆕 计算报告权重
        trading_style = state.get("trading_style")  # 从state获取交易风格（如果有）
        weights = calculate_report_weights(reports, trading_style)

        # 准备模板变量
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "analysis_date": analysis_date,
        }

        # 添加所有报告到模板变量
        for key, value in reports.items():
            template_variables[key] = str(value) if value else ""

        # 添加历史上下文
        if historical_context:
            template_variables["historical_context"] = historical_context

        # 尝试从模板系统获取用户提示词
        if get_user_prompt:
            try:
                preference_id = state.get("preference_id", "neutral")

                prompt = get_user_prompt(
                    agent_type="researchers_v2",
                    agent_name="bull_researcher_v2",
                    variables=template_variables,
                    preference_id=preference_id,
                    fallback_prompt=None,
                    context=state
                )

                if prompt:
                    logger.info(f"✅ 从模板系统获取看涨研究员用户提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ 从模板系统获取用户提示词失败: {e}，使用降级提示词")

        # 降级：使用硬编码提示词
        prompt = f"""请从看涨角度分析 {company_name}（{ticker}）：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}

"""

        # 🆕 使用权重格式化报告
        if weights:
            # 报告标签映射
            report_labels = {
                "market_report": "市场分析（技术分析）",
                "news_report": "新闻分析",
                "sentiment_report": "社媒分析（市场情绪）",
                "fundamentals_report": "基本面分析",
                "sector_report": "板块分析（行业分析）",
                "index_report": "大盘分析",
            }

            weighted_reports_text = format_weighted_reports_prompt(reports, weights, report_labels)
            prompt += weighted_reports_text
        else:
            # 如果没有权重信息，使用原来的方式（向后兼容）
            if "market_report" in reports:
                prompt += f"\n【市场分析】\n{reports['market_report']}\n"

            if "news_report" in reports:
                prompt += f"\n【新闻分析】\n{reports['news_report']}\n"

            if "fundamentals_report" in reports:
                prompt += f"\n【基本面分析】\n{reports['fundamentals_report']}\n"

            # 添加其他报告
            for key, value in reports.items():
                if key not in ["market_report", "news_report", "fundamentals_report"]:
                    prompt += f"\n【{key}】\n{value}\n"

        # 添加历史上下文
        if historical_context:
            prompt += f"\n【历史上下文】\n{historical_context}\n"

        prompt += "\n请给出详细的看涨观点和理由。"

        return prompt
    
    def _get_required_reports(self) -> List[str]:
        """
        获取需要的报告列表
        
        Returns:
            报告字段名列表
        """
        return [
            "market_report",
            "news_report",
            "fundamentals_report",
            "sector_report",
            "index_report",
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

