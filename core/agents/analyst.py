from core.agents.base import BaseAgent, GENERIC_REPORT_FALLBACK
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

    @staticmethod
    def _build_post_tool_analysis_prompt() -> str:
        return """工具调用已完成，所有需要的数据都已获取。

现在请直接撰写详细的中文分析报告，不要再调用任何工具。

报告要求：
1. **严格基于工具返回的真实数据进行分析**：所有结论必须来自工具返回的数据，禁止编造、假设或推测
2. **数据缺失处理**：如果工具返回的数据中没有某个维度的数据，不要分析该维度，也不要单独列出“未获取的数据维度”“数据缺口说明”或缺失维度清单。只有当工具明确返回异常、缺失、口径冲突等提示时，才可在对应段落内用一句话简要说明其对结论的限制。
3. **多口径数据处理**：如果工具返回“汇总口径/明细口径”“口径差异摘要”或其他多套统计口径，正文必须同时保留两套数值，并明确写出“存在口径差异”；禁止压缩成单一计数，也不要写成“其中 … 家”这类包含关系。
4. 结构清晰，逻辑严谨
5. 结论明确，有理有据
6. 使用中文输出
7. 直接输出报告内容，不要返回工具调用

**重要提醒**：仔细检查工具返回的数据，只分析数据中实际存在的维度。不要额外补写 KOL 观点、散户情绪、机构持仓、行业资金流向等未提供维度，也不要生成“本报告未获取以下维度数据，不作相关分析”之类章节。

请立即开始撰写报告："""
    
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
        self._current_state = state

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
                logger.warning(f"⚠️ [{self.agent_id}] 启动轨迹采集失败（不影响 agent）: {e}")
                self._last_trace_id = None

        try:
            # 1. 提取输入参数（统一使用基类方法，兼容多种字段名与场景兜底）
            ticker, analysis_date = self._extract_common_params(state)

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
            # 🔑 传递 state 给 _build_system_prompt，以便从 state 中提取变量完善模板
            system_prompt = self._build_system_prompt(market_type, context=context, state=state)
            user_prompt = self._build_user_prompt(ticker, analysis_date, {}, state)

            # 3. 调用LLM分析（使用工具调用）
            system_prompt = self._apply_global_trading_advice_guard(system_prompt)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # 🔥 详细日志：打印系统提示词的完整内容和长度
            logger.info(f"系统提示词 (长度: {len(system_prompt)}): {system_prompt}")
            logger.info(f"用户提示词 (长度: {len(user_prompt)}): {user_prompt}")

            # P1: 记录 Prompt
            if recorder:
                try:
                    recorder.record_inputs({"ticker": ticker, "analysis_date": analysis_date, "market_type": market_type})
                    recorder.record_prompts(system_prompt, user_prompt)
                except Exception as e:
                    logger.debug(f"[{self.agent_id}] 记录 Prompt 失败（不影响 agent）: {e}")
            
            # 🔥 验证：检查发送给LLM的SystemMessage内容是否与system_prompt一致
            actual_system_content = messages[0].content if messages and hasattr(messages[0], 'content') else None
            if actual_system_content != system_prompt:
                logger.error(f"❌ 警告：SystemMessage内容与system_prompt不一致！")
                logger.error(f"   system_prompt长度: {len(system_prompt)}")
                logger.error(f"   SystemMessage.content长度: {len(actual_system_content) if actual_system_content else 0}")
                logger.error(f"   system_prompt前500字符: {system_prompt[:500]}")
                logger.error(f"   SystemMessage.content前500字符: {actual_system_content[:500] if actual_system_content else '(None)'}")
            else:
                logger.info(f"✅ 验证通过：SystemMessage内容与system_prompt一致 (长度: {len(system_prompt)})")

            if self._llm:
                # 使用 invoke_with_tools 支持工具调用
                if self._langchain_tools:
                    logger.info(f"[{self.agent_id}] 使用工具调用模式，工具数量: {len(self._langchain_tools)}")
                    logger.info(f"[{self.agent_id}] 工具列表: {[tool.name for tool in self._langchain_tools]}")

                    # 构建分析提示词，明确告诉 LLM 基于工具结果生成报告
                    analysis_prompt = self._build_post_tool_analysis_prompt()

                    report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                    # 🔑 LLM 响应已由 invoke_with_tools 内部的 _record_llm_response_to_trace 自动记录
                else:
                    # 没有工具，直接调用LLM
                    logger.warning(f"[{self.agent_id}] 没有配置工具，使用普通模式")
                    import time as _time_llm
                    _llm_start = _time_llm.time()
                    response = self._llm.invoke(messages)
                    _llm_duration_ms = int((_time_llm.time() - _llm_start) * 1000)
                    # 直接返回字符串内容，与 invoke_with_tools 保持一致
                    report = response.content if hasattr(response, 'content') else str(response)

                    # P1: 记录 LLM 响应
                    if recorder:
                        try:
                            recorder.record_llm_response(response, llm_duration_ms=_llm_duration_ms)
                        except Exception as e:
                            logger.debug(f"[{self.agent_id}] 记录 LLM 响应失败（不影响 agent）: {e}")
            else:
                raise ValueError("LLM not initialized")

            # P1: 记录解析后的输出
            if recorder:
                try:
                    recorder.record_parsed_output({"report": report[:500] if isinstance(report, str) else str(report)[:500]})
                except Exception as e:
                    logger.debug(f"[{self.agent_id}] 记录解析输出失败（不影响 agent）: {e}")

            # 🆕 v3.5.0 质量门禁：检查报告完整性，失败时重试1次，仍失败标记 low_quality
            quality_flag = self._check_and_retry_quality(
                report=report,
                messages=messages,
                analysis_prompt=analysis_prompt if self._langchain_tools else None,
                ticker=ticker,
            )
            # 重试成功时，用重试后的报告替换原报告
            if quality_flag is None and hasattr(self, "_retry_report") and self._retry_report:
                report = self._retry_report
                self._retry_report = None  # 清理，避免影响下次调用

            # 5. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.analyst_type}_report"

            logger.info(f"分析师Agent {self.agent_id} 执行成功")
            result = {output_key: report}

            # 质量门禁标记（写入 state.quality_flags，下游可知哪些报告质量差）
            if quality_flag:
                result["quality_flags"] = [quality_flag]

            # 🆕 v3.6.0 项5 闭环：采集质量指标写入 MongoDB（供仪表盘查询）
            # 不阻塞主流程，失败时静默降级
            try:
                from app.services.quality_metrics_service import QualityMetricsService
                from app.core.database import get_mongo_db_sync
                metrics_db = get_mongo_db_sync()
                if metrics_db is not None:
                    user_id = state.get("user_id") or state.get("userId") or "default_user"
                    # 检测是否命中兜底文案
                    hit_fallback = bool(quality_flag and quality_flag.get("severity") == "critical")
                    fallback_pattern = quality_flag.get("reason", "") if quality_flag else ""
                    # v3.6.0 fix：仅 critical 级别标记为低质量，warning 级别不标记
                    is_low_quality = bool(quality_flag and quality_flag.get("severity") == "critical")
                    retry_count = 1 if (quality_flag and quality_flag.get("retried")) else 0
                    QualityMetricsService(db=metrics_db).record_analysis_metrics_sync(
                        user_id=user_id,
                        ticker=ticker,
                        agent_id=self.agent_id,
                        agent_type=self.analyst_type,
                        report_content=report[:500] if isinstance(report, str) else "",
                        report_length=len(report) if isinstance(report, str) else 0,
                        is_low_quality=is_low_quality,
                        quality_flags=[quality_flag] if quality_flag else [],
                        hit_fallback=hit_fallback,
                        fallback_pattern=fallback_pattern,
                        retry_count=retry_count,
                        analysis_date=analysis_date,
                        workflow_id=state.get("workflow_id", ""),
                    )
            except Exception as metrics_exc:
                logger.debug(f"[Analyst] 质量指标采集失败（不阻塞）: {metrics_exc}")

            # 🆕 附带工具调用摘要，供下游 Agent 引用
            tool_summary = self._format_tool_call_summary()
            if tool_summary:
                result["tool_call_summaries"] = {self.analyst_type: tool_summary}
                logger.info(f"📊 [{self.agent_id}] 工具调用摘要已生成（{len(self._tool_call_summaries_collected)} 次调用）")

            return result

        except Exception as e:
            logger.error(f"分析师Agent {self.agent_id} 执行失败: {e}", exc_info=True)
            # P1: 记录异常
            if recorder:
                try:
                    recorder.record_error(e)
                except Exception:
                    pass
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.analyst_type}_report"
            return {
                output_key: {
                    "error": GENERIC_REPORT_FALLBACK,
                    "success": False
                }
            }
        finally:
            self._current_state = None
            # P1: 完成轨迹采集并写入 MongoDB（非阻塞）
            if recorder:
                try:
                    recorder.finish()
                except Exception:
                    pass

    def _check_and_retry_quality(
        self,
        report: str,
        messages: list,
        analysis_prompt: Optional[str],
        ticker: str,
    ) -> Optional[Dict[str, Any]]:
        """v3.5.0 质量门禁：检查报告完整性，失败时重试1次，仍失败返回 quality_flag。

        分层降级策略：
        - critical 级别失败（空报告/兜底文案）→ 重试1次
        - warning 级别失败（缺结论关键词）→ 不重试，只标记
        - 重试后仍失败 → 返回 quality_flag 字典写入 state.quality_flags

        Args:
            report: 原始报告内容
            messages: 原始消息列表（重试时复用）
            analysis_prompt: 工具后分析提示词（重试时复用，无工具模式为 None）
            ticker: 股票代码（用于日志和告警元数据）

        Returns:
            None 表示质量通过；Dict 表示质量标记（应写入 state.quality_flags）
        """
        from core.agents.quality_gate import validate_analyst_report

        report_str = report if isinstance(report, str) else str(report)
        qc_result = validate_analyst_report(
            content=report_str,
            agent_id=self.agent_id,
            ticker=ticker,
        )

        if qc_result.is_valid:
            logger.info(f"[QualityGate] {self.agent_id} 报告质量通过")
            return None

        # warning 级别：不重试，只标记
        if not qc_result.should_retry:
            logger.warning(
                f"[QualityGate] {self.agent_id} 报告质量 warning：{qc_result.reason}"
            )
            return {
                "agent_id": self.agent_id,
                "analyst_type": self.analyst_type,
                "ticker": ticker,
                "reason": qc_result.reason,
                "severity": qc_result.severity,
                "retried": False,
            }

        # critical 级别：重试1次
        logger.warning(
            f"[QualityGate] {self.agent_id} 报告质量 critical：{qc_result.reason}，重试1次"
        )
        try:
            retry_messages = list(messages) + [
                HumanMessage(content=(
                    f"注意：你刚才生成的报告存在问题（{qc_result.reason}）。"
                    "请重新生成一份完整的分析报告，必须包含明确结论（如建议/判断/风险等）。"
                    "直接输出报告内容，不要再调用任何工具。"
                ))
            ]
            if self._langchain_tools and analysis_prompt:
                retry_report = self.invoke_with_tools(retry_messages, analysis_prompt=analysis_prompt)
            elif self._llm:
                retry_response = self._llm.invoke(retry_messages)
                retry_report = retry_response.content if hasattr(retry_response, 'content') else str(retry_response)
            else:
                retry_report = report  # 无法重试，保持原报告

            # 二次校验
            retry_str = retry_report if isinstance(retry_report, str) else str(retry_report)
            qc_result2 = validate_analyst_report(
                content=retry_str,
                agent_id=self.agent_id,
                ticker=ticker,
            )

            if qc_result2.is_valid:
                logger.info(f"[QualityGate] {self.agent_id} 重试后质量通过")
                # 用重试后的报告替换原报告（通过实例属性传递回 execute）
                # 注意：这里直接修改不了 execute 的局部变量 report，
                # 所以用 _retry_report 属性传递
                self._retry_report = retry_report
                return None
            else:
                logger.error(
                    f"[QualityGate] {self.agent_id} 重试后仍不通过：{qc_result2.reason}，标记 low_quality"
                )
                return {
                    "agent_id": self.agent_id,
                    "analyst_type": self.analyst_type,
                    "ticker": ticker,
                    "reason": qc_result2.reason,
                    "severity": qc_result2.severity,
                    "retried": True,
                }
        except Exception as retry_err:
            logger.error(f"[QualityGate] {self.agent_id} 重试异常：{retry_err}", exc_info=True)
            return {
                "agent_id": self.agent_id,
                "analyst_type": self.analyst_type,
                "ticker": ticker,
                "reason": f"重试异常: {retry_err}",
                "severity": "critical",
                "retried": True,
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
    def _build_system_prompt(self, market_type: str, context=None, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（子类实现）

        Args:
            market_type: 市场类型
            context: AgentContext 对象（用于调试模式）
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

