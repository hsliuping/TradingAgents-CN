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

    # 研究立场（bull/bear/risky/safe/neutral）
    stance: str = None

    # 辩论相关配置（子类可覆盖）
    debate_state_field: str = "investment_debate_state"  # 或 "risk_debate_state"
    history_field: str = None  # "bull_history", "bear_history" 等
    opponent_history_field: str = None  # 对方的 history 字段
    
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

            # 3. 检测辩论模式并获取上下文
            is_debate_mode = self._is_debate_mode(state)

            if is_debate_mode:
                # 辩论模式：获取辩论上下文
                historical_context = self._get_debate_context(state)
                logger.info(f"[辩论模式] {self.agent_id} 读取辩论历史")
            else:
                # 单次分析模式：从记忆系统获取历史上下文
                historical_context = self._get_memory_context(ticker, reports) if self.memory else None
                logger.info(f"[单次分析模式] {self.agent_id}")

            # 4. 构建提示词
            # 传递 state 参数（子类可以从 state 中提取变量如 company_name, ticker 等）
            system_prompt = self._build_system_prompt(self.stance, state)

            user_prompt = self._build_user_prompt(ticker, analysis_date, reports, historical_context, state)
            
            # 5. 调用LLM分析
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")
            
            if self._llm:
                response = self._llm.invoke(messages)
                report = self._parse_response(response.content)
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 保存到记忆系统（如果有）
            if self.memory and not is_debate_mode:
                # 只在单次分析模式下保存到记忆系统
                self._save_to_memory(ticker, report)

            # 7. 构建输出结果
            output_key = self.output_field or f"{self.researcher_type}_report"
            result = {output_key: report}

            # 8. 更新辩论状态（如果是辩论模式）
            if is_debate_mode:
                result = self._update_debate_state(state, report, result)
                logger.info(f"[辩论模式] {self.agent_id} 更新辩论状态")

            logger.info(f"研究员Agent {self.agent_id} 执行成功")
            return result

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
    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（子类实现）

        Args:
            stance: 研究立场（bull/bear）
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

    # 注意：_get_prompt_from_template() 方法已移至 BaseAgent 基类，所有 Agent 共享

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

    # ========== 辩论支持方法 ==========

    def _is_debate_mode(self, state: Dict[str, Any]) -> bool:
        """
        检测是否为辩论模式

        Args:
            state: 工作流状态

        Returns:
            True 如果是辩论模式
        """
        return self.debate_state_field in state and isinstance(state.get(self.debate_state_field), dict)

    def _get_debate_context(self, state: Dict[str, Any]) -> str:
        """
        获取辩论上下文

        Args:
            state: 工作流状态

        Returns:
            辩论上下文字符串（包含辩论历史和对方观点）
        """
        debate_state = state.get(self.debate_state_field, {})

        # 完整辩论历史
        history = debate_state.get("history", "")

        # 对方最新观点
        current_response = debate_state.get("current_response", "")

        # 对方历史（如果配置了 opponent_history_field）
        opponent_history = ""
        if self.opponent_history_field:
            opponent_history = debate_state.get(self.opponent_history_field, "")

        # 构建上下文
        context_parts = []

        if history:
            context_parts.append(f"【完整辩论历史】\n{history}")

        if current_response:
            context_parts.append(f"\n【对方最新观点】\n{current_response}")

        if opponent_history and opponent_history != history:
            context_parts.append(f"\n【对方历史观点】\n{opponent_history}")

        return "\n".join(context_parts) if context_parts else ""

    def _get_memory_context(self, ticker: str, reports: Dict[str, Any]) -> str:
        """
        从 Memory 系统获取历史经验

        Args:
            ticker: 股票代码
            reports: 当前报告

        Returns:
            历史经验字符串
        """
        if not self.memory:
            return ""

        try:
            # 构建当前情况描述
            curr_situation = "\n\n".join([str(v) for v in reports.values() if v])

            # 检索相似历史
            past_memories = self.memory.get_memories(curr_situation, n_matches=2)

            memory_str = ""
            for i, rec in enumerate(past_memories, 1):
                memory_str += rec.get("recommendation", "") + "\n\n"

            if memory_str:
                return f"\n【历史经验】\n{memory_str}"

        except Exception as e:
            logger.warning(f"获取 Memory 上下文失败: {e}")

        return ""

    def _update_debate_state(
        self,
        state: Dict[str, Any],
        response: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        更新辩论状态

        注意：count 由工作流层的辩论参与者包装器自动递增，Agent 层不需要管理

        Args:
            state: 工作流状态
            response: LLM 响应（报告内容）
            result: 当前结果字典

        Returns:
            更新后的结果字典
        """
        debate_state = state.get(self.debate_state_field, {})

        # 格式化发言
        speaker_label = self._get_speaker_label()

        # 提取报告内容
        if isinstance(response, dict):
            content = response.get("content", str(response))
        else:
            content = str(response)

        argument = f"{speaker_label}: {content}"

        # 构建新的辩论状态（不包含 count，由工作流层管理）
        new_debate_state = debate_state.copy()

        # 更新完整历史
        new_debate_state["history"] = debate_state.get("history", "") + "\n" + argument

        # 更新自己的历史
        if self.history_field:
            new_debate_state[self.history_field] = debate_state.get(self.history_field, "") + "\n" + argument

        # 更新最新发言
        new_debate_state["current_response"] = argument

        # 更新最新发言者（如果字段存在）
        if "latest_speaker" in debate_state:
            new_debate_state["latest_speaker"] = self.stance

        # 添加到结果
        result[self.debate_state_field] = new_debate_state

        return result

    def _get_speaker_label(self) -> str:
        """
        获取发言者标签

        Returns:
            发言者标签字符串
        """
        labels = {
            "bull": "Bull Analyst",
            "bear": "Bear Analyst",
            "risky": "Risky Analyst",
            "safe": "Safe Analyst",
            "neutral": "Neutral Analyst",
        }
        return labels.get(self.stance, "Analyst")

