"""
Skill 执行器

负责根据 Skill 的 implementation 配置执行实际调用：
- python: 调用内置 Python 函数
- http: 调用外部 HTTP API
- mcp: 调用 MCP Server（通过 MCPClientManager）
"""

import asyncio
import importlib
import json
import logging
import threading
from typing import Any, Callable, Dict, Optional

import aiohttp

from .models import (
    HttpImplementation,
    ImplementationType,
    McpImplementation,
    PythonImplementation,
    SkillImplementation,
    SkillMetadata,
)

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Skill 执行器"""

    @staticmethod
    async def execute_async(skill: SkillMetadata, **kwargs) -> Any:
        """
        异步执行 Skill
        
        Args:
            skill: Skill 元数据
            **kwargs: 调用参数
            
        Returns:
            执行结果
        """
        if not skill.implementation:
            raise ValueError(f"Skill '{skill.name}' 是知识型 Skill，不支持执行调用")

        impl = skill.implementation
        impl_type = impl.type if isinstance(impl.type, str) else impl.type.value

        if impl_type == ImplementationType.PYTHON or impl_type == "python":
            return await SkillExecutor._execute_python(impl, **kwargs)
        elif impl_type == ImplementationType.HTTP or impl_type == "http":
            return await SkillExecutor._execute_http(impl, **kwargs)
        elif impl_type == ImplementationType.MCP or impl_type == "mcp":
            return await SkillExecutor._execute_mcp(impl, **kwargs)
        else:
            raise ValueError(f"不支持的执行协议: {impl_type}")

    @staticmethod
    def execute_sync(skill: SkillMetadata, **kwargs) -> Any:
        """
        同步执行 Skill（为 LangChain/Function Calling 提供同步接口）
        """
        # 统一使用线程 + 新事件循环的方式，避免事件循环嵌套问题
        result_container: Dict[str, Any] = {}
        exception_container: Dict[str, Exception] = {}

        def run_async():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result_container["value"] = new_loop.run_until_complete(
                        SkillExecutor.execute_async(skill, **kwargs)
                    )
                finally:
                    new_loop.close()
            except Exception as e:
                exception_container["value"] = e

        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        thread.join(timeout=60)

        if thread.is_alive():
            raise TimeoutError("Skill 执行超时（超过 60 秒）")
        if "value" in exception_container:
            raise exception_container["value"]
        return result_container.get("value")

    # =========================================================================
    # 各协议执行器
    # =========================================================================

    @staticmethod
    async def _execute_python(impl: PythonImplementation, **kwargs) -> Any:
        """执行 Python 函数、代码或本地脚本"""
        # 如果提供了 code，使用沙箱执行
        if impl.code:
            return await SkillExecutor._execute_python_code(impl.code, **kwargs)

        # ClawHub/OpenClaw 本地脚本型 Skill
        if impl.script_path and impl.skill_dir:
            from core.skills.script_executor import ScriptSkillExecutor
            result = await asyncio.to_thread(
                ScriptSkillExecutor.execute,
                skill_dir=impl.skill_dir,
                script_path=impl.script_path,
                args=kwargs,
                credentials={},
                timeout=impl.timeout,
            )
            if not result.get("success"):
                raise RuntimeError(result.get("error") or "脚本执行失败")
            return result.get("result")

        # 优先从 ToolRegistry 查找已注册的函数
        from core.tools.registry import get_tool_registry

        registry = get_tool_registry()
        func_name = impl.function
        func = None

        # ⚠️ 如果提供了 module，直接导入模块获取原始函数，不使用 ToolRegistry
        #    因为 ToolRegistry 中可能存的是 Skill wrapper 包装函数，
        #    会导致无限递归：wrapper → execute_sync → _execute_python → wrapper → ...
        if impl.module:
            try:
                module = importlib.import_module(impl.module)
                func = getattr(module, func_name)
                # 如果模块层函数被 @tool 装饰成了 StructuredTool，取出原始函数
                from langchain_core.tools import StructuredTool
                if isinstance(func, StructuredTool):
                    func = func.func
            except (ImportError, AttributeError) as e:
                raise RuntimeError(
                    f"无法加载 Python 函数 {impl.module}.{func_name}: {e}"
                )
        else:
            func = registry.get_function(func_name)

        if func is None:
            raise RuntimeError(f"找不到 Python 函数: {func_name}")

        # 执行
        import inspect
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        else:
            return func(**kwargs)

    @staticmethod
    async def _execute_python_code(code: str, **kwargs) -> Any:
        """在子进程沙箱中执行 Python 代码"""
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name

        try:
            input_data = json.dumps(kwargs, ensure_ascii=False)
            proc = subprocess.run(
                ["python", temp_path],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(__file__).parent.parent.parent),
            )

            if proc.returncode != 0:
                raise RuntimeError(proc.stderr or "代码执行失败")

            stdout = proc.stdout.strip()
            if "__SANDBOX_OUTPUT_START__" in stdout:
                start = stdout.index("__SANDBOX_OUTPUT_START__") + len("__SANDBOX_OUTPUT_START__")
                end = stdout.index("__SANDBOX_OUTPUT_END__")
                result_str = stdout[start:end].strip()
                try:
                    return json.loads(result_str)
                except Exception:
                    return result_str
            else:
                return stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    async def _execute_http(impl: HttpImplementation, **kwargs) -> Any:
        """执行 HTTP API 调用"""
        url = impl.url
        # URL 参数替换
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            if placeholder in url:
                url = url.replace(placeholder, str(value))

        # 分离已在 URL 中使用的参数
        remaining = {k: v for k, v in kwargs.items() if f"{{{k}}}" not in impl.url}

        params = None
        json_body = None

        if impl.method.upper() == "GET":
            params = remaining
        elif impl.method.upper() in ("POST", "PUT", "PATCH"):
            if impl.body_template:
                # 使用模板，替换占位符
                json_body = SkillExecutor._render_template(impl.body_template, remaining)
            else:
                json_body = remaining

        # 处理 headers 中的变量替换
        headers = dict(impl.headers) if impl.headers else {}
        for hk, hv in headers.items():
            for key, value in kwargs.items():
                headers[hk] = headers[hk].replace(f"{{{{{key}}}}}", str(value))

        timeout = aiohttp.ClientTimeout(total=impl.timeout)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=impl.method,
                    url=url,
                    headers=headers or None,
                    params=params,
                    json=json_body,
                ) as response:
                    try:
                        result = await response.json()
                    except Exception:
                        result = await response.text()

                    if response.status >= 400:
                        raise RuntimeError(f"HTTP {response.status}: {result}")

                    # 响应字段映射
                    if impl.response_mapping:
                        result = SkillExecutor._apply_response_mapping(
                            result, impl.response_mapping
                        )

                    return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"HTTP 请求超时（{impl.timeout}秒）: {url}")

    @staticmethod
    async def _execute_mcp(impl: McpImplementation, **kwargs) -> Any:
        """执行 MCP Server 调用

        通过 MCPClientManager 连接 MCP 服务器并调用指定工具。
        支持三种传输协议：stdio、sse、streamable_http。
        """
        from core.tools.mcp.client_manager import get_mcp_client_manager

        # 根据 transport 构造 MCP 服务器配置
        transport = (impl.transport or "sse").lower()
        if transport == "stdio":
            # stdio 模式下 server_url 用作 command
            config = {
                "transport_type": "stdio",
                "connection": {"command": impl.server_url, "args": []},
            }
        elif transport in ("sse", "streamable_http"):
            config = {
                "transport_type": transport,
                "connection": {"url": impl.server_url},
            }
        else:
            raise ValueError(f"不支持的 MCP 传输协议: {transport}")

        manager = get_mcp_client_manager()
        # MCPClientManager.call_tool 是同步方法（内部用后台事件循环），
        # 用 asyncio.to_thread 避免阻塞当前事件循环
        try:
            result = await asyncio.to_thread(
                manager.call_tool,
                config,
                impl.tool_name,
                kwargs,
                60,
            )
        except Exception as e:
            raise RuntimeError(
                f"MCP 工具调用失败 (server={impl.server_url}, "
                f"tool={impl.tool_name}): {e}"
            ) from e

        # 尝试将字符串结果解析为 JSON，便于下游处理
        if isinstance(result, str):
            try:
                return json.loads(result)
            except (json.JSONDecodeError, ValueError):
                return result
        return result

    # =========================================================================
    # 辅助方法
    # =========================================================================

    @staticmethod
    def _render_template(template: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """渲染请求体模板"""
        result = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                param_name = value[2:-2].strip()
                result[key] = params.get(param_name, value)
            elif isinstance(value, dict):
                result[key] = SkillExecutor._render_template(value, params)
            else:
                result[key] = value
        return result

    @staticmethod
    def _apply_response_mapping(data: Any, mapping: Dict[str, str]) -> Any:
        """应用响应字段映射"""
        result = {}
        for target_key, source_path in mapping.items():
            value = data
            for part in source_path.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                elif isinstance(value, list) and part.isdigit():
                    value = value[int(part)] if int(part) < len(value) else None
                else:
                    value = None
                    break
            result[target_key] = value
        return result

    @staticmethod
    def create_sync_wrapper(skill: SkillMetadata) -> Callable:
        """
        为 Skill 创建同步包装函数，用于注册到 ToolRegistry

        动态生成具有正确参数签名的函数，使 LangChain StructuredTool
        能正确推断 args_schema，从而让 Function Calling 参数正确传递。

        Returns:
            同步包装函数（带正确参数签名）
        """
        import inspect

        # 从 Skill 参数定义构建函数签名
        params = []
        for p in (skill.parameters or []):
            default = inspect.Parameter.empty if p.required else p.default
            params.append(
                inspect.Parameter(
                    name=p.name,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    default=default,
                )
            )

        def wrapper(**kwargs):
            return SkillExecutor.execute_sync(skill, **kwargs)

        wrapper.__name__ = skill.name.replace("-", "_")
        wrapper.__doc__ = skill.description

        # 设置正确的函数签名，让 LangChain 能推断出参数 schema
        if params:
            wrapper.__signature__ = inspect.Signature(parameters=params)

        return wrapper

