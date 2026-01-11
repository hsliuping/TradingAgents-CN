"""
分析师Agent基类

用于实现各种分析师Agent（市场分析师、新闻分析师、基本面分析师等）
v2.0 新增：基于配置的分析师Agent架构
"""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent
from .config import AgentMetadata, AgentCategory

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """
    分析师Agent基类
    
    工作模式：调用工具 → LLM分析 → 生成报告
    
    特点：
    - 需要调用工具获取数据
    - 使用LLM进行分析
    - 输出格式：{type}_report
    - 处理市场类型（A股/港股/美股）
    
    工作流程：
    1. 从state读取输入（ticker, date等）
    2. 调用工具获取数据
    3. 使用LLM分析数据
    4. 生成分析报告
    5. 输出到state["{type}_report"]
    
    子类需要实现：
    - _build_system_prompt(): 构建系统提示词
    - _build_user_prompt(): 构建用户提示词
    - _parse_response(): 解析LLM响应
    """
    
    # 分析师类型（子类定义）
    analyst_type: str = None
    
    # 输出字段名（子类定义）
    output_field: str = None
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm: Optional[Any] = None,
        tool_ids: Optional[List[str]] = None,
        **kwargs
    ):
        """
        初始化分析师Agent
        
        Args:
            config: Agent配置
            llm: LLM实例
            tool_ids: 工具ID列表
            **kwargs: 其他参数
        """
        super().__init__(config=config, llm=llm, tool_ids=tool_ids, **kwargs)
        
        logger.debug(f"AnalystAgent '{self.agent_id}' 初始化完成")
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行分析

        Args:
            state: 工作流状态字典，包含：
                - ticker: 股票代码
                - analysis_date: 分析日期
                - market_type: 市场类型（可选）
                - trade_info: 交易信息（交易复盘场景）

        Returns:
            更新后的状态字典，包含分析报告
        """
        logger.info(f"开始执行分析师Agent: {self.agent_id}")

        try:
            # 1. 提取输入参数（兼容多种参数名）
            ticker = state.get("ticker") or state.get("company_of_interest")

            # 🆕 支持交易复盘场景：从 trade_info 中提取 code
            if not ticker and "trade_info" in state:
                trade_info = state.get("trade_info", {})
                if isinstance(trade_info, dict):
                    ticker = trade_info.get("code")

            analysis_date = state.get("analysis_date") or state.get("trade_date") or state.get("end_date")

            # 🆕 支持交易复盘场景：使用当前日期作为分析日期
            if not analysis_date:
                from datetime import datetime
                analysis_date = datetime.now().strftime("%Y-%m-%d")

            market_type = state.get("market_type", "A股")

            if not ticker:
                raise ValueError("Missing required parameters: ticker")

            # 🔥 提取 AgentContext（用于调试模式）
            context = None
            if "context" in state:
                context = state["context"]
            elif "agent_context" in state:
                # 兼容旧格式：agent_context 是字典
                from tradingagents.agents.utils.agent_context import AgentContext
                ctx_dict = state["agent_context"]
                if isinstance(ctx_dict, dict):
                    context = AgentContext(**ctx_dict)
                else:
                    context = ctx_dict

            # 🔍 调试日志：检查是否为调试模式
            if context:
                is_debug = getattr(context, 'is_debug_mode', False)
                debug_template_id = getattr(context, 'debug_template_id', None)
                if is_debug and debug_template_id:
                    logger.info(
                        f"🔍 [{self.agent_id}] 调试模式已启用，模板ID: {debug_template_id}"
                    )
                else:
                    logger.debug(f"[{self.agent_id}] 正常模式，context 存在但非调试模式")
            else:
                logger.debug(f"[{self.agent_id}] 正常模式，无 context")

            # 2. 构建提示词
            system_prompt = self._build_system_prompt(market_type, context=context)
            user_prompt = self._build_user_prompt(ticker, analysis_date, {}, state)

            # 3. 调用LLM分析（使用工具调用）
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            if self._llm:
                # 使用 invoke_with_tools 支持工具调用
                if self._langchain_tools:
                    logger.info(f"[{self.agent_id}] 使用工具调用模式，工具数量: {len(self._langchain_tools)}")
                    logger.info(f"[{self.agent_id}] 工具列表: {[tool.name for tool in self._langchain_tools]}")

                    # 构建分析提示词，明确告诉 LLM 基于工具结果生成报告
                    analysis_prompt = f"""工具调用已完成，所有需要的数据都已获取。

现在请直接撰写详细的中文分析报告，不要再调用任何工具。

报告要求：
1. 基于上述工具返回的真实数据进行分析
2. 结构清晰，逻辑严谨
3. 结论明确，有理有据
4. 使用中文输出
5. 直接输出报告内容，不要返回工具调用

请立即开始撰写报告："""

                    report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                else:
                    # 没有工具，直接调用LLM
                    logger.warning(f"[{self.agent_id}] 没有配置工具，使用普通模式")
                    response = self._llm.invoke(messages)
                    # 直接返回字符串内容，与 invoke_with_tools 保持一致
                    report = response.content if hasattr(response, 'content') else str(response)
            else:
                raise ValueError("LLM not initialized")
            
            # 5. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.analyst_type}_report"

            logger.info(f"分析师Agent {self.agent_id} 执行成功")
            return {
                output_key: report
            }

        except Exception as e:
            logger.error(f"分析师Agent {self.agent_id} 执行失败: {e}", exc_info=True)
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.analyst_type}_report"
            return {
                output_key: {
                    "error": str(e),
                    "success": False
                }
            }
    
    def _fetch_data_with_tools(
        self, 
        ticker: str, 
        analysis_date: str, 
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用工具获取数据
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            state: 工作流状态
            
        Returns:
            工具返回的数据字典
        """
        tool_data = {}
        
        # 如果有LangChain工具，使用invoke_with_tools
        if self._langchain_tools and self._llm:
            # 构建工具调用提示
            tool_prompt = self._build_tool_prompt(ticker, analysis_date)
            result = self.invoke_with_tools(tool_prompt)
            tool_data = result
        
        return tool_data
    
    def _build_tool_prompt(self, ticker: str, analysis_date: str) -> str:
        """
        构建工具调用提示词
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            
        Returns:
            提示词字符串
        """
        return f"请获取 {ticker} 在 {analysis_date} 的相关数据"

    # 注意：_get_prompt_from_template() 方法已移至 BaseAgent 基类，所有 Agent 共享

    @abstractmethod
    def _build_system_prompt(self, market_type: str, context=None) -> str:
        """
        构建系统提示词（子类实现）

        Args:
            market_type: 市场类型
            context: AgentContext 对象（用于调试模式）

        Returns:
            系统提示词
        """
        pass
    
    @abstractmethod
    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（子类实现）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据
            state: 工作流状态

        Returns:
            用户提示词
        """
        pass

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM响应（子类可覆盖）

        Args:
            response: LLM响应文本

        Returns:
            解析后的报告字典
        """
        # 默认实现：直接返回文本
        return {
            "content": response,
            "success": True
        }

    @property
    def agent_id(self) -> str:
        """获取Agent ID"""
        if self.metadata:
            return self.metadata.id
        return self.__class__.__name__.lower()

