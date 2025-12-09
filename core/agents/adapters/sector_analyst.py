"""
板块分析师智能体

分析行业趋势、板块轮动和同业对比
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage

from ..base import BaseAgent
from ..config import AgentConfig, BUILTIN_AGENTS
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class SectorAnalystAgent(BaseAgent):
    """
    板块分析师智能体
    
    职责：
    1. 分析目标股票所属行业的整体表现
    2. 识别板块轮动趋势和资金流向
    3. 进行同业竞争对手对比分析
    """
    
    metadata = BUILTIN_AGENTS["sector_analyst"]
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一位专业的板块分析师，专注于行业研究和板块轮动分析。

你的任务是分析目标股票 {ticker} 的板块和行业情况。

🔴 分析要求：

1️⃣ **板块表现分析**
   - 目标股票所属哪些板块
   - 各板块近期涨跌幅表现
   - 板块相对大盘的强弱

2️⃣ **板块轮动趋势**
   - 当前市场热点板块
   - 资金流入/流出方向
   - 板块轮动周期判断

3️⃣ **同业对比分析**
   - 目标股票在行业中的地位（市值排名）
   - 估值对比（PE/PB vs 行业中位数）
   - 行业龙头识别

📊 输出要求：
- 板块热度评估：热门/一般/冷门
- 轮动方向：资金流入/流出/稳定
- 个股位置：龙头/第二梯队/跟风
- 投资建议：结合板块趋势给出建议
"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
        self._toolkit = None
    
    def set_dependencies(self, llm: Any, toolkit: Any) -> "SectorAnalystAgent":
        """
        设置依赖项
        
        Args:
            llm: LLM 实例 (用于 LangGraph 模式)
            toolkit: 工具包实例 (用于 LangGraph 模式)
            
        Returns:
            self (支持链式调用)
        """
        self._llm = llm
        self._toolkit = toolkit
        return self
    
    def initialize(self) -> None:
        """初始化智能体"""
        pass  # 工具函数直接导入，无需初始化
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行板块分析
        
        Args:
            state: 包含以下键的状态字典:
                - company_of_interest: 股票代码
                - trade_date: 交易日期
                - messages: 消息历史
                
        Returns:
            更新后的状态，包含:
                - sector_report: 板块分析报告
                - messages: 更新的消息历史
        """
        ticker = state.get("company_of_interest", "")
        trade_date = state.get("trade_date", "")
        
        logger.info(f"🏭 板块分析师开始分析: {ticker} @ {trade_date}")
        
        try:
            # 导入并调用板块分析工具
            from core.tools.sector_tools import analyze_sector_sync
            
            # 获取综合板块分析报告
            sector_report = analyze_sector_sync(ticker, trade_date)
            
            # 如果有 LLM，可以让 LLM 对报告进行总结
            if self._llm is not None:
                sector_report = self._enhance_with_llm(ticker, sector_report)
            
            logger.info(f"✅ 板块分析完成: {ticker}")
            
            # 更新状态
            messages = state.get("messages", [])
            messages.append(HumanMessage(content=sector_report, name="sector_analyst"))
            
            return {
                **state,
                "sector_report": sector_report,
                "messages": messages,
            }
            
        except Exception as e:
            logger.error(f"❌ 板块分析失败: {e}")
            error_report = f"板块分析失败: {e}"
            
            messages = state.get("messages", [])
            messages.append(HumanMessage(content=error_report, name="sector_analyst"))
            
            return {
                **state,
                "sector_report": error_report,
                "messages": messages,
            }
    
    def _enhance_with_llm(self, ticker: str, data_report: str) -> str:
        """
        使用 LLM 增强分析报告
        
        Args:
            ticker: 股票代码
            data_report: 原始数据报告
            
        Returns:
            增强后的分析报告
        """
        try:
            prompt = self.SYSTEM_PROMPT.format(ticker=ticker)
            full_prompt = f"{prompt}\n\n以下是板块数据：\n\n{data_report}\n\n请基于以上数据，给出专业的板块分析报告。"
            
            # 调用 LLM
            response = self._llm.invoke(full_prompt)
            
            if hasattr(response, 'content'):
                return response.content
            return str(response)
            
        except Exception as e:
            logger.warning(f"LLM 增强分析失败，返回原始报告: {e}")
            return data_report

