"""
大盘分析师 v2.0

基于AnalystAgent基类实现的大盘分析师
"""

import logging
from typing import Dict, Any, Optional

from core.agents.analyst import AnalystAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class IndexAnalystV2(AnalystAgent):
    """
    大盘分析师 v2.0
    
    功能：
    - 分析大盘指数走势
    - 评估市场整体环境
    - 分析市场风险和机会
    
    工作流程：
    1. 调用指数数据工具获取大盘数据
    2. 使用LLM分析大盘趋势
    3. 生成大盘分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("index_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="index_analyst_v2",
        name="大盘分析师 v2.0",
        description="分析大盘指数走势，评估市场整体环境",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_index_data", "get_market_breadth"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="index_report", type="string", description="大盘分析报告"),
        ],
        requires_tools=True,
        output_field="index_report",
        report_label="【大盘分析 v2】",
    )

    # 分析师类型
    analyst_type = "index"
    
    # 输出字段名
    output_field = "index_report"

    def _build_system_prompt(self, market_type: str, context=None) -> str:
        """
        构建系统提示词
        
        Args:
            market_type: 市场类型（A股/港股/美股）
            context: AgentContext 对象（用于调试模式）
            
                    
        Returns:
            系统提示词
        """
        # 从模板系统获取提示词
        if get_agent_prompt:
            try:
                template_variables = {
                    "market_name": market_type,
                    "ticker": "",
                    "company_name": "",
                    "current_date": "",
                    "currency_name": "人民币",
                    "currency_symbol": "¥",
                    "tool_names": ""
                }
                prompt = get_agent_prompt(
                    agent_type="analysts_v2",  # 🔧 修复：使用 v2.0 类型
                    agent_name="index_analyst_v2",  # 🔧 修复：使用 v2.0 名称
                    variables=template_variables,
                    preference_id="neutral",
                    fallback_prompt=None,
                    context=context  # ✅ 传递 context 以支持调试模式
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取大盘分析师 v2.0 提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        # 降级：使用默认提示词
        return f"""您是一位专业的大盘分析师。

您的职责是分析大盘指数走势，评估市场整体环境。

分析要点：
1. 分析主要指数的走势和趋势
2. 评估市场整体情绪和风险偏好
3. 分析市场宽度和参与度
4. 识别系统性风险和机会
5. 提供基于大盘的投资建议

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据
            state: 当前状态
            
        Returns:
            用户提示词
        """
        company_name = self._get_company_name(ticker, state)
        
        # 获取指数数据
        index_data = tool_data.get("get_index_data", "")
        market_breadth = tool_data.get("get_market_breadth", "")
        
        return f"""请基于以下大盘数据，对股票 {ticker}（{company_name}）所在市场进行详细的大盘分析：

=== 分析日期 ===
{analysis_date}

=== 指数数据 ===
{index_data}

=== 市场宽度数据 ===
{market_breadth}

请撰写详细的中文分析报告，包括：
1. 大盘走势分析
2. 市场情绪评估
3. 市场宽度分析
4. 系统性风险评估
5. 投资建议"""

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

