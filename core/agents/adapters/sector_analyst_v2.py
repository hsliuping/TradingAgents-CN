"""
板块分析师 v2.0

基于AnalystAgent基类实现的板块分析师
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
class SectorAnalystV2(AnalystAgent):
    """
    板块分析师 v2.0
    
    功能：
    - 分析行业趋势和板块轮动
    - 评估同业对比和竞争格局
    - 分析资金流向
    
    工作流程：
    1. 调用板块数据工具获取行业数据
    2. 使用LLM分析板块趋势
    3. 生成板块分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("sector_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="sector_analyst_v2",
        name="板块分析师 v2.0",
        description="分析行业趋势、板块轮动和同业对比",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_sector_data", "get_fund_flow_data"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="sector_report", type="string", description="板块分析报告"),
        ],
        requires_tools=True,
        output_field="sector_report",
        report_label="【板块分析 v2】",
    )

    # 分析师类型
    analyst_type = "sector"
    
    # 输出字段名
    output_field = "sector_report"

    def _build_system_prompt(self, market_type: str) -> str:
        """
        构建系统提示词
        
        Args:
            market_type: 市场类型（A股/港股/美股）
            
        Returns:
            系统提示词
        """
        # 从模板系统获取提示词
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="analysts",
                    agent_name="sector_analyst",
                    variables={"market_name": market_type},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取板块分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        # 降级：使用默认提示词
        return f"""您是一位专业的板块分析师。

您的职责是分析行业趋势、板块轮动和同业对比。

分析要点：
1. 分析所属行业的整体趋势
2. 评估板块轮动和资金流向
3. 对比同行业公司的表现
4. 识别行业机会和风险
5. 提供基于板块的投资建议

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
        
        # 获取板块数据
        sector_data = tool_data.get("get_sector_data", "")
        fund_flow_data = tool_data.get("get_fund_flow_data", "")
        
        return f"""请基于以下板块数据，对股票 {ticker}（{company_name}）进行详细的板块分析：

=== 分析日期 ===
{analysis_date}

=== 板块数据 ===
{sector_data}

=== 资金流向数据 ===
{fund_flow_data}

请撰写详细的中文分析报告，包括：
1. 行业趋势分析
2. 板块轮动评估
3. 同业对比分析
4. 资金流向分析
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

