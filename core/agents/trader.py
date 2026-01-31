"""
交易员Agent基类

用于实现交易员Agent
v2.0 新增：基于配置的交易员Agent架构
"""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent
from .config import AgentMetadata, AgentCategory

logger = logging.getLogger(__name__)


class TraderAgent(BaseAgent):
    """
    交易员Agent基类
    
    工作模式：读取决策 → 生成交易分析计划
    
    特点：
    - 不调用工具
    - 依赖所有前序Agent的输出
    - 需要记忆系统（历史交易记录）
    - 输出格式：交易分析计划
    
    工作流程：
    1. 从state读取投资计划和所有分析报告
    2. 使用LLM生成交易分析
    3. 输出交易分析计划
    4. 输出到state["trading_plan"]
    
    子类需要实现：
    - _build_system_prompt(): 构建系统提示词
    - _build_user_prompt(): 构建用户提示词
    """
    
    # 输出字段名（子类定义）
    output_field: str = "trading_plan"
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm: Optional[Any] = None,
        memory: Optional[Any] = None,
        **kwargs
    ):
        """
        初始化交易员Agent
        
        Args:
            config: Agent配置
            llm: LLM实例
            memory: 记忆系统实例（用于历史交易记录）
            **kwargs: 其他参数
        """
        super().__init__(config=config, llm=llm, **kwargs)
        
        self.memory = memory
        
        logger.debug(f"TraderAgent '{self.agent_id}' 初始化完成")
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行交易分析
        
        Args:
            state: 工作流状态字典，包含：
                - ticker: 股票代码
                - analysis_date: 分析日期
                - investment_plan: 投资计划
                - market_report: 市场分析报告（可选）
                - news_report: 新闻分析报告（可选）
                - 其他报告...
                
        Returns:
            更新后的状态字典，包含交易分析计划
        """
        logger.info(f"开始执行交易员Agent: {self.agent_id}")
        
        try:
            # 1. 提取输入参数（兼容多种参数名）
            ticker = state.get("ticker") or state.get("company_of_interest")
            analysis_date = state.get("analysis_date") or state.get("trade_date") or state.get("end_date")
            investment_plan = state.get("investment_plan")

            if not ticker or not analysis_date:
                raise ValueError("Missing required parameters: ticker or analysis_date")
            
            if not investment_plan:
                raise ValueError("Missing investment_plan")
            
            # 2. 收集所有相关报告
            all_reports = self._collect_all_reports(state)
            
            # 3. 从记忆系统获取历史交易记录（如果有）
            historical_trades = self._get_historical_trades(ticker) if self.memory else None
            
            # 4. 构建提示词
            system_prompt = self._build_system_prompt(state=state)
            user_prompt = self._build_user_prompt(
                ticker, 
                analysis_date, 
                investment_plan, 
                all_reports,
                historical_trades,
                state
            )
            
            # 5. 调用LLM生成交易分析计划
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")
            # 🔍 调试日志：打印提示词长度
            logger.info(f"🔍 [TraderAgent] 系统提示词长度: {len(system_prompt)}")
            logger.info(f"🔍 [TraderAgent] 用户提示词长度: {len(user_prompt)}")
            logger.info(f"🔍 [TraderAgent] 用户提示词前500字符:\n{user_prompt[:500]}")

            if self._llm:
                response = self._llm.invoke(messages)

                # 🔍 调试日志：打印 LLM 响应
                logger.info(f"🔍 [TraderAgent] LLM 响应长度: {len(response.content)}")
                logger.info(f"🔍 [TraderAgent] LLM 响应内容:\n{response.content}")

                trading_plan = self._parse_response(response.content)

                # 🔍 调试日志：打印解析后的交易分析计划
                logger.info(f"🔍 [TraderAgent] 解析后的交易分析计划类型: {type(trading_plan)}")
                if isinstance(trading_plan, dict):
                    logger.info(f"🔍 [TraderAgent] 交易分析计划字段: {list(trading_plan.keys())}")
                    if 'content' in trading_plan:
                        logger.info(f"🔍 [TraderAgent] 交易分析计划内容长度: {len(str(trading_plan['content']))}")
            else:
                raise ValueError("LLM not initialized")

            # 6. 保存到记忆系统（如果有）
            if self.memory:
                self._save_to_memory(ticker, trading_plan)

            # 7. 输出到state（只返回新增的字段，避免并发冲突）
            logger.info(f"✅ [TraderAgent] {self.agent_id} 执行成功，输出字段: {self.output_field}")
            return {
                self.output_field: trading_plan
            }

        except Exception as e:
            logger.error(f"交易员Agent {self.agent_id} 执行失败: {e}", exc_info=True)
            # 返回错误状态（只返回新增的字段）
            return {
                self.output_field: {
                    "error": str(e),
                    "success": False
                }
            }
    
    def _collect_all_reports(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        收集所有相关报告
        
        Args:
            state: 工作流状态
            
        Returns:
            报告字典
        """
        report_keys = [
            "market_report",
            "news_report",
            "fundamentals_report",
            "social_report",
            "sector_report",
            "index_report",
            "bull_report",
            "bear_report",
            "risk_assessment"
        ]
        
        reports = {}
        for key in report_keys:
            if key in state:
                reports[key] = state[key]

        return reports

    def _get_historical_trades(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        从记忆系统获取历史交易记录

        Args:
            ticker: 股票代码

        Returns:
            历史交易记录列表
        """
        if not self.memory:
            return None

        try:
            # 这里需要根据实际的记忆系统实现
            # 暂时返回None
            return None
        except Exception as e:
            logger.warning(f"获取历史交易记录失败: {e}")
            return None

    def _save_to_memory(self, ticker: str, trading_plan: Dict[str, Any]) -> None:
        """
        保存到记忆系统

        Args:
            ticker: 股票代码
            trading_plan: 交易分析计划
        """
        if not self.memory:
            return

        try:
            # 这里需要根据实际的记忆系统实现
            pass
        except Exception as e:
            logger.warning(f"保存到记忆系统失败: {e}")

    @abstractmethod
    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（子类实现）

        Args:
            state: 工作流状态（可选，用于提取变量如 company_name, ticker 等）

        Returns:
            系统提示词
        """
        pass

    @abstractmethod
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
        构建用户提示词（子类实现）

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
        pass

    # 注意：_get_prompt_from_template() 方法已移至 BaseAgent 基类，所有 Agent 共享

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM响应（子类可覆盖）

        Args:
            response: LLM响应文本

        Returns:
            解析后的交易分析计划字典
        """
        # 🔍 调试日志
        logger.info(f"🔍 [TraderAgent._parse_response] 开始解析响应")
        logger.info(f"🔍 [TraderAgent._parse_response] 响应长度: {len(response)}")

        # 默认实现：直接返回文本
        result = {
            "content": response,
            "success": True
        }

        logger.info(f"🔍 [TraderAgent._parse_response] 解析完成，返回字典")
        return result

    @property
    def agent_id(self) -> str:
        """获取Agent ID"""
        if self.metadata:
            return self.metadata.id
        return self.__class__.__name__.lower()

