"""
管理者Agent基类

用于实现管理者Agent（研究整合员、风险评估师等）
v2.0 新增：基于配置的管理者Agent架构
"""

import logging
import json
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent
from .config import AgentMetadata, AgentCategory

logger = logging.getLogger(__name__)


def _stringify_manager_decision(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(value)
    return str(value)


class ManagerAgent(BaseAgent):
    """
    管理者Agent基类
    
    工作模式：主持辩论/审阅 → 综合多方意见 → 形成最终研究结论
    
    特点：
    - 不调用工具
    - 依赖多个Agent的输出
    - 需要辩论状态管理
    - 输出格式：决策/计划
    
    工作流程：
    1. 从state读取多个观点报告
    2. 主持辩论（可选）
    3. 使用LLM综合研判
    4. 生成最终研究结论
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
        memory: Optional[Any] = None,
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
        
        self.memory = memory
        self.debate_rounds = debate_rounds
        self.debate_history = []
        self._last_trace_id = None  # P1: 执行轨迹 ID（供子类回填校验结果）
        self._last_assertion_result = None  # P2: 最近一次断言执行结果（供子类参考）

        logger.debug(f"ManagerAgent '{self.agent_id}' 初始化完成")

    def delegate_to_agent(
        self,
        target_agent_id: str,
        state: Dict[str, Any],
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """管理者语义化包装：把专项任务委托给子 Agent 执行。"""
        logger.info(f"[ManagerAgent] {self.agent_id} 开始委托子 Agent: {target_agent_id}")
        result = self.invoke_agent(
            target_agent_id=target_agent_id,
            state=state,
            payload=payload,
            metadata={
                "manager_type": self.manager_type,
                **(metadata or {}),
            },
        )
        logger.info(f"[ManagerAgent] {self.agent_id} 委托子 Agent 完成: {target_agent_id}")
        return result
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行管理决策

        Args:
            state: 工作流状态字典，包含：
                - ticker: 股票代码
                - analysis_date: 分析日期
                - bull_report: 积极证据研究观察（可选）
                - bear_report: 谨慎证据研究观察（可选）
                - trade_info: 交易信息（交易复盘场景）
                - 其他输入...

        Returns:
            更新后的状态字典，包含决策结果
        """
        logger.info(f"开始执行管理者Agent: {self.agent_id}")

        # P1: 启动执行轨迹采集
        from core.agents.execution_trace_recorder import (
            start_execution_trace, is_trace_enabled
        )
        recorder = None
        if is_trace_enabled():
            try:
                recorder = start_execution_trace(self, state)
                self._last_trace_id = recorder.trace_id
            except Exception as e:
                logger.warning(f"⚠️ 启动轨迹采集失败（不影响 agent）: {e}")
                self._last_trace_id = None

        try:
            # 🔍 调试日志：排查 ticker 丢失问题
            logger.error(
                f"🔍 [{self.agent_id}] state keys: {list(state.keys())[:20]}, "
                f"ticker={state.get('ticker')}, company_of_interest={state.get('company_of_interest')}, "
                f"trade_info存在={('trade_info' in state)}, code={state.get('trade_info', {}).get('code') if isinstance(state.get('trade_info'), dict) else 'N/A'}"
            )

            # 1. 提取输入参数（统一使用基类方法，兼容多种字段名与场景兜底）
            ticker, analysis_date = self._extract_common_params(state)

            if not ticker:
                raise ValueError("Missing required parameters: ticker")
            
            # 2. 收集所需的输入
            inputs = self._collect_inputs(state)
            if recorder:
                recorder.record_inputs(inputs)

            if not inputs:
                raise ValueError("No inputs available for decision making")
            
            # 3. 如果启用辩论，进行辩论
            if self.enable_debate:
                debate_summary = self._conduct_debate(inputs, state)
            else:
                debate_summary = None

            memory_context = self._get_memory_context(ticker, inputs)
            if memory_context:
                debate_summary = self._merge_memory_context(debate_summary, memory_context)
            
            # 4. 构建提示词
            logger.info(f"🔍 [{self.agent_id}] 开始构建提示词...")
            # 🔑 传递 state 参数（子类可以从 state 中提取变量如 company_name, ticker 等）
            system_prompt = self._build_system_prompt(state=state)
            logger.info(f"📝 [{self.agent_id}] 系统提示词长度: {len(system_prompt)} 字符")
            logger.info(f"📝 [{self.agent_id}] 完整系统提示词:\n{'='*80}\n{system_prompt}\n{'='*80}")

            user_prompt = self._build_user_prompt(ticker, analysis_date, inputs, debate_summary, state)
            logger.info(f"📝 [{self.agent_id}] 用户提示词长度: {len(user_prompt)} 字符")
            logger.info(f"📝 [{self.agent_id}] 完整用户提示词:\n{'='*80}\n{user_prompt}\n{'='*80}")

            # 5. 调用LLM做决策
            system_prompt = self._apply_global_trading_advice_guard(system_prompt)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            if recorder:
                recorder.record_prompts(system_prompt, user_prompt)

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")

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
                import time as _time
                _t0 = _time.time()
                response = self._llm.invoke(messages)
                _llm_duration_ms = int((_time.time() - _t0) * 1000)

                # 🛡️ Q1: 空响应防线——推理模型偶发"瞬时异常"返回空 content（HTTP 成功但可见内容为 0）
                # 记录 finish_reason/思考token 后退避重试 1 次；仍为空则走失败路径，禁止把空内容包装成成功
                if not (getattr(response, "content", "") or "").strip():
                    _meta = getattr(response, "response_metadata", None) or {}
                    _usage = getattr(response, "usage_metadata", None) or {}
                    _reasoning = ((_usage.get("output_token_details") or {}).get("reasoning"))
                    logger.warning(
                        f"⚠️ [{self.agent_id}] LLM 返回空内容（finish_reason={_meta.get('finish_reason')}, "
                        f"reasoning_tokens={_reasoning}, 耗时={_llm_duration_ms}ms），5s 后自动重试 1 次"
                    )
                    _time.sleep(5)
                    _t0 = _time.time()
                    response = self._llm.invoke(messages)
                    _llm_duration_ms = int((_time.time() - _t0) * 1000)
                    if not (getattr(response, "content", "") or "").strip():
                        _meta = getattr(response, "response_metadata", None) or {}
                        raise ValueError(
                            f"LLM 返回空内容（重试 1 次后仍为空，finish_reason={_meta.get('finish_reason')}）"
                        )

                if recorder:
                    recorder.record_llm_response(response, llm_duration_ms=_llm_duration_ms)
                logger.info(f"✅ [{self.agent_id}] LLM 调用成功")
                logger.info(f"📝 [{self.agent_id}] LLM 响应长度: {len(response.content)} 字符")
                logger.info(f"📝 [{self.agent_id}] 完整 LLM 响应:\n{'='*80}\n{response.content}\n{'='*80}")

                decision = self._parse_response(response.content)
                if recorder:
                    recorder.record_parsed_output(decision)
                logger.info(f"✅ [{self.agent_id}] 响应解析成功")
                logger.info(f"📝 [{self.agent_id}] 解析结果类型: {type(decision)}")
                logger.info(f"📝 [{self.agent_id}] llm返回的解析结果: {decision}")

                # 如果是字典，记录关键字段
                if isinstance(decision, dict):
                    logger.info(f"📝 [{self.agent_id}] 解析结果字段: {list(decision.keys())}")
                    if "target_price" in decision or "price_analysis_range" in decision:
                        price_info = decision.get("target_price") or decision.get("price_analysis_range")
                        logger.info(f"💰 [{self.agent_id}] 价格分析区间: {price_info}")
                    if "action" in decision or "analysis_view" in decision or "market_view" in decision:
                        view = decision.get("action") or decision.get("analysis_view") or decision.get("market_view")
                        logger.info(f"🎯 [{self.agent_id}] 市场观点: {view}")
                    if "confidence" in decision:
                        logger.info(f"📊 [{self.agent_id}] 信心度: {decision.get('confidence')}")

                self._save_to_memory(ticker, decision)
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
            if recorder:
                recorder.record_error(e)
            logger.error(f"管理者Agent {self.agent_id} 执行失败: {e}", exc_info=True)
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.manager_type}_decision"
            return {
                output_key: {
                    "error": str(e),
                    "success": False
                }
            }
        finally:
            if recorder:
                recorder.finish()

    def _record_trace_validation(
        self,
        validation_status: str,
        validation_error: Optional[str] = None,
        validation_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """P1: 回填校验结果到执行轨迹（供子类调用，非阻塞）"""
        from core.agents.execution_trace_recorder import record_trace_validation
        record_trace_validation(
            trace_id=self._last_trace_id,
            validation_status=validation_status,
            validation_error=validation_error,
            validation_details=validation_details,
        )

    def _run_assertions(
        self,
        raw_text: str,
        parsed: Optional[Dict[str, Any]] = None,
    ):
        """P2: 执行召回的断言（非阻塞）。

        供子类在 _validate_* 完成后调用。返回 AssertionRunResult，
        由子类决定如何合并到 validation_status。

        全程 try/except，失败返回 AssertionRunResult(ran=False)，
        不影响 agent 主流程。
        """
        from app.core.config import settings
        try:
            from app.pro.models.agent_assertion import AssertionRunResult
        except ImportError:
            # 社区版无断言体系（app/models/agent_assertion 等已随 Pro 开源分离剔除）：
            # 返回"未运行"占位结果，调用方对 violations/has_error_violation/error_count
            # 的属性访问均安全（空列表 + False），断言功能整体静默跳过
            from types import SimpleNamespace
            return SimpleNamespace(
                ran=False, violations=[], has_error_violation=False, error_count=0
            )
        if not getattr(settings, "AGENT_ASSERTION_ENABLED", True):
            return AssertionRunResult(ran=False)
        try:
            from core.agents.assertion_executor import assertion_executor
            result = assertion_executor.run_assertions_sync(
                agent_id=self.agent_id,
                raw_text=raw_text,
                parsed=parsed,
            )
            self._last_assertion_result = result
            return result
        except Exception as e:
            logger.warning(f"⚠️ [{self.agent_id}] 断言执行失败（不影响 agent）: {e}")
            return AssertionRunResult(ran=False)
    
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

    def _build_memory_query(self, ticker: str, inputs: Dict[str, Any]) -> str:
        query_parts = [f"股票代码: {ticker}", f"管理者类型: {self.manager_type or self.agent_id}", "历史管理决策"]
        for key, value in list(inputs.items())[:4]:
            if not value:
                continue
            content = value.get("content") if isinstance(value, dict) else str(value)
            query_parts.append(f"{key}: {str(content)[:200]}")
        return "\n".join(query_parts)

    def _get_memory_context(self, ticker: str, inputs: Dict[str, Any]) -> str:
        if not self.memory:
            return ""

        try:
            query = self._build_memory_query(ticker, inputs)

            if not hasattr(self.memory, "search_memories"):
                logger.warning("记忆实例不支持 search_memories，已跳过管理者历史召回: %s", type(self.memory).__name__)
                return ""

            memories = self.memory.search_memories(
                query=query,
                n_results=3,
                filter_metadata={"ticker": ticker} if ticker else None,
            )
            formatted = []
            for item in memories or []:
                content = item.get("content", "")
                similarity = item.get("similarity", 0.0)
                if content:
                    formatted.append(f"[相似度: {similarity:.2f}] {content}")
            if formatted:
                return "【历史管理经验】\n" + "\n\n".join(formatted)
        except Exception as exc:
            logger.warning(f"获取管理者历史记忆失败: {exc}")

        return ""

    def _merge_memory_context(self, debate_summary: Optional[str], memory_context: str) -> str:
        if debate_summary:
            return f"{debate_summary}\n\n{memory_context}"
        return memory_context

    def _save_to_memory(self, ticker: str, decision: Any) -> None:
        if not self.memory:
            return

        try:
            content = _stringify_manager_decision(decision)

            if not hasattr(self.memory, "add_memory"):
                logger.warning("记忆实例不支持 add_memory，已跳过管理者记忆保存: %s", type(self.memory).__name__)
                return

            metadata = {
                "ticker": ticker,
                "agent_id": self.agent_id,
                "manager_type": self.manager_type,
                "output_field": self.output_field,
                "memory_kind": "manager_decision",
                "source": "manager_agent_runtime",
            }
            self.memory.add_memory(content=content, metadata=metadata)
        except Exception as exc:
            logger.warning(f"保存管理者记忆失败: {exc}")

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

