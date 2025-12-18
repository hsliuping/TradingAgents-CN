"""
研究经理Agent v2.0

基于ManagerAgent基类实现的研究经理
综合看涨和看跌观点，做出最终投资决策
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
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError):
    logger.warning("无法导入get_agent_prompt，将使用默认提示词")
    get_agent_prompt = None


@register_agent
class ResearchManagerV2(ManagerAgent):
    """
    研究经理 v2.0
    
    功能：
    - 综合看涨和看跌观点
    - 主持辩论（可选）
    - 做出最终投资决策
    - 生成投资计划
    
    工作流程：
    1. 读取看涨报告和看跌报告
    2. 主持辩论（可选）
    3. 综合研判
    4. 生成投资计划（买入/持有/卖出）
    
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
        description="综合看涨和看跌观点，做出最终投资决策",
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
            AgentOutput(name="investment_advice", type="string", description="投资建议"),
        ],
        requires_tools=False,
        output_field="investment_advice",
        report_label="【投资建议 v2】",
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
        # 调用父类方法获取基本输出
        result = super().execute(state)

        # 提取决策内容
        decision_content = result.get(self.output_field, "")

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

        # 返回包含 investment_debate_state 的结果
        return {
            **result,
            "investment_debate_state": new_debate_state,
        }
    
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词
        
        Returns:
            系统提示词
        """
        # 尝试从模板系统获取
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="managers",
                    agent_name="research_manager",
                    variables={},
                    preference_id="neutral",
                    fallback_prompt=None
                )
                
                if prompt:
                    logger.debug(f"✅ 从模板系统获取研究经理系统提示词")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ 从模板系统获取提示词失败: {e}，使用默认提示词")
        
        # 默认提示词
        return """你是一位研究经理，需要综合看涨和看跌观点做出决策。

你的职责：
1. 综合分析看涨和看跌观点
2. 权衡双方的理由和证据
3. 做出客观、理性的投资决策
4. 给出明确的投资建议（买入/持有/卖出）

决策要求：
- 客观、理性、基于证据
- 权衡风险和收益
- 给出明确的建议
- 说明决策理由
- 使用中文输出

输出格式：
请以结构化的方式输出投资计划，包括：
- 投资建议（买入/持有/卖出）
- 置信度（0-1）
- 决策理由
- 风险提示
- 建议持仓比例
"""
    
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
        # 获取公司名称
        if StockUtils:
            market_info = StockUtils.get_market_info(ticker)
            company_name = self._get_company_name(ticker, market_info)
        else:
            company_name = ticker
        
        # 构建提示词
        prompt = f"""请综合分析 {company_name}（{ticker}）的投资机会：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}

"""
        
        # 添加看涨观点
        if "bull_report" in inputs:
            prompt += f"\n【看涨观点】\n{inputs['bull_report']}\n"
        
        # 添加看跌观点
        if "bear_report" in inputs:
            prompt += f"\n【看跌观点】\n{inputs['bear_report']}\n"
        
        # 添加辩论总结
        if debate_summary:
            prompt += f"\n【辩论总结】\n{debate_summary}\n"
        
        # 添加其他输入
        for key, value in inputs.items():
            if key not in ["bull_report", "bear_report"]:
                prompt += f"\n【{key}】\n{value}\n"
        
        prompt += "\n请给出最终的投资计划（买入/持有/卖出）和详细理由。"
        
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

