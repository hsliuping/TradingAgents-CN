"""
研究员Agent基类

用于实现研究员Agent（积极证据研究员、谨慎证据研究员等）
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

        import time as _time_exec
        _exec_start = _time_exec.time()

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
            # 🔍 调试日志：排查 ticker 丢失问题
            logger.error(
                f"🔍 [{self.agent_id}] state keys: {list(state.keys())[:20]}, "
                f"ticker={state.get('ticker')}, company_of_interest={state.get('company_of_interest')}, "
                f"trade_info存在={('trade_info' in state)}, code={state.get('trade_info', {}).get('code') if isinstance(state.get('trade_info'), dict) else 'N/A'}"
            )

            # 1. 提取输入参数（统一使用基类方法，兼容多种字段名与场景兜底）
            ticker, analysis_date = self._extract_common_params(state)

            if not ticker:
                logger.error(f"❌ [{self.agent_id}] ticker 未找到！state 全部 keys: {list(state.keys())}")
                raise ValueError("Missing required parameters: ticker")
            
            logger.info(f"✅ [{self.agent_id}] ticker 解析成功: {ticker}")
            
            # 2. 收集所需的报告
            reports = self._collect_reports(state)

            if not reports:
                raise ValueError("No reports available for analysis")

            # 3. 检测辩论模式并获取上下文
            is_debate_mode = self._is_debate_mode(state)

            if is_debate_mode:
                # 辩论模式：获取辩论上下文 + 向量缓存历史经验
                debate_context = self._get_debate_context(state)
                memory_context = self._get_memory_context(ticker, reports) if self.memory else None
                
                # 合并辩论上下文和向量缓存上下文
                context_parts = []
                if debate_context:
                    context_parts.append(debate_context)
                if memory_context:
                    context_parts.append(f"\n【历史经验（向量缓存）】\n{memory_context}")
                
                historical_context = "\n".join(context_parts) if context_parts else None
                logger.info(f"[辩论模式] {self.agent_id} 读取辩论历史 + 向量缓存")
            else:
                # 单次分析模式：从记忆系统获取历史上下文
                historical_context = self._get_memory_context(ticker, reports) if self.memory else None
                logger.info(f"[单次分析模式] {self.agent_id} 使用向量缓存")

            # v3.5.0 项1 闭环：检查质量门禁标记，低质量报告在 prompt 中提示
            # 让研究员感知哪些分析师报告质量存疑，从而降低结论权重
            quality_flags = state.get("quality_flags") or []
            if quality_flags:
                quality_hint = self._build_quality_hint(quality_flags)
                if quality_hint:
                    historical_context = (
                        quality_hint + "\n" + (historical_context or "")
                    ).strip()
                    logger.info(
                        f"[Researcher] 检测到 {len(quality_flags)} 条质量标记，已注入质量提示"
                    )

            # 4. 构建提示词
            # 传递 state 参数（子类可以从 state 中提取变量如 company_name, ticker 等）
            system_prompt = self._build_system_prompt(self.stance, state)

            user_prompt = self._build_user_prompt(ticker, analysis_date, reports, historical_context, state)
            
            # 5. 调用LLM分析
            system_prompt = self._apply_global_trading_advice_guard(system_prompt)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")

            # P1: 记录 Prompt
            if recorder:
                try:
                    recorder.record_inputs({"ticker": ticker, "analysis_date": analysis_date, "reports_keys": list(reports.keys()) if isinstance(reports, dict) else []})
                    recorder.record_prompts(system_prompt, user_prompt)
                except Exception as e:
                    logger.debug(f"[{self.agent_id}] 记录 Prompt 失败（不影响 agent）: {e}")
            
            if self._llm:
                import time
                _llm_start = time.time()
                logger.info(f"⏳ [{self.agent_id}] 开始调用 LLM (timeout={getattr(self._llm, 'timeout', '?')}, max_retries={getattr(self._llm, 'max_retries', '?')})...")
                try:
                    response = self._llm.invoke(messages)
                    _llm_elapsed = time.time() - _llm_start
                    logger.info(f"✅ [{self.agent_id}] LLM 调用完成, 耗时: {_llm_elapsed:.1f}s, 响应长度: {len(response.content) if response.content else 0}")
                except Exception as _llm_err:
                    _llm_elapsed = time.time() - _llm_start
                    logger.error(f"❌ [{self.agent_id}] LLM 调用失败, 耗时: {_llm_elapsed:.1f}s, 错误: {_llm_err}", exc_info=True)
                    raise
                report = self._parse_response(response.content)

                # P1: 记录 LLM 响应和解析输出
                if recorder:
                    try:
                        recorder.record_llm_response(response, llm_duration_ms=int(_llm_elapsed * 1000))
                        recorder.record_parsed_output({"report": report[:500] if isinstance(report, str) else str(report)[:500]})
                    except Exception as e:
                        logger.debug(f"[{self.agent_id}] 记录 LLM 响应失败（不影响 agent）: {e}")
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 保存到记忆系统（如果有）
            if self.memory:
                # 🔥 v2.0: 辩论模式下也保存到向量缓存，以便后续使用
                # v3.5.0 项3：同时触发反思提炼，把报告提炼为结构化教训
                self._save_to_memory(ticker, report, state=state)
                if is_debate_mode:
                    logger.info(f"[辩论模式] {self.agent_id} 已保存到向量缓存")

            # 7. 构建输出结果
            output_key = self.output_field or f"{self.researcher_type}_report"
            result = {output_key: report}

            # 8. 更新辩论状态（如果是辩论模式）
            if is_debate_mode:
                result = self._update_debate_state(state, report, result)
                logger.info(f"[辩论模式] {self.agent_id} 更新辩论状态")

            logger.info(f"研究员Agent {self.agent_id} 执行成功 (总耗时: {_time_exec.time() - _exec_start:.1f}s)")
            return result

        except Exception as e:
            logger.error(f"研究员Agent {self.agent_id} 执行失败 (总耗时: {_time_exec.time() - _exec_start:.1f}s): {e}", exc_info=True)
            # P1: 记录异常
            if recorder:
                try:
                    recorder.record_error(e)
                except Exception:
                    pass
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.researcher_type}_report"
            return {
                output_key: {
                    "error": str(e),
                    "success": False
                }
            }
        finally:
            # P1: 完成轨迹采集并写入 MongoDB（非阻塞）
            if recorder:
                try:
                    recorder.finish()
                except Exception:
                    pass
    
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

    def _build_quality_hint(self, quality_flags: List[Dict[str, Any]]) -> str:
        """构建质量提示文本（v3.5.0 项1 闭环）。

        将分析师报告的质量门禁标记转化为 prompt 提示，
        让研究员感知哪些分析师报告质量存疑，从而降低结论权重。

        Args:
            quality_flags: 质量标记列表，每项包含 agent_id/severity/reason

        Returns:
            质量提示文本，或空字符串
        """
        if not quality_flags:
            return ""

        hints: List[str] = []
        for flag in quality_flags:
            if not isinstance(flag, dict):
                continue
            agent_id = flag.get("agent_id", "未知分析师")
            severity = flag.get("severity", "")
            reason = flag.get("reason", "")
            retried = flag.get("retried", False)

            if severity == "critical":
                retry_note = "（已重试仍失败）" if retried else ""
                hints.append(
                    f"⚠️ {agent_id} 报告质量不合格{retry_note}：{reason}。"
                    f"请谨慎参考该分析师的结论，建议以其他分析师报告为主。"
                )
            elif severity == "warning":
                hints.append(
                    f"⚠️ {agent_id} 报告质量存疑：{reason}。"
                    f"建议降低该结论的参考权重。"
                )

        if not hints:
            return ""

        return "【质量提示】\n" + "\n".join(hints)
    
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

    def _save_to_memory(self, ticker: str, report: Dict[str, Any], state: Optional[Dict[str, Any]] = None) -> None:
        """
        保存到记忆系统

        Args:
            ticker: 股票代码
            report: 研究报告
            state: 工作流状态（用于提取 user_id 等上下文，v3.5.0 项3 反思节点需要）
        """
        if not self.memory:
            return

        try:
            # 提取报告内容
            if isinstance(report, dict):
                content = report.get("content", str(report))
            else:
                content = str(report)

            # 准备元数据
            from datetime import datetime
            metadata = {
                "ticker": ticker,
                "stance": self.stance,
                "agent_id": self.agent_id,
                "timestamp": datetime.now().isoformat()
            }

            if not hasattr(self.memory, 'add_memory'):
                logger.warning("记忆实例不支持 add_memory，已跳过保存: %s", type(self.memory).__name__)
                return

            success = self.memory.add_memory(
                content=content,
                metadata=metadata
            )
            if success:
                logger.info(f"✅ 保存到记忆系统: {ticker}, stance={self.stance}")

            # v3.5.0 项3：研究员报告反思提炼
            # 在原文写入后追加结构化教训节点，把报告提炼为 4 维度经验
            # 写入 ANALYSIS_INSIGHT scope，memory_kind=analysis_lesson
            # 失败时 helper 内部已降级，不阻塞主流程
            self._reflect_on_analysis(ticker, report, content, state=state)

        except Exception as e:
            logger.warning(f"保存到记忆系统失败: {e}")

    def _reflect_on_analysis(
        self,
        ticker: str,
        report: Dict[str, Any],
        original_content: str,
        state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """研究员报告反思提炼（v3.5.0 项3）。

        把本次分析报告提炼为结构化教训（reasoning/improvement/summary/query），
        写入 ANALYSIS_INSIGHT scope，memory_kind=analysis_lesson。

        下次同股票分析时，_get_memory_context 可优先召回结构化教训而非原文。

        降级策略：
        - LLM 超时/返回非 JSON → fallback 写入原文（reflection_success=False）
        - mem0 不可用 → 跳过
        - 任何异常 → 不阻塞主流程
        """
        try:
            from core.agents.reflection_helper import run_reflection_sync
            from core.agents.reflection_prompts import (
                ANALYSIS_REFLECTION_SYSTEM_PROMPT,
                build_analysis_reflection_user_prompt,
            )
            from core.memory.models import MemoryScope

            # 提取报告内容用于反思
            if isinstance(report, dict):
                stance = report.get("stance", self.stance)
            else:
                stance = self.stance

            analysis_date = ""
            if state:
                analysis_date = state.get("analysis_date") or state.get("trade_date") or ""
            if not analysis_date:
                try:
                    from datetime import datetime
                    analysis_date = datetime.now().strftime("%Y-%m-%d")
                except Exception:
                    pass

            user_prompt = build_analysis_reflection_user_prompt(
                ticker=ticker,
                report=report,
                analysis_date=analysis_date,
            )
            if not user_prompt.strip():
                return

            # 获取 db 句柄（用于 MemoryService）
            db = self._get_db_handle(state=state)
            if db is None:
                logger.debug("[Researcher] 反思跳过：未获取到 db 句柄")
                return

            user_id = self._get_user_id(state=state) or "default_user"

            success = run_reflection_sync(
                db=db,
                user_id=user_id,
                agent_id=self.agent_id,
                scope=MemoryScope.ANALYSIS_INSIGHT,
                memory_kind="analysis_lesson",
                system_prompt=ANALYSIS_REFLECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                fallback_content=original_content,
                fallback_metadata={
                    "symbol": str(ticker).upper(),
                    "stance": stance,
                    "agent_id": self.agent_id,
                    "analysis_date": analysis_date,
                    "source": "researcher_reflection",
                },
            )
            if success:
                logger.info(
                    f"[Researcher] 已写入 analysis_lesson 教训: ticker={ticker} stance={stance}"
                )
        except Exception as e:
            logger.warning(f"[Researcher] analysis_lesson 反思异常: {e}", exc_info=True)

    def _reflect_on_debate(
        self,
        ticker: str,
        debate_history: str,
        conclusion: str,
        debate_type: str,
        state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """辩论反思提炼（v3.6.0 项8）。

        在多情景研究 / 风险审阅达到最大轮数后触发，把多情景研究历史和最终裁决
        提炼为结构化教训（reasoning/improvement/summary/query），写入
        AGENT_EXPERIENCE scope，memory_kind=debate_lesson。

        下次同股票分析时，_get_memory_context 可召回多情景研究教训，
        让多视角对比从"对抗"升级为"积累"。

        降级策略：
        - LLM 超时/返回非 JSON → fallback 写入研究历史摘要（reflection_success=False）
        - mem0 不可用 → 跳过
        - 任何异常 → 不阻塞主流程
        """
        try:
            from core.agents.reflection_helper import run_reflection_sync
            from core.agents.reflection_prompts import (
                DEBATE_REFLECTION_SYSTEM_PROMPT,
                build_debate_reflection_user_prompt,
            )
            from core.memory.models import MemoryScope

            if not debate_history.strip() and not conclusion.strip():
                return

            user_prompt = build_debate_reflection_user_prompt(
                ticker=ticker,
                debate_history=debate_history,
                conclusion=conclusion,
                debate_type=debate_type,
            )
            if not user_prompt.strip():
                return

            db = self._get_db_handle(state=state)
            if db is None:
                logger.debug("[Researcher] 辩论反思跳过：未获取到 db 句柄")
                return

            user_id = self._get_user_id(state=state) or "default_user"

            # fallback 内容：取辩论历史末尾 + 结论（避免空字符串作为 fallback）
            fallback_parts = [f"辩论反思 {ticker} ({debate_type})"]
            if debate_history:
                # 仅保留末尾 800 字，避免 fallback 过长
                fallback_parts.append(debate_history[-800:])
            if conclusion:
                fallback_parts.append(f"最终裁决: {conclusion[:300]}")
            fallback_content = "\n\n".join(fallback_parts)

            success = run_reflection_sync(
                db=db,
                user_id=user_id,
                agent_id=self.agent_id,
                scope=MemoryScope.AGENT_EXPERIENCE,
                memory_kind="debate_lesson",
                system_prompt=DEBATE_REFLECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                fallback_content=fallback_content,
                fallback_metadata={
                    "symbol": str(ticker).upper() if ticker else "",
                    "stance": self.stance or "",
                    "agent_id": self.agent_id,
                    "debate_type": debate_type,
                    "source": "debate_reflection",
                },
            )
            if success:
                logger.info(
                    f"[Researcher] 已写入 debate_lesson 教训: ticker={ticker} type={debate_type}"
                )
        except Exception as e:
            logger.warning(f"[Researcher] debate_lesson 反思异常: {e}", exc_info=True)

    def _get_db_handle(self, state: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """获取 MongoDB 数据库句柄（用于 MemoryService）。

        ResearcherAgent 可能在不同上下文中被调用（工作流引擎、独立调用等），
        尝试从多个来源获取 db 句柄。
        """
        # 1. 从 state 获取（工作流引擎注入）
        if state and isinstance(state, dict):
            db = state.get("_db") or state.get("db")
            if db is not None:
                return db

        # 2. 从 self._db 获取（如果存在）
        if hasattr(self, "_db") and self._db is not None:
            return self._db

        # 3. 从 self.config.prompt_variables 获取（Pydantic 模型）
        try:
            if hasattr(self, "config") and self.config is not None:
                prompt_vars = getattr(self.config, "prompt_variables", None) or {}
                if isinstance(prompt_vars, dict):
                    db = prompt_vars.get("db") or prompt_vars.get("database")
                    if db is not None:
                        return db
        except Exception:
            pass

        # 4. 从全局 get_mongo_db 获取
        try:
            from app.core.database import get_mongo_db_sync
            return get_mongo_db_sync()
        except Exception:
            pass

        # 5. 尝试从 settings 直接构造
        try:
            from pymongo import MongoClient
            from app.core.config import settings
            client = MongoClient(settings.MONGO_URI)
            return client[settings.MONGO_DB]
        except Exception as e:
            logger.debug(f"[Researcher] 获取 db 句柄失败: {e}")
            return None

    def _get_user_id(self, state: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """获取当前用户 ID（用于 mem0 元数据）。"""
        # 1. 从 state 获取
        if state and isinstance(state, dict):
            user_id = state.get("user_id") or state.get("userId")
            if user_id:
                return str(user_id)

        # 2. 从 self._user_id 获取
        if hasattr(self, "_user_id") and self._user_id:
            return str(self._user_id)

        # 3. 从 self.config.prompt_variables 获取
        try:
            if hasattr(self, "config") and self.config is not None:
                prompt_vars = getattr(self.config, "prompt_variables", None) or {}
                if isinstance(prompt_vars, dict):
                    user_id = prompt_vars.get("user_id")
                    if user_id:
                        return str(user_id)
        except Exception:
            pass

        return None

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
            # 🔥 构建查询文本：使用关键信息而不是完整报告
            # 向量检索的目的是找到相似的历史经验，应该使用关键信息作为查询
            # 而不是把所有报告都合并（这样会导致查询文本过长，且不是好的查询方式）
            
            query_parts = []
            
            # 1. 股票基本信息（最重要的查询条件）
            if ticker:
                query_parts.append(f"股票代码: {ticker}")
            
            # 2. 从 reports 中提取关键信息（如果有）
            # 注意：reports 可能包含字典或字符串，需要处理
            company_name = None
            industry = None
            current_price = None
            
            for key, value in reports.items():
                if not value:
                    continue
                
                # 处理字典类型的值
                if isinstance(value, dict):
                    company_name = value.get("company_name") or value.get("name") or company_name
                    industry = value.get("industry") or industry
                    current_price = value.get("current_price") or current_price
                elif isinstance(value, str):
                    # 字符串类型的值，尝试提取关键信息
                    if key in ["company_name", "name"]:
                        company_name = value
                    elif key == "industry":
                        industry = value
                    elif key == "current_price":
                        try:
                            current_price = float(value)
                        except:
                            pass
            
            if company_name:
                query_parts.append(f"公司名称: {company_name}")
            if industry:
                query_parts.append(f"行业: {industry}")
            if current_price:
                query_parts.append(f"当前价格: {current_price}")
            
            # 3. 使用报告的摘要/关键部分（只取前 300 字符）
            # 这样可以保留关键信息，但不会太长
            MAX_SUMMARY_LENGTH = 300
            for key, value in reports.items():
                # 跳过已经处理过的字段和空值
                if key in ["company_name", "name", "industry", "current_price", "ticker"] or not value:
                    continue
                
                report_text = str(value)
                # 只取前 N 个字符作为摘要
                summary = report_text[:MAX_SUMMARY_LENGTH]
                if len(report_text) > MAX_SUMMARY_LENGTH:
                    summary += "..."
                query_parts.append(f"{key}摘要: {summary}")
            
            # 构建查询文本
            curr_situation = "\n".join(query_parts)
            
            # 🔥 限制查询文本总长度，确保不超过 Embedding API 限制
            MAX_QUERY_LENGTH = 2000  # 使用关键信息，应该不会太长
            if len(curr_situation) > MAX_QUERY_LENGTH:
                logger.warning(f"⚠️ 查询文本过长 ({len(curr_situation):,} > {MAX_QUERY_LENGTH:,})，进行截断")
                curr_situation = curr_situation[:MAX_QUERY_LENGTH] + "..."
                logger.info(f"📝 截断后查询文本长度: {len(curr_situation):,} 字符")
            
            logger.debug(f"🔍 构建查询文本（使用关键信息）: {curr_situation[:500]}...")

            # 🔧 检查是否启用记忆功能（一级分析深度不使用记忆）
            # 🔥 self.config 是 AgentConfig (Pydantic BaseModel)，直接访问属性
            memory_enabled = getattr(self.config, "memory_enabled", True)
            if not memory_enabled:
                logger.info(f"📭 记忆功能已禁用（快速分析模式）")
                return ""

            if not hasattr(self.memory, 'search_memories'):
                logger.warning("记忆实例不支持 search_memories，已跳过召回: %s", type(self.memory).__name__)
                return ""

            past_memories = self.memory.search_memories(
                query=curr_situation,
                n_results=3,
                filter_metadata={"ticker": ticker} if ticker else None
            )

            memory_str = ""
            for i, mem in enumerate(past_memories, 1):
                content = mem.get("content", "")
                similarity = mem.get("similarity", 0.0)

                # 只使用相似度 > 0.7 的记忆
                if similarity > 0.7:
                    memory_str += f"[相似度: {similarity:.2f}] {content}\n\n"

            # v3.5.0 闭环 L2/L3：优先召回 mem0 中的反思教训
            # 反思教训通过 reflection_helper.run_reflection 写入 mem0，
            # 这里通过 recall_lessons_sync 召回并注入 prompt，形成完整闭环。
            lessons_str = ""
            try:
                from core.agents.reflection_helper import recall_lessons_sync
                db = self._get_db_handle()
                if db is not None:
                    user_id = self._get_user_id() or "default_user"
                    lessons_str = recall_lessons_sync(
                        db=db,
                        user_id=user_id,
                        query=curr_situation,
                        agent_id=self.agent_id,
                        limit=3,
                        max_chars=1500,
                    )
                    if lessons_str:
                        logger.info(f"🧠 从 mem0 召回反思教训（闭环 L2/L3）")
            except Exception as lessons_exc:
                logger.debug(f"[Researcher] 召回反思教训失败（不阻塞）: {lessons_exc}")

            # 教训放在前面（优先参考），原文放在后面
            if lessons_str and memory_str:
                return f"\n{lessons_str}\n【历史经验】\n{memory_str}"
            elif lessons_str:
                return f"\n{lessons_str}"
            elif memory_str:
                logger.info(f"🧠 从记忆系统检索到 {len(past_memories)} 条相关经验")
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

