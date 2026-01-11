"""
研究员Agent基类

用于实现研究员Agent（看涨研究员、看跌研究员等）
v2.0 新增：基于配置的研究员Agent架构
"""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent
from .config import AgentMetadata, AgentCategory

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """
    研究员Agent基类
    
    工作模式：读取多个报告 → LLM综合研判 → 生成观点
    
    特点：
    - 不调用工具（或很少调用）
    - 依赖其他Agent的输出
    - 需要记忆系统（memory）
    - 输出格式：观点报告
    
    工作流程：
    1. 从state读取多个分析报告
    2. 使用LLM综合分析
    3. 生成投资观点
    4. 输出到state["bull_report"/"bear_report"]
    
    子类需要实现：
    - _build_system_prompt(): 构建系统提示词
    - _build_user_prompt(): 构建用户提示词
    - _get_required_reports(): 获取需要的报告列表
    """
    
    # 研究员类型（子类定义）
    researcher_type: str = None
    
    # 输出字段名（子类定义）
    output_field: str = None
    
    # 研究立场（bull/bear）
    stance: str = None
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm: Optional[Any] = None,
        memory: Optional[Any] = None,
        **kwargs
    ):
        """
        初始化研究员Agent
        
        Args:
            config: Agent配置
            llm: LLM实例
            memory: 记忆系统实例
            **kwargs: 其他参数
        """
        super().__init__(config=config, llm=llm, **kwargs)
        
        self.memory = memory
        
        logger.debug(f"ResearcherAgent '{self.agent_id}' 初始化完成")
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行研究分析

        Args:
            state: 工作流状态字典，包含：
                - ticker: 股票代码
                - analysis_date: 分析日期
                - market_report: 市场分析报告（可选）
                - news_report: 新闻分析报告（可选）
                - fundamentals_report: 基本面分析报告（可选）
                - trade_info: 交易信息（交易复盘场景）
                - 其他分析报告...

        Returns:
            更新后的状态字典，包含研究观点
        """
        logger.info(f"开始执行研究员Agent: {self.agent_id}")

        try:
            # 1. 提取输入参数（兼容多种参数名）
            ticker = state.get("ticker") or state.get("company_of_interest")

            # 🆕 支持交易复盘场景：从 trade_info 中提取 code
            if not ticker and "trade_info" in state:
                trade_info = state.get("trade_info", {})
                if isinstance(trade_info, dict):
                    ticker = trade_info.get("code")
            
            # 🆕 支持持仓分析场景：从 position_info 中提取 code
            if not ticker and "position_info" in state:
                position_info = state.get("position_info", {})
                if isinstance(position_info, dict):
                    ticker = position_info.get("code")

            analysis_date = state.get("analysis_date") or state.get("trade_date") or state.get("end_date")

            # 🆕 支持交易复盘场景：使用当前日期作为分析日期
            if not analysis_date:
                from datetime import datetime
                analysis_date = datetime.now().strftime("%Y-%m-%d")

            if not ticker:
                raise ValueError("Missing required parameters: ticker")
            
            # 2. 收集所需的报告
            reports = self._collect_reports(state)
            
            if not reports:
                raise ValueError("No reports available for analysis")
            
            # 3. 从记忆系统获取历史上下文（如果有）
            historical_context = self._get_historical_context(ticker) if self.memory else None
            
            # 4. 构建提示词
            system_prompt = self._build_system_prompt(self.stance)
            user_prompt = self._build_user_prompt(ticker, analysis_date, reports, historical_context, state)
            
            # 5. 调用LLM分析
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            if self._llm:
                response = self._llm.invoke(messages)
                report = self._parse_response(response.content)
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 保存到记忆系统（如果有）
            if self.memory:
                self._save_to_memory(ticker, report)
            
            # 7. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.researcher_type}_report"

            logger.info(f"研究员Agent {self.agent_id} 执行成功")
            return {
                output_key: report
            }

        except Exception as e:
            logger.error(f"研究员Agent {self.agent_id} 执行失败: {e}", exc_info=True)
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.researcher_type}_report"
            return {
                output_key: {
                    "error": str(e),
                    "success": False
                }
            }
    
    def _collect_reports(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        收集所需的报告
        
        Args:
            state: 工作流状态
            
        Returns:
            报告字典
        """
        required_reports = self._get_required_reports()
        reports = {}
        
        for report_key in required_reports:
            if report_key in state:
                reports[report_key] = state[report_key]
        
        return reports
    
    def _get_historical_context(self, ticker: str) -> Optional[str]:
        """
        从记忆系统获取历史上下文

        Args:
            ticker: 股票代码

        Returns:
            历史上下文文本
        """
        if not self.memory:
            return None

        try:
            # 这里需要根据实际的记忆系统实现
            # 暂时返回None
            return None
        except Exception as e:
            logger.warning(f"获取历史上下文失败: {e}")
            return None

    def _save_to_memory(self, ticker: str, report: Dict[str, Any]) -> None:
        """
        保存到记忆系统

        Args:
            ticker: 股票代码
            report: 研究报告
        """
        if not self.memory:
            return

        try:
            # 这里需要根据实际的记忆系统实现
            pass
        except Exception as e:
            logger.warning(f"保存到记忆系统失败: {e}")

    @abstractmethod
    def _build_system_prompt(self, stance: str) -> str:
        """
        构建系统提示词（子类实现）

        Args:
            stance: 研究立场（bull/bear）

        Returns:
            系统提示词
        """
        pass

    @abstractmethod
    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, Any],
        historical_context: Optional[str],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（子类实现）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            reports: 收集的报告字典
            historical_context: 历史上下文
            state: 工作流状态

        Returns:
            用户提示词
        """
        pass

    @abstractmethod
    def _get_required_reports(self) -> List[str]:
        """
        获取需要的报告列表（子类实现）

        Returns:
            报告字段名列表
        """
        pass

    def _get_prompt_from_template(
        self,
        agent_type: str,
        agent_name: str,
        variables: Dict[str, Any],
        context: Any = None,
        fallback_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        从模板系统获取提示词（通用方法）

        Args:
            agent_type: Agent 类型（如 "researchers_v2"）
            agent_name: Agent 名称（如 "bull_researcher_v2"）
            variables: 模板变量字典
            context: AgentContext 对象（包含 user_id 和 preference_id）
            fallback_prompt: 降级提示词

        Returns:
            提示词文本，如果获取失败则返回 fallback_prompt
        """
        try:
            from tradingagents.utils.template_client import get_agent_prompt
        except (ImportError, KeyError) as e:
            logger.warning(f"无法导入模板系统: {e}")
            return fallback_prompt

        try:
            # 从 context 中提取 user_id 和 preference_id
            user_id = None
            preference_id = "neutral"

            if context:
                if hasattr(context, 'user_id'):
                    user_id = context.user_id
                if hasattr(context, 'preference_id'):
                    preference_id = context.preference_id or "neutral"

            # 调用模板系统
            prompt = get_agent_prompt(
                agent_type=agent_type,
                agent_name=agent_name,
                variables=variables,
                preference_id=preference_id,
                user_id=user_id,
                fallback_prompt=fallback_prompt,
                context=context
            )

            if prompt:
                logger.info(
                    f"✅ 从模板系统获取 {agent_name} 提示词 "
                    f"(user_id={user_id}, preference_id={preference_id}, 长度={len(prompt)})"
                )
                return prompt
            else:
                logger.warning(f"模板系统返回空提示词，使用降级提示词")
                return fallback_prompt

        except Exception as e:
            logger.warning(f"从模板系统获取提示词失败: {e}")
            return fallback_prompt

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
            "stance": self.stance,
            "success": True
        }

    @property
    def agent_id(self) -> str:
        """获取Agent ID"""
        if self.metadata:
            return self.metadata.id
        return self.__class__.__name__.lower()

