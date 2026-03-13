"""
统一 LLM 客户端

提供统一的接口调用各种 LLM 提供商
"""

import asyncio
import inspect
import json
import logging
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

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
        response = self._adapter.chat(messages, tools, **kwargs)
        
        if auto_execute_tools and response.has_tool_calls:
            return self._execute_tool_loop(
                messages, tools, response, max_tool_rounds, **kwargs
            )
        
        return response
    
    async def achat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        auto_execute_tools: bool = False,
        max_tool_rounds: int = 5,
        tools_used: Optional[List[str]] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> LLMResponse:
        """
        异步聊天

        Args:
            tools_used: 可选，用于收集各轮工具调用名称（智能助手展示执行步骤用）
            dry_run: 若为 True，工具调用只记日志并返回模拟结果，不真正执行函数（用于意图路由测试）
        """
        response = await self._adapter.achat(messages, tools, **kwargs)

        if auto_execute_tools and response.has_tool_calls:
            return await self._aexecute_tool_loop(
                messages, tools, response, max_tool_rounds,
                tools_used=tools_used,
                dry_run=dry_run,
                progress_callback=progress_callback,
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
            
            # 继续对话
            current_response = self._adapter.chat(current_messages, tools, **kwargs)
            rounds += 1

        return current_response

    async def _aexecute_tool_loop(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        response: LLMResponse,
        max_rounds: int,
        tools_used: Optional[List[str]] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> LLMResponse:
        """异步执行工具调用循环，可选收集每轮调用的工具名称"""
        current_messages = messages.copy()
        current_response = response
        rounds = 0

        while current_response.has_tool_calls and rounds < max_rounds:
            current_messages.append(current_response.to_message())
            await self._emit_progress(progress_callback, {
                "event": "tool_round_started",
                "round": rounds + 1,
                "tool_count": len(current_response.tool_calls),
            })

            for tool_call in current_response.tool_calls:
                if tools_used is not None:
                    tools_used.append(tool_call.name)

                await self._emit_progress(progress_callback, {
                    "event": "tool_started",
                    "round": rounds + 1,
                    "tool": tool_call.name,
                    "arguments": tool_call.arguments,
                })

                if dry_run:
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
                    result = await ToolCallNormalizer.aexecute_tool_call(
                        tool_call,
                        self._tools
                    )
                await self._emit_progress(progress_callback, {
                    "event": "tool_completed",
                    "round": rounds + 1,
                    "tool": tool_call.name,
                    "is_error": result.is_error,
                    "preview": (result.content or "")[:400],
                })
                current_messages.append(Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                    name=result.name
                ))

            # dry_run 模式：只看第一轮 LLM 选了什么工具，不继续后续轮次
            if dry_run:
                logger.info("[DRY_RUN] ✅ 第 1 轮工具选择已记录，跳过后续轮次")
                # 不再调 LLM，直接构造一个纯文本回复返回
                from .models import LLMResponse
                return LLMResponse(
                    content=f"[dry_run 测试模式] LLM 选择的工具: {', '.join(tools_used or [])}",
                    model=current_response.model,
                )

            current_response = await self._adapter.achat(current_messages, tools, **kwargs)
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
            # 不传 tools 参数，强制纯文本回复
            current_response = await self._adapter.achat(
                current_messages, tools=None, **kwargs
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

