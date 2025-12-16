"""
基本面分析师 v2.0 (持仓分析)

基于ResearcherAgent基类实现的基本面分析师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
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
class FundamentalAnalystV2(ResearcherAgent):
    """
    基本面分析师 v2.0 (持仓分析)
    
    功能：
    - 分析财务数据和估值水平
    - 评估行业地位和成长性
    - 判断基本面价值
    
    工作流程：
    1. 读取持仓信息和基本面报告
    2. 使用LLM分析基本面
    3. 生成基本面分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("pa_fundamental_v2", llm)

        result = agent.execute({
            "position_info": {...},
            "stock_analysis_report": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="pa_fundamental_v2",
        name="基本面分析师 v2.0",
        description="分析持仓股票的基本面，包括财务数据、估值水平、行业地位",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具
    )

    # 研究员类型
    researcher_type = "position_fundamental"
    
    # 立场（中性）
    stance = "neutral"
    
    # 输出字段名
    output_field = "fundamental_analysis"

    def _build_system_prompt(self, stance: str) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 立场（对于基本面分析师，始终为neutral）
            
        Returns:
            系统提示词
        """
        # 从模板系统获取提示词
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="position_analysis",
                    agent_name="pa_fundamental",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取基本面分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        # 降级：使用默认提示词
        return """您是一位专业的基本面分析师。

您的职责是分析持仓股票的基本面状态。

分析要点：
1. 财务状况 - 营收、利润、现金流分析
2. 估值水平 - PE/PB/PEG等估值指标
3. 行业地位 - 竞争优势和市场份额
4. 成长性 - 未来增长潜力
5. 基本面评分 - 1-10分的基本面评分

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        Args:
            ticker: 股票代码（从position_info中提取）
            analysis_date: 分析日期
            reports: 各类数据（position_info, stock_analysis_report等）
            historical_context: 历史上下文
            state: 当前状态
            
        Returns:
            用户提示词
        """
        position_info = state.get("position_info", {})
        stock_report = state.get("stock_analysis_report", {})
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        # 提取基本面报告
        reports_data = stock_report.get("reports", {})
        fundamentals_report = reports_data.get("fundamentals_report", "暂无基本面报告")[:2000]
        
        return f"""请分析以下持仓股票的基本面：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 所属行业: {position_info.get('industry', '未知')}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}

=== 基本面报告 ===
{fundamentals_report}

请撰写详细的基本面分析报告，包括：
1. 财务状况分析
2. 估值水平评估
3. 行业地位分析
4. 成长性判断
5. 基本面评分（1-10分）"""

    def _get_required_reports(self) -> List[str]:
        """
        获取需要的数据列表
        
        Returns:
            数据字段名列表
        """
        return [
            "position_info",
            "stock_analysis_report"
        ]

