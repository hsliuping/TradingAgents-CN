"""
管理者Agent基类

用于实现管理者Agent（研究经理、风险经理等）
v2.0 新增：基于配置的管理者Agent架构
"""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent
from .config import AgentMetadata, AgentCategory

logger = logging.getLogger(__name__)


class ManagerAgent(BaseAgent):
    """
    管理者Agent基类
    
    工作模式：主持辩论/决策 → 综合多方意见 → 形成最终决策
    
    特点：
    - 不调用工具
    - 依赖多个Agent的输出
    - 需要辩论状态管理
    - 输出格式：决策/计划
    
    工作流程：
    1. 从state读取多个观点报告
    2. 主持辩论（可选）
    3. 使用LLM综合研判
    4. 生成最终决策
    5. 输出到state["investment_plan"/"risk_assessment"]
    
    子类需要实现：
    - _build_system_prompt(): 构建系统提示词
    - _build_user_prompt(): 构建用户提示词
    - _get_required_inputs(): 获取需要的输入列表
    """
    
    # 管理者类型（子类定义）
    manager_type: str = None
    
    # 输出字段名（子类定义）
    output_field: str = None
    
    # 是否需要辩论
    enable_debate: bool = False
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm: Optional[Any] = None,
        debate_rounds: int = 1,
        **kwargs
    ):
        """
        初始化管理者Agent
        
        Args:
            config: Agent配置
            llm: LLM实例
            debate_rounds: 辩论轮数
            **kwargs: 其他参数
        """
        super().__init__(config=config, llm=llm, **kwargs)
        
        self.debate_rounds = debate_rounds
        self.debate_history = []
        
        logger.debug(f"ManagerAgent '{self.agent_id}' 初始化完成")
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行管理决策

        Args:
            state: 工作流状态字典，包含：
                - ticker: 股票代码
                - analysis_date: 分析日期
                - bull_report: 看涨观点（可选）
                - bear_report: 看跌观点（可选）
                - trade_info: 交易信息（交易复盘场景）
                - 其他输入...

        Returns:
            更新后的状态字典，包含决策结果
        """
        logger.info(f"开始执行管理者Agent: {self.agent_id}")

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
            
            # 2. 收集所需的输入
            inputs = self._collect_inputs(state)
            
            if not inputs:
                raise ValueError("No inputs available for decision making")
            
            # 3. 如果启用辩论，进行辩论
            if self.enable_debate:
                debate_summary = self._conduct_debate(inputs, state)
            else:
                debate_summary = None
            
            # 4. 构建提示词
            logger.info(f"🔍 [{self.agent_id}] 开始构建提示词...")
            # 🔑 尝试传递 state 参数（v2.0 优化后的 Agent 支持从 state 中提取变量）
            try:
                system_prompt = self._build_system_prompt(state=state)
            except TypeError:
                # 降级：如果方法不接受 state 参数，使用旧方式调用
                system_prompt = self._build_system_prompt()
            logger.info(f"📝 [{self.agent_id}] 系统提示词长度: {len(system_prompt)} 字符")
            logger.info(f"📝 [{self.agent_id}] 完整系统提示词:\n{'='*80}\n{system_prompt}\n{'='*80}")

            user_prompt = self._build_user_prompt(ticker, analysis_date, inputs, debate_summary, state)
            logger.info(f"📝 [{self.agent_id}] 用户提示词长度: {len(user_prompt)} 字符")
            logger.info(f"📝 [{self.agent_id}] 完整用户提示词:\n{'='*80}\n{user_prompt}\n{'='*80}")

            # 5. 调用LLM做决策
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            # 打印最终发送给LLM的完整内容（包括所有字段：system_prompt, tool_guidance, analysis_requirements, output_format, constraints, user_prompt）
            final_system_content = system_prompt  # system_prompt已经包含了所有系统相关部分（通过get_agent_prompt组合）
            final_user_content = user_prompt
            final_messages_text = f"""【SystemMessage - 系统提示词（包含system_prompt + tool_guidance + analysis_requirements + output_format + constraints）】
{final_system_content}

【HumanMessage - 用户提示词】
{final_user_content}"""
            
            total_length = len(final_system_content) + len(final_user_content)
            logger.info(f"📝 [{self.agent_id}] 最终发送给LLM的完整内容长度: {total_length} 字符")
            logger.info(f"📝 [{self.agent_id}] SystemMessage长度: {len(final_system_content)} 字符")
            logger.info(f"📝 [{self.agent_id}] HumanMessage长度: {len(final_user_content)} 字符")
            logger.info(f"📝 [{self.agent_id}] 最终发送给LLM的完整内容:\n{'='*80}\n{final_messages_text}\n{'='*80}")

            logger.info(f"🤖 [{self.agent_id}] 开始调用 LLM...")
            logger.info(f"🤖 [{self.agent_id}] LLM 类型: {type(self._llm).__name__}")

            if self._llm:
                response = self._llm.invoke(messages)
                logger.info(f"✅ [{self.agent_id}] LLM 调用成功")
                logger.info(f"📝 [{self.agent_id}] LLM 响应长度: {len(response.content)} 字符")
                logger.info(f"📝 [{self.agent_id}] 完整 LLM 响应:\n{'='*80}\n{response.content}\n{'='*80}")

                decision = self._parse_response(response.content)
                logger.info(f"✅ [{self.agent_id}] 响应解析成功")
                logger.info(f"📝 [{self.agent_id}] 解析结果类型: {type(decision)}")
                logger.info(f"📝 [{self.agent_id}] llm返回的解析结果: {decision}")

                # 如果是字典，记录关键字段
                if isinstance(decision, dict):
                    logger.info(f"📝 [{self.agent_id}] 解析结果字段: {list(decision.keys())}")
                    if "target_price" in decision:
                        logger.info(f"💰 [{self.agent_id}] 目标价格: {decision.get('target_price')}")
                    if "action" in decision:
                        logger.info(f"🎯 [{self.agent_id}] 投资建议: {decision.get('action')}")
                    if "confidence" in decision:
                        logger.info(f"📊 [{self.agent_id}] 信心度: {decision.get('confidence')}")
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.manager_type}_decision"
            result = {
                output_key: decision
            }

            # 7. 保存辩论历史（如果有）
            if self.enable_debate and self.debate_history:
                result[f"{self.agent_id}_debate_history"] = self.debate_history

            logger.info(f"管理者Agent {self.agent_id} 执行成功")
            return result

        except Exception as e:
            logger.error(f"管理者Agent {self.agent_id} 执行失败: {e}", exc_info=True)
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.manager_type}_decision"
            return {
                output_key: {
                    "error": str(e),
                    "success": False
                }
            }
    
    def _collect_inputs(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        收集所需的输入

        Args:
            state: 工作流状态

        Returns:
            输入字典
        """
        required_inputs = self._get_required_inputs()
        logger.info(f"🔍 [{self.agent_id}] 需要的输入字段: {required_inputs}")
        logger.info(f"🔍 [{self.agent_id}] State 中的所有字段: {list(state.keys())}")

        inputs = {}

        for input_key in required_inputs:
            if input_key in state:
                value = state[input_key]
                inputs[input_key] = value
                logger.info(f"✅ [{self.agent_id}] 找到输入: {input_key}, 类型: {type(value)}, 长度: {len(str(value))} 字符")
            else:
                logger.warning(f"⚠️ [{self.agent_id}] 缺少输入: {input_key}")

        logger.info(f"📝 [{self.agent_id}] 收集到 {len(inputs)} 个输入")

        return inputs
    
    def _conduct_debate(self, inputs: Dict[str, Any], state: Dict[str, Any]) -> str:
        """
        主持辩论
        
        Args:
            inputs: 输入字典
            state: 工作流状态
            
        Returns:
            辩论总结
        """
        self.debate_history = []
        
        # 简化实现：直接总结各方观点
        # 实际实现可以进行多轮辩论
        debate_summary = "辩论总结：\n"
        
        for key, value in inputs.items():
            if isinstance(value, dict) and "content" in value:
                debate_summary += f"\n{key}: {value['content'][:200]}...\n"
        
        self.debate_history.append({
            "round": 1,
            "summary": debate_summary
        })

        return debate_summary

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词（子类实现）

        Returns:
            系统提示词
        """
        pass

    @abstractmethod
    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        inputs: Dict[str, Any],
        debate_summary: Optional[str],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（子类实现）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            inputs: 收集的输入字典
            debate_summary: 辩论总结
            state: 工作流状态

        Returns:
            用户提示词
        """
        pass

    @abstractmethod
    def _get_required_inputs(self) -> List[str]:
        """
        获取需要的输入列表（子类实现）

        Returns:
            输入字段名列表
        """
        pass

    # 注意：_get_prompt_from_template() 方法已移至 BaseAgent 基类，所有 Agent 共享

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM响应（子类可覆盖）

        Args:
            response: LLM响应文本

        Returns:
            解析后的决策字典
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

