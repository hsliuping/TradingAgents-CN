"""
看跌研究员 v2.0

基于ResearcherAgent基类实现的看跌研究员
"""

import logging
from typing import Dict, Any, List

from core.agents.researcher import ResearcherAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent
from core.agents.utils.weight_calculator import calculate_report_weights, format_weighted_reports_prompt

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt, get_user_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None
    get_user_prompt = None

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class BearResearcherV2(ResearcherAgent):
    """
    看跌研究员 v2.0
    
    功能：
    - 从看跌角度综合分析多个报告
    - 找出所有风险因素和看跌理由
    - 生成看跌观点报告
    
    工作流程：
    1. 读取市场报告、新闻报告、基本面报告等
    2. 从看跌角度综合分析
    3. 生成看跌观点报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("bear_researcher_v2", llm)

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
        id="bear_researcher_v2",
        name="看跌研究员 v2.0",
        description="从看跌角度综合分析多个报告，找出风险因素和看跌理由",
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
            AgentOutput(name="bear_report", type="string", description="看跌观点报告"),
        ],
        requires_tools=False,
        output_field="bear_report",
        report_label="【看跌观点 v2】",
    )

    # 研究员类型
    researcher_type = "bear"
    
    # 立场
    stance = "bear"
    
    # 输出字段名
    output_field = "bear_report"

    def _build_system_prompt(self, stance: str) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 立场（bull/bear）
            
        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词
        template_variables = {"stance": stance}
        prompt = self._get_prompt_from_template(
            agent_type="researchers_v2",
            agent_name="bear_researcher_v2",
            variables=template_variables,
            context=None,
            fallback_prompt=None
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取看跌研究员提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：使用默认提示词
        return """您是一位专业的看跌研究员。

您的职责是从谨慎和风险控制的角度，综合分析各类报告，识别潜在风险。

分析要点：
1. 识别所有潜在的风险因素
2. 分析可能导致股价下跌的因素
3. 评估估值是否过高
4. 识别市场情绪是否过度乐观
5. 提供风险提示和谨慎建议

请使用中文，保持客观和专业。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（从模板系统获取）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            reports: 各类分析报告
            historical_context: 历史上下文
            state: 当前状态

        Returns:
            用户提示词
        """
        company_name = self._get_company_name(ticker, state)

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
                    agent_name="bear_researcher_v2",
                    variables=template_variables,
                    preference_id=preference_id,
                    fallback_prompt=None,
                    context=state
                )

                if prompt:
                    logger.info(f"✅ 从模板系统获取看跌研究员用户提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ 从模板系统获取用户提示词失败: {e}，使用降级提示词")

        # 降级：使用硬编码提示词
        prompt = f"""请从看跌角度综合分析以下报告，对股票 {ticker}（{company_name}）进行风险评估：

=== 分析日期 ===
{analysis_date}

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
            reports_text = ""
            for report_name, report_content in reports.items():
                if report_content:
                    reports_text += f"\n=== {report_name} ===\n{report_content}\n"
            prompt += f"=== 各类分析报告 ===\n{reports_text}"

        # 添加历史上下文
        if historical_context:
            prompt += f"\n=== 历史上下文 ===\n{historical_context}\n"

        prompt += """
请撰写详细的看跌观点报告，包括：
1. 主要风险因素识别
2. 可能导致下跌的催化剂
3. 估值风险评估
4. 市场情绪风险
5. 投资风险提示"""

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
            "sentiment_report",
            "fundamentals_report",
            "sector_report",
            "index_report"
        ]

    def _get_company_name(self, ticker: str, state: Dict[str, Any]) -> str:
        """获取公司名称"""
        # 优先从state获取
        if "company_name" in state:
            return state["company_name"]
        
        # 使用StockUtils获取
        if StockUtils:
            try:
                market_info = StockUtils.get_market_info(ticker)
                if market_info.get('is_china'):
                    from tradingagents.dataflows.interface import get_china_stock_info_unified
                    stock_info = get_china_stock_info_unified(ticker)
                    if "股票名称:" in stock_info:
                        return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            except Exception as e:
                logger.debug(f"获取公司名称失败: {e}")
        
        return f"股票{ticker}"

