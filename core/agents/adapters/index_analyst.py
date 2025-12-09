"""
大盘/指数分析师智能体

分析大盘走势、市场环境和系统性风险
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage

from ..base import BaseAgent
from ..config import AgentConfig, BUILTIN_AGENTS
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class IndexAnalystAgent(BaseAgent):
    """
    大盘/指数分析师智能体
    
    职责：
    1. 分析主要指数走势（上证、深证、创业板等）
    2. 评估市场宽度（涨跌家数、量能等）
    3. 判断市场环境和风险水平
    4. 识别市场周期（牛市/熊市/震荡）
    """
    
    metadata = BUILTIN_AGENTS["index_analyst"]
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一位专业的大盘分析师，专门分析市场整体环境和系统性风险。

你的分析职责包括：

1️⃣ **指数走势分析**
   - 上证指数、深证成指、创业板指等主要指数走势
   - 均线系统判断（MA5/MA20/MA60）
   - 趋势方向判断

2️⃣ **市场宽度分析**
   - 涨跌家数比
   - 涨停跌停数量
   - 市场情绪判断

3️⃣ **市场环境评估**
   - 指数估值水平（PE/PB）
   - 市场波动率
   - 风险水平评估

4️⃣ **市场周期识别**
   - 牛市/熊市/震荡市判断
   - 年内位置分析
   - 操作建议

📊 输出要求：
- 市场趋势：上涨/下跌/震荡
- 风险等级：高/中/低
- 市场周期：牛市/熊市/震荡市
- 操作建议：积极/中性/防守
"""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._llm = None
        self._toolkit = None
    
    def set_dependencies(self, llm: Any, toolkit: Any) -> "IndexAnalystAgent":
        """
        设置依赖项
        
        Args:
            llm: LLM 实例
            toolkit: 工具包实例
            
        Returns:
            self (支持链式调用)
        """
        self._llm = llm
        self._toolkit = toolkit
        return self
    
    def initialize(self) -> None:
        """初始化智能体"""
        pass
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行大盘分析
        
        Args:
            state: 包含以下键的状态字典:
                - trade_date: 交易日期
                - messages: 消息历史
                
        Returns:
            更新后的状态，包含:
                - index_report: 大盘分析报告
                - messages: 更新的消息历史
        """
        trade_date = state.get("trade_date", "")
        
        logger.info(f"🌐 大盘分析师开始分析 @ {trade_date}")
        
        try:
            # 导入并调用大盘分析工具
            from core.tools.index_tools import analyze_index_sync
            
            # 获取综合大盘分析报告
            index_report = analyze_index_sync(trade_date)
            
            # 如果有 LLM，可以让 LLM 对报告进行总结
            if self._llm is not None:
                index_report = self._enhance_with_llm(index_report)
            
            logger.info(f"✅ 大盘分析完成")
            
            # 更新状态
            messages = state.get("messages", [])
            messages.append(HumanMessage(content=index_report, name="index_analyst"))
            
            return {
                **state,
                "index_report": index_report,
                "messages": messages,
            }
            
        except Exception as e:
            logger.error(f"❌ 大盘分析失败: {e}")
            error_report = f"大盘分析失败: {e}"
            
            messages = state.get("messages", [])
            messages.append(HumanMessage(content=error_report, name="index_analyst"))
            
            return {
                **state,
                "index_report": error_report,
                "messages": messages,
            }
    
    def _enhance_with_llm(self, data_report: str) -> str:
        """
        使用 LLM 增强分析报告
        """
        try:
            full_prompt = f"{self.SYSTEM_PROMPT}\n\n以下是大盘数据：\n\n{data_report}\n\n请基于以上数据，给出专业的大盘分析报告。"
            
            response = self._llm.invoke(full_prompt)
            
            if hasattr(response, 'content'):
                return response.content
            return str(response)
            
        except Exception as e:
            logger.warning(f"LLM 增强分析失败，返回原始报告: {e}")
            return data_report

