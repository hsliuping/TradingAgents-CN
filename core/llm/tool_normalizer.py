"""
工具调用标准化器

处理不同 LLM 提供商之间工具调用格式的差异
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from .models import LLMProvider, ToolCall, ToolResult

logger = logging.getLogger(__name__)


def normalize_ticker_for_engine(ticker: str) -> str:
    """
    将 LLM 传入的股票代码规范化为分析引擎期望的格式。
    分析引擎与数据源（MongoDB、AKShare 等）统一使用无后缀格式。

    - A股: 002594.SZ / 600519.SH → 002594 / 600519（6 位纯数字）
    - 港股: 0700.HK / 09988.HK → 0700 / 09988（去掉 .HK）
    - 美股: AAPL → AAPL（不变）
    """
    if not ticker or not isinstance(ticker, str):
        return ticker
    s = ticker.strip().upper()
    # A股：6位数字 + 交易所后缀 → 去掉后缀
    if re.match(r'^\d{6}\.(SZ|SH|SS|XSHE|XSHG)$', s):
        return s.split('.')[0]
    # 港股：4-5位数字.HK → 去掉后缀
    if re.match(r'^\d{4,5}\.HK$', s):
        return s.split('.')[0]
    return ticker


class ToolCallNormalizer:
    """
    工具调用标准化器
    
    统一处理:
    1. 工具定义格式转换
    2. 工具调用结果转换
    3. 工具执行和结果包装
    """
    
    @staticmethod
    def normalize_tool_definition(
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从函数创建标准化的工具定义
        
        Args:
            func: 工具函数
            name: 工具名称 (默认使用函数名)
            description: 工具描述 (默认使用函数文档字符串)
            
        Returns:
            OpenAI 格式的工具定义
        """
        import inspect
        
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        
        # 从类型注解推断参数
        sig = inspect.signature(func)
        hints = func.__annotations__ if hasattr(func, '__annotations__') else {}
        
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            
            param_type = hints.get(param_name, str)
            json_type = ToolCallNormalizer._python_type_to_json(param_type)
            
            properties[param_name] = {
                "type": json_type,
                "description": f"参数 {param_name}"
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_desc.strip(),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    @staticmethod
    def _python_type_to_json(python_type) -> str:
        """Python 类型转 JSON Schema 类型"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return type_map.get(python_type, "string")

    @staticmethod
    def _merge_tool_arguments(arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """兼容历史/异常工具调用格式，自动解包 kwargs。"""
        merged = {**(arguments or {}), **context}
        nested_kwargs = merged.get("kwargs")
        if isinstance(nested_kwargs, dict):
            normalized = {**nested_kwargs}
            for key, value in merged.items():
                if key != "kwargs":
                    normalized[key] = value
            return normalized
        return merged
    
    @staticmethod
    def execute_tool_call(
        tool_call: ToolCall,
        tools: Dict[str, Callable],
        **context
    ) -> ToolResult:
        """
        执行工具调用（同步版本，仅适用于同步工具函数）

        Args:
            tool_call: 工具调用对象
            tools: 可用工具字典 {name: callable}
            **context: 传递给工具的上下文参数

        Returns:
            工具执行结果
        """
        import inspect

        if tool_call.name not in tools:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"错误: 未找到工具 '{tool_call.name}'",
                is_error=True
            )

        try:
            func = tools[tool_call.name]
            # 合并参数
            kwargs = ToolCallNormalizer._merge_tool_arguments(tool_call.arguments, context)
            # 规范化股票代码：分析引擎统一使用无后缀格式（002594 而非 002594.SZ）
            for key in ('ticker', 'symbol'):
                if key in kwargs and kwargs[key]:
                    kwargs[key] = normalize_ticker_for_engine(str(kwargs[key]))

            # 若是异步函数，在新事件循环中执行（兼容同步调用场景）
            if inspect.iscoroutinefunction(func):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(func(**kwargs))
            else:
                result = func(**kwargs)

            # 确保结果是字符串
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False, default=str)

            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=result,
                is_error=False
            )
        except Exception as e:
            logger.exception("[ToolNormalizer] 工具 %s 同步执行异常: %s", tool_call.name, e)
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"工具执行错误: {str(e)}",
                is_error=True
            )

    @staticmethod
    def _get_tool_timeout(tool_name: str) -> int:
        """根据工具注册表中的 timeout_tier 返回超时秒数"""
        try:
            from core.tools import get_tool_registry, TOOL_TIMEOUT_SECONDS
            from core.tools.config import ToolTimeoutTier
            meta = get_tool_registry().get(tool_name)
            if meta:
                tier = getattr(meta, "timeout_tier", ToolTimeoutTier.MEDIUM)
                return TOOL_TIMEOUT_SECONDS.get(tier, TOOL_TIMEOUT_SECONDS[ToolTimeoutTier.MEDIUM])
        except Exception:
            pass
        return 45  # 默认 medium

    @staticmethod
    async def aexecute_tool_call(
        tool_call: ToolCall,
        tools: Dict[str, Callable],
        **context
    ) -> ToolResult:
        """
        异步执行工具调用，正确处理异步和同步工具函数，并按分层超时保护。

        - 异步工具：直接 await 调用
        - 同步工具：在线程池中运行，避免阻塞事件循环
        - 超时保护：根据工具 timeout_tier（light=15s, medium=45s, heavy=180s）

        Args:
            tool_call: 工具调用对象
            tools: 可用工具字典 {name: callable}
            **context: 传递给工具的上下文参数

        Returns:
            工具执行结果
        """
        import asyncio
        import inspect

        if tool_call.name not in tools:
            # 上报能力缺口：LLM 调用了不存在的工具
            try:
                from core.tools.external.skill_gap_detector import SkillGapDetector
                SkillGapDetector.report_gap(
                    gap_type="tool_not_found",
                    tool_name=tool_call.name,
                    agent_id="intelligent_assistant",
                    error="工具不存在于当前注册表",
                    context={
                        "tool_call_args": tool_call.arguments,
                        "available_tools_sample": list(tools.keys())[:20],
                    },
                )
            except Exception:
                pass

            # 记录到执行日志
            try:
                from core.tools.execution_logger import get_tool_execution_logger
                get_tool_execution_logger().log(
                    tool_id=tool_call.name,
                    agent_id="intelligent_assistant",
                    tool_args=tool_call.arguments,
                    result=None,
                    success=False,
                    execution_time_ms=0,
                    error="tool_not_found",
                )
            except Exception:
                pass

            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"错误: 未找到工具 '{tool_call.name}'",
                is_error=True
            )

        timeout_seconds = ToolCallNormalizer._get_tool_timeout(tool_call.name)
        import time as _time
        _exec_start = _time.perf_counter()

        def _log_exec(success: bool, result_str=None, error_str=None):
            try:
                from core.tools.execution_logger import get_tool_execution_logger
                get_tool_execution_logger().log(
                    tool_id=tool_call.name,
                    agent_id="intelligent_assistant",
                    tool_args=tool_call.arguments,
                    result=result_str,
                    success=success,
                    execution_time_ms=int((_time.perf_counter() - _exec_start) * 1000),
                    error=error_str,
                )
            except Exception:
                pass

        try:
            func = tools[tool_call.name]
            kwargs = ToolCallNormalizer._merge_tool_arguments(tool_call.arguments, context)
            for key in ('ticker', 'symbol'):
                if key in kwargs and kwargs[key]:
                    kwargs[key] = normalize_ticker_for_engine(str(kwargs[key]))

            if inspect.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(**kwargs), timeout=timeout_seconds)
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(func, **kwargs),
                    timeout=timeout_seconds,
                )

            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False, default=str)

            _log_exec(success=True, result_str=result)
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=result,
                is_error=False
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[ToolNormalizer] 工具 %s 执行超时（%ds），已中断",
                tool_call.name, timeout_seconds,
            )
            _log_exec(success=False, error_str=f"timeout {timeout_seconds}s")
            # 上报执行超时为能力缺口（间接说明工具效率不达预期）
            try:
                from core.tools.external.skill_gap_detector import SkillGapDetector
                SkillGapDetector.report_gap(
                    gap_type="tool_execution_error",
                    tool_name=tool_call.name,
                    agent_id="intelligent_assistant",
                    error=f"工具执行超时（{timeout_seconds}秒）",
                    context={"tool_call_args": tool_call.arguments},
                )
            except Exception:
                pass
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"工具执行超时（已超过 {timeout_seconds} 秒限制），请尝试简化参数或稍后重试。",
                is_error=True
            )
        except Exception as e:
            logger.exception("[ToolNormalizer] 工具 %s 异步执行异常: %s", tool_call.name, e)
            _log_exec(success=False, error_str=str(e))
            # 上报执行错误为能力缺口
            try:
                from core.tools.external.skill_gap_detector import SkillGapDetector
                SkillGapDetector.report_gap(
                    gap_type="tool_execution_error",
                    tool_name=tool_call.name,
                    agent_id="intelligent_assistant",
                    error=str(e),
                    context={"tool_call_args": tool_call.arguments},
                )
            except Exception:
                pass
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"工具执行错误: {str(e)}",
                is_error=True
            )

    @staticmethod
    def tool_result_to_message(
        result: ToolResult,
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """
        将工具结果转换为消息格式
        
        Args:
            result: 工具执行结果
            provider: LLM 提供商
            
        Returns:
            提供商特定的消息格式
        """
        if provider == LLMProvider.GOOGLE:
            return {
                "role": "user",
                "parts": [{
                    "function_response": {
                        "name": result.name,
                        "response": {"result": result.content}
                    }
                }]
            }
        else:
            # OpenAI 兼容格式
            return {
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "name": result.name,
                "content": result.content
            }

