"""
统一 LLM 客户端

提供统一的接口调用各种 LLM 提供商
"""

import asyncio
import inspect
import json
import logging
import re
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

from core.utils.retry import is_retryable as _is_retryable, retry_sync, retry_async

from .models import LLMConfig, LLMProvider, LLMResponse, Message, ToolCall, ToolResult
from .providers.base import BaseAdapter
from .providers.openai_compat import OpenAICompatAdapter

# 可选适配器
try:
    from .providers.google import GoogleAdapter
    GOOGLE_AVAILABLE = True
except ImportError:
    GoogleAdapter = None
    GOOGLE_AVAILABLE = False

try:
    from .providers.anthropic import AnthropicAdapter
    ANTHROPIC_AVAILABLE = True
except ImportError:
    AnthropicAdapter = None
    ANTHROPIC_AVAILABLE = False

from .tool_normalizer import ToolCallNormalizer


class UnifiedLLMClient:
    """
    统一 LLM 客户端
    
    自动选择合适的适配器，提供统一的调用接口
    
    用法:
        client = UnifiedLLMClient.from_config(config)
        response = client.chat(messages)
        
        # 或使用便捷方法
        client = UnifiedLLMClient.from_provider("deepseek")
    """
    
    def __init__(self, adapter: BaseAdapter):
        self._adapter = adapter
        self._tools: Dict[str, Callable] = {}

    @classmethod
    def _get_adapter_map(cls) -> Dict[LLMProvider, type]:
        """动态构建适配器映射（根据可用性）"""
        adapter_map = {
            LLMProvider.OPENAI: OpenAICompatAdapter,
            LLMProvider.DEEPSEEK: OpenAICompatAdapter,
            LLMProvider.DASHSCOPE: OpenAICompatAdapter,
            LLMProvider.ZHIPU: OpenAICompatAdapter,
            LLMProvider.SILICONFLOW: OpenAICompatAdapter,
            LLMProvider.OLLAMA: OpenAICompatAdapter,
            LLMProvider.OPENROUTER: OpenAICompatAdapter,
        }

        if GOOGLE_AVAILABLE:
            adapter_map[LLMProvider.GOOGLE] = GoogleAdapter

        if ANTHROPIC_AVAILABLE:
            adapter_map[LLMProvider.ANTHROPIC] = AnthropicAdapter

        return adapter_map

    @classmethod
    def from_config(cls, config: LLMConfig) -> "UnifiedLLMClient":
        """从配置创建客户端"""
        adapter_map = cls._get_adapter_map()
        adapter_class = adapter_map.get(config.provider)

        if not adapter_class:
            available_providers = list(adapter_map.keys())
            raise ValueError(
                f"不支持的提供商: {config.provider}。"
                f"可用的提供商: {available_providers}"
            )
        
        adapter = adapter_class(config)
        adapter.initialize()
        return cls(adapter)
    
    @classmethod
    def from_provider(
        cls,
        provider: str,
        model: Optional[str] = None,
        **kwargs
    ) -> "UnifiedLLMClient":
        """
        从提供商名称创建客户端 (自动从环境变量读取配置)
        
        Args:
            provider: 提供商名称 (deepseek, dashscope, google, etc.)
            model: 模型名称 (可选，使用默认值)
            **kwargs: 其他配置参数
        """
        provider_enum = LLMProvider(provider.lower())
        config = LLMConfig.from_env(provider_enum)
        
        if model:
            config.model = model
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return cls.from_config(config)
    
    def register_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        注册工具函数
        
        Args:
            func: 工具函数
            name: 工具名称
            description: 工具描述
            
        Returns:
            工具定义 (可用于 chat 调用)
        """
        tool_def = ToolCallNormalizer.normalize_tool_definition(func, name, description)
        tool_name = tool_def["function"]["name"]
        self._tools[tool_name] = func
        return tool_def

    def inject_tools(self, tools: Dict[str, Callable]) -> None:
        """
        批量注入工具函数（用于智能助手等场景）
        tools: {tool_name: callable} 映射
        """
        self._tools.update(tools)

    @staticmethod
    def _estimate_message_chars(messages: List[Message]) -> int:
        total = 0
        for message in messages:
            total += len(message.role or "")
            total += len(message.name or "")
            total += len(message.tool_call_id or "")
            total += len(message.content or "")
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    total += len(tool_call.id or "")
                    total += len(tool_call.name or "")
                    try:
                        total += len(json.dumps(tool_call.arguments or {}, ensure_ascii=False, default=str))
                    except Exception:
                        total += len(str(tool_call.arguments or {}))
        return total

    @staticmethod
    def _build_message_size_summary(messages: List[Message]) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        for index, message in enumerate(messages):
            tool_call_count = len(message.tool_calls or [])
            content_len = len(message.content or "")
            tool_args_len = 0
            for tool_call in message.tool_calls or []:
                try:
                    tool_args_len += len(json.dumps(tool_call.arguments or {}, ensure_ascii=False, default=str))
                except Exception:
                    tool_args_len += len(str(tool_call.arguments or {}))
            summary.append(
                {
                    "index": index,
                    "role": message.role,
                    "name": message.name,
                    "content_len": content_len,
                    "tool_call_count": tool_call_count,
                    "tool_args_len": tool_args_len,
                }
            )
        return summary

    def _log_tool_round_state(
        self,
        *,
        loop_name: str,
        round_number: int,
        stage: str,
        messages: List[Message],
    ) -> None:
        total_chars = self._estimate_message_chars(messages)
        top_messages = sorted(
            self._build_message_size_summary(messages),
            key=lambda item: item["content_len"] + item["tool_args_len"],
            reverse=True,
        )[:5]
        logger.info(
            "[%s] %s | round=%s | message_count=%s | approx_chars=%s | largest=%s",
            loop_name,
            stage,
            round_number,
            len(messages),
            total_chars,
            json.dumps(top_messages, ensure_ascii=False, default=str),
        )

    def _log_llm_call_timing(
        self,
        *,
        loop_name: str,
        stage: str,
        elapsed_seconds: float,
        messages: List[Message],
        response: Optional[LLMResponse],
        round_number: Optional[int] = None,
    ) -> None:
        logger.info(
            "[%s] %s | round=%s | elapsed=%.2fs | message_count=%s | approx_chars=%s | has_tool_calls=%s | tool_call_count=%s | content_chars=%s | finish_reason=%s",
            loop_name,
            stage,
            round_number if round_number is not None else "-",
            elapsed_seconds,
            len(messages),
            self._estimate_message_chars(messages),
            response.has_tool_calls if response else False,
            len(response.tool_calls) if response and response.tool_calls else 0,
            len(response.content or "") if response else 0,
            response.finish_reason if response else None,
        )

    @staticmethod
    def _serialize_message_for_log(message: Message) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "role": message.role,
            "name": message.name,
            "tool_call_id": message.tool_call_id,
            "content": message.content,
            "reasoning_content": message.reasoning_content,
        }
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
                for tool_call in message.tool_calls
            ]
        return payload

    @staticmethod
    def _serialize_response_for_log(response: Optional[LLMResponse]) -> Dict[str, Any]:
        if response is None:
            return {}

        return {
            "content": response.content,
            "reasoning_content": response.reasoning_content,
            "finish_reason": response.finish_reason,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
                for tool_call in response.tool_calls
            ],
        }

    def _log_llm_payload(
        self,
        *,
        loop_name: str,
        stage: str,
        payload_label: Optional[str],
        round_number: Optional[int] = None,
        messages: Optional[List[Message]] = None,
        response: Optional[LLMResponse] = None,
    ) -> None:
        if messages is not None:
            logger.info(
                "[%s] %s | label=%s | round=%s | payload=%s",
                loop_name,
                stage,
                payload_label or "-",
                round_number if round_number is not None else "-",
                json.dumps(
                    [self._serialize_message_for_log(message) for message in messages],
                    ensure_ascii=False,
                    default=str,
                ),
            )
            return

        logger.info(
            "[%s] %s | label=%s | round=%s | payload=%s",
            loop_name,
            stage,
            payload_label or "-",
            round_number if round_number is not None else "-",
            json.dumps(
                self._serialize_response_for_log(response),
                ensure_ascii=False,
                default=str,
            ),
        )

    @staticmethod
    def _log_tool_call_timing(
        *,
        loop_name: str,
        round_number: int,
        tool_name: str,
        elapsed_seconds: float,
        result: ToolResult,
    ) -> None:
        logger.info(
            "[%s] tool_exec_completed | round=%s | tool=%s | elapsed=%.2fs | chars=%s | is_error=%s",
            loop_name,
            round_number,
            tool_name,
            elapsed_seconds,
            len(result.content or ""),
            result.is_error,
        )

    async def _emit_progress(self, progress_callback: Optional[Callable], payload: Dict[str, Any]) -> None:
        """统一处理可选的进度回调，兼容同步/异步函数。"""
        if not progress_callback:
            return

        try:
            result = progress_callback(payload)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            logger.debug("[UnifiedLLM] 进度回调失败(忽略): %s", e)

    def _summarize_tool_result(self, tool_name: str, content: str) -> Dict[str, Any]:
        """提取批量工具结果摘要，便于前端展示执行产出。"""
        if not content:
            return {}

        if tool_name == "screen_stocks_by_criteria":
            match = re.search(r"共找到\s*(\d+)\s*只符合条件的股票，以下展示前\s*(\d+)\s*只", content)
            if match:
                return {
                    "total_candidates": int(match.group(1)),
                    "displayed_candidates": int(match.group(2)),
                }
            if "未找到符合条件的股票" in content:
                return {"total_candidates": 0, "displayed_candidates": 0}

        if tool_name == "batch_check_profit_consistency":
            match = re.search(r"稳定\s*(\d+)\s*只\s*\|\s*不稳定\s*(\d+)\s*只\s*\|\s*无数据\s*(\d+)\s*只", content)
            if match:
                return {
                    "stable_count": int(match.group(1)),
                    "volatile_count": int(match.group(2)),
                    "no_data_count": int(match.group(3)),
                }

        if tool_name == "add_stocks_to_favorites":
            summary: Dict[str, Any] = {}
            added_match = re.search(r"已添加\s*(\d+)\s*只股票到股票关注列表", content)
            existed_match = re.search(r"已存在\s*(\d+)\s*只", content)
            failed_match = re.search(r"失败\s*(\d+)\s*只", content)
            if added_match:
                summary["added_count"] = int(added_match.group(1))
            if existed_match:
                summary["existing_count"] = int(existed_match.group(1))
            if failed_match:
                summary["failed_count"] = int(failed_match.group(1))
            return summary

        if tool_name == "add_stock_to_watchlist":
            summary: Dict[str, Any] = {}
            added_match = re.search(r"已添加\s*(\d+)\s*只股票到[「\"]?([^」\"\n]+)[」\"]?", content)
            created_match = re.search(r"已自动创建分组[「\"]?([^」\"\n]+)[」\"]?并添加\s*(\d+)\s*只股票", content)
            existing_match = re.search(r"已在分组[「\"]?([^」\"\n]+)[」\"]?中", content)
            if added_match:
                summary["added_count"] = int(added_match.group(1))
            if created_match:
                summary["group_created"] = 1
                summary["added_count"] = int(created_match.group(2))
            if existing_match and "added_count" not in summary:
                summary["existing_count"] = 1
            return summary

        return {}

    @property
    def _max_retries(self) -> int:
        return getattr(self._adapter.config, "retry_times", 3)

    def _retry_chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """同步调用适配器，带指数退避重试。"""
        return retry_sync(
            self._adapter.chat,
            messages, tools,
            max_retries=self._max_retries,
            label="UnifiedLLM",
            **kwargs,
        )

    async def _aretry_chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """异步调用适配器，带指数退避重试。"""
        return await retry_async(
            self._adapter.achat,
            messages, tools,
            max_retries=self._max_retries,
            label="UnifiedLLM",
            **kwargs,
        )

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        auto_execute_tools: bool = False,
        max_tool_rounds: int = 5,
        **kwargs
    ) -> LLMResponse:
        """
        同步聊天
        
        Args:
            messages: 消息列表
            tools: 工具定义列表
            auto_execute_tools: 是否自动执行工具调用
            max_tool_rounds: 最大工具调用轮次
            **kwargs: 其他参数
        """
        response = self._retry_chat(messages, tools, **kwargs)
        
        if auto_execute_tools and response.has_tool_calls:
            return self._execute_tool_loop(
                messages, tools, response, max_tool_rounds, **kwargs
            )
        
        return response

    def chat_stream(
        self,
        messages: List[Message],
        on_delta: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ) -> LLMResponse:
        """同步流式聊天：逐段回调思考/正文增量，最终返回完整 LLMResponse。

        Args:
            messages: 消息列表（仅支持无工具调用的单轮场景）
            on_delta: 回调 on_delta(kind, text)，kind ∈ {"reset", "reasoning", "content"}；
                      重试开始前会先发一次 ("reset", "") 让调用方清空已收内容
            **kwargs: 其他参数（max_tokens、temperature 等）

        适配器不支持流式时自动回退到普通 chat，并把完整回复作为一次 content 增量回调。
        """
        stream_adapter = getattr(self._adapter, "chat_stream_deltas", None)

        if stream_adapter is None:
            response = self.chat(messages, **kwargs)
            if on_delta and response.content:
                on_delta("content", response.content)
            return response

        def _consume(**call_kwargs: Any) -> str:
            if on_delta:
                on_delta("reset", "")
            parts: List[str] = []
            for delta in stream_adapter(messages, **call_kwargs):
                if delta.get("type") == "content":
                    parts.append(delta.get("text") or "")
                if on_delta:
                    on_delta(delta.get("type", ""), delta.get("text") or "")
            return "".join(parts)

        content = retry_sync(
            _consume,
            max_retries=self._max_retries,
            label="UnifiedLLMStream",
            **kwargs,
        )
        return LLMResponse(
            content=content,
            model=getattr(self._adapter.config, "model", None),
            provider=getattr(self._adapter.config, "provider", None),
            finish_reason="stop",
        )
    
    async def achat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        auto_execute_tools: bool = False,
        max_tool_rounds: int = 5,
        tools_used: Optional[List[str]] = None,
        tool_results_collector: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable] = None,
        log_payloads: bool = False,
        payload_log_label: Optional[str] = None,
        tool_interceptor: Optional[Callable[[ToolCall], Awaitable[Optional[ToolResult]]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        异步聊天

        Args:
            tools_used: 可选，用于收集各轮工具调用名称（智能助手展示执行步骤用）
            tool_results_collector: 可选，用于收集各轮工具返回原文（数字溯源校验用），
                每项为 {"tool": 工具名, "content": 返回文本, "is_error": 是否出错}
            dry_run: 若为 True，工具调用只记日志并返回模拟结果，不真正执行函数（用于意图路由测试）
            tool_interceptor: 可选，在真正执行工具前调用；返回 ToolResult 则跳过默认执行
        """
        if log_payloads:
            self._log_llm_payload(
                loop_name="UnifiedLLM·异步",
                stage="initial_llm_prompt",
                payload_label=payload_log_label,
                messages=messages,
            )
        initial_started_at = time.perf_counter()
        response = await self._aretry_chat(messages, tools, **kwargs)
        if log_payloads:
            self._log_llm_payload(
                loop_name="UnifiedLLM·异步",
                stage="initial_llm_response",
                payload_label=payload_log_label,
                response=response,
            )
        self._log_llm_call_timing(
            loop_name="UnifiedLLM·异步",
            stage="initial_llm_completed",
            elapsed_seconds=time.perf_counter() - initial_started_at,
            messages=messages,
            response=response,
        )

        if auto_execute_tools and response.has_tool_calls:
            return await self._aexecute_tool_loop(
                messages, tools, response, max_tool_rounds,
                tools_used=tools_used,
                tool_results_collector=tool_results_collector,
                dry_run=dry_run,
                progress_callback=progress_callback,
                log_payloads=log_payloads,
                payload_log_label=payload_log_label,
                tool_interceptor=tool_interceptor,
                **kwargs
            )

        return response
    
    async def astream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """异步流式输出"""
        async for chunk in self._adapter.astream(messages, tools, **kwargs):
            yield chunk
    
    def _execute_tool_loop(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        response: LLMResponse,
        max_rounds: int,
        **kwargs
    ) -> LLMResponse:
        """执行工具调用循环"""
        current_messages = messages.copy()
        current_response = response
        rounds = 0
        
        while current_response.has_tool_calls and rounds < max_rounds:
            self._log_tool_round_state(
                loop_name="UnifiedLLM·同步",
                round_number=rounds + 1,
                stage="tool_round_started",
                messages=current_messages,
            )
            # 添加助手消息
            current_messages.append(current_response.to_message())
            
            # 执行所有工具调用
            for tool_call in current_response.tool_calls:
                result = ToolCallNormalizer.execute_tool_call(
                    tool_call, self._tools
                )
                # 添加工具结果消息
                current_messages.append(Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                    name=result.name
                ))
                logger.info(
                    "[UnifiedLLM·同步] tool_result_appended | round=%s | tool=%s | chars=%s | is_error=%s",
                    rounds + 1,
                    result.name,
                    len(result.content or ""),
                    result.is_error,
                )

            self._log_tool_round_state(
                loop_name="UnifiedLLM·同步",
                round_number=rounds + 1,
                stage="before_retry_chat",
                messages=current_messages,
            )
            
            current_response = self._retry_chat(current_messages, tools, **kwargs)
            rounds += 1

        # ── 最终综合：当工具轮次耗尽但 LLM 仍想调用工具时，强制生成文本回复 ──
        if current_response.has_tool_calls:
            logger.warning(
                f"[UnifiedLLM·同步] 工具调用轮次已达上限 ({max_rounds})，"
                f"LLM 仍请求工具调用，启动最终综合..."
            )
            # 不能把带 tool_calls 的 assistant 消息直接加入历史，
            # 否则 API 会要求紧跟对应的 tool response 消息（400 错误）。
            if current_response.content:
                current_messages.append(Message(
                    role="assistant",
                    content=current_response.content,
                ))
            current_messages.append(Message(
                role="user",
                content=(
                    "工具调用次数已达到上限，请不要再调用任何工具。"
                    "请根据上面已经获取到的所有数据，直接生成完整的分析回复。"
                ),
            ))
            current_response = self._retry_chat(
                current_messages, tools=None, **kwargs
            )

        return current_response

    async def _aexecute_tool_loop(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        response: LLMResponse,
        max_rounds: int,
        tools_used: Optional[List[str]] = None,
        tool_results_collector: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable] = None,
        log_payloads: bool = False,
        payload_log_label: Optional[str] = None,
        tool_interceptor: Optional[Callable[[ToolCall], Awaitable[Optional[ToolResult]]]] = None,
        **kwargs
    ) -> LLMResponse:
        """异步执行工具调用循环，可选收集每轮调用的工具名称"""
        from .models import LLMResponse  # 🔥 函数开头统一导入：避免 dry_run 分支内局部导入导致 intercepted 分支 UnboundLocalError
        current_messages = messages.copy()
        current_response = response
        rounds = 0

        while current_response.has_tool_calls and rounds < max_rounds:
            self._log_tool_round_state(
                loop_name="UnifiedLLM·异步",
                round_number=rounds + 1,
                stage="tool_round_started",
                messages=current_messages,
            )
            current_messages.append(current_response.to_message())
            await self._emit_progress(progress_callback, {
                "event": "tool_round_started",
                "round": rounds + 1,
                "tool_count": len(current_response.tool_calls),
            })

            intercepted_any = False
            for tool_call in current_response.tool_calls:
                if tools_used is not None:
                    tools_used.append(tool_call.name)

                await self._emit_progress(progress_callback, {
                    "event": "tool_started",
                    "round": rounds + 1,
                    "tool": tool_call.name,
                    "arguments": tool_call.arguments,
                })

                # ── v3.5.0 项4：工具执行拦截器（如智能助手 HITL）──
                intercepted_result: Optional[ToolResult] = None
                if tool_interceptor is not None and not dry_run:
                    try:
                        intercepted_result = await tool_interceptor(tool_call)
                        if intercepted_result is not None:
                            intercepted_any = True
                    except Exception as exc:
                        logger.warning(
                            "[UnifiedLLM·异步] tool_interceptor 异常，继续默认执行: %s",
                            exc,
                        )

                if intercepted_result is not None:
                    result = intercepted_result
                elif dry_run:
                    # ── 测试模式：只记日志，返回模拟结果 ──
                    logger.info(
                        "[DRY_RUN] 🏷️ LLM 选择工具: %s | 参数: %s",
                        tool_call.name,
                        json.dumps(tool_call.arguments, ensure_ascii=False),
                    )
                    result = ToolResult(
                        tool_call_id=tool_call.id,
                        name=tool_call.name,
                        content=f"[dry_run] 工具 {tool_call.name} 已被调用，参数: {json.dumps(tool_call.arguments, ensure_ascii=False)}",
                        is_error=False,
                    )
                else:
                    # ── 正常模式：真正执行工具 ──
                    tool_started_at = time.perf_counter()
                    result = await ToolCallNormalizer.aexecute_tool_call(
                        tool_call,
                        self._tools
                    )
                    self._log_tool_call_timing(
                        loop_name="UnifiedLLM·异步",
                        round_number=rounds + 1,
                        tool_name=tool_call.name,
                        elapsed_seconds=time.perf_counter() - tool_started_at,
                        result=result,
                    )
                    if log_payloads:
                        logger.info(
                            "[%s] tool_exec_payload | label=%s | round=%s | tool=%s | payload=%s",
                            "UnifiedLLM·异步",
                            payload_log_label or "-",
                            rounds + 1,
                            tool_call.name,
                            json.dumps(
                                {
                                    "arguments": tool_call.arguments,
                                    "result": result.content,
                                    "is_error": result.is_error,
                                },
                                ensure_ascii=False,
                                default=str,
                            ),
                        )
                await self._emit_progress(progress_callback, {
                    "event": "tool_completed",
                    "round": rounds + 1,
                    "tool": tool_call.name,
                    "is_error": result.is_error,
                    "preview": (result.content or "")[:400],
                    "summary": self._summarize_tool_result(tool_call.name, result.content or ""),
                })
                current_messages.append(Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                    name=result.name
                ))
                if tool_results_collector is not None:
                    tool_results_collector.append({
                        "tool": result.name or tool_call.name,
                        "content": result.content or "",
                        "is_error": bool(result.is_error),
                        # 工具调用参数（事实记忆层用 query/url 作主题键）
                        "args": dict(tool_call.arguments) if tool_call.arguments else {},
                    })
                logger.info(
                    "[UnifiedLLM·异步] tool_result_appended | round=%s | tool=%s | chars=%s | is_error=%s",
                    rounds + 1,
                    result.name,
                    len(result.content or ""),
                    result.is_error,
                )

            # dry_run 模式：只看第一轮 LLM 选了什么工具，不继续后续轮次
            if dry_run:
                logger.info("[DRY_RUN] ✅ 第 1 轮工具选择已记录，跳过后续轮次")
                # 不再调 LLM，直接构造一个纯文本回复返回
                return LLMResponse(
                    content=f"[dry_run 测试模式] LLM 选择的工具: {', '.join(tools_used or [])}",
                    model=current_response.model,
                )

            # 如果有工具被拦截（如 HITL 暂停），直接返回确认消息，不再继续后续轮次
            if intercepted_any:
                confirmation_contents = [
                    msg.content for msg in current_messages
                    if msg.role == "tool" and msg.content and "即将执行关键操作" in msg.content
                ]
                return LLMResponse(
                    content="\n\n".join(confirmation_contents) or "有待确认的操作，请确认后继续。",
                    model=current_response.model,
                )

            self._log_tool_round_state(
                loop_name="UnifiedLLM·异步",
                round_number=rounds + 1,
                stage="before_retry_chat",
                messages=current_messages,
            )
            if log_payloads:
                self._log_llm_payload(
                    loop_name="UnifiedLLM·异步",
                    stage="post_tool_llm_prompt",
                    payload_label=payload_log_label,
                    round_number=rounds + 1,
                    messages=current_messages,
                )
            retry_started_at = time.perf_counter()
            # 工具结果回传后的下一轮 LLM 思考同样可能持续较长时间（推理模型），
            # 发一条进度事件避免前端在「工具完成」后陷入长时间静默
            await self._emit_progress(progress_callback, {
                "event": "llm_thinking",
                "round": rounds + 2,
                "message": f"正在结合第 {rounds + 1} 轮工具结果继续分析…",
            })
            current_response = await self._aretry_chat(current_messages, tools, **kwargs)
            if log_payloads:
                self._log_llm_payload(
                    loop_name="UnifiedLLM·异步",
                    stage="post_tool_llm_response",
                    payload_label=payload_log_label,
                    round_number=rounds + 1,
                    response=current_response,
                )
            self._log_llm_call_timing(
                loop_name="UnifiedLLM·异步",
                stage="post_tool_llm_completed",
                round_number=rounds + 1,
                elapsed_seconds=time.perf_counter() - retry_started_at,
                messages=current_messages,
                response=current_response,
            )
            await self._emit_progress(progress_callback, {
                "event": "tool_round_completed",
                "round": rounds + 1,
            })
            rounds += 1

        # ── 最终综合：当工具轮次耗尽但 LLM 仍想调用工具时，强制生成文本回复 ──
        if current_response.has_tool_calls:
            logger.warning(
                f"[UnifiedLLM] 工具调用轮次已达上限 ({max_rounds})，"
                f"LLM 仍请求工具调用，启动最终综合..."
            )
            await self._emit_progress(progress_callback, {
                "event": "tool_limit_reached",
                "max_rounds": max_rounds,
            })
            # 注意：不能把带 tool_calls 的 assistant 消息直接加入历史，
            # 否则 API 会要求紧跟对应的 tool response 消息（400 错误）。
            # 只保留其中的文本内容（如果有），作为纯文本 assistant 消息。
            if current_response.content:
                current_messages.append(Message(
                    role="assistant",
                    content=current_response.content,
                ))
            # 添加一条 user 消息，强制 LLM 基于已有数据生成最终分析
            current_messages.append(Message(
                role="user",
                content=(
                    "工具调用次数已达到上限，请不要再调用任何工具。"
                    "请根据上面已经获取到的所有数据，直接生成完整的分析回复。"
                ),
            ))
            if log_payloads:
                self._log_llm_payload(
                    loop_name="UnifiedLLM·异步",
                    stage="final_summary_llm_prompt",
                    payload_label=payload_log_label,
                    round_number=rounds + 1,
                    messages=current_messages,
                )
            final_summary_started_at = time.perf_counter()
            current_response = await self._aretry_chat(
                current_messages, tools=None, **kwargs
            )
            if log_payloads:
                self._log_llm_payload(
                    loop_name="UnifiedLLM·异步",
                    stage="final_summary_llm_response",
                    payload_label=payload_log_label,
                    round_number=rounds + 1,
                    response=current_response,
                )
            self._log_llm_call_timing(
                loop_name="UnifiedLLM·异步",
                stage="final_summary_llm_completed",
                round_number=rounds + 1,
                elapsed_seconds=time.perf_counter() - final_summary_started_at,
                messages=current_messages,
                response=current_response,
            )
            logger.info("[UnifiedLLM] ✅ 最终综合完成")
            await self._emit_progress(progress_callback, {
                "event": "tool_limit_summary_completed",
                "max_rounds": max_rounds,
            })

        return current_response

    @property
    def provider(self) -> LLMProvider:
        """当前提供商"""
        return self._adapter.config.provider
    
    @property
    def model(self) -> str:
        """当前模型"""
        return self._adapter.config.model

