"""
沙箱执行器 — 子进程隔离运行生成的代码

核心特性：
- subprocess 隔离执行（独立进程，防止污染主进程）
- 30 秒超时保护
- stdout / stderr / 返回值捕获
- 资源限制（内存、CPU 时间）
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from core.python_runtime import resolve_python_executable
from .skill_spec import SandboxResult, SkillSpec

logger = logging.getLogger(__name__)

# 默认超时（秒）
DEFAULT_TIMEOUT = 30


class SandboxRunner:
    """
    沙箱执行器

    在独立子进程中运行生成的 Python 代码，捕获输出和返回值。
    """

    # 需要从生成代码中剥离的装饰器模式
    _DECORATOR_PATTERNS = [
        r"^\s*@tool\b.*$",
        r"^\s*@register_tool\b.*$",
    ]
    # 需要从生成代码中剥离的导入模式
    _IMPORT_STRIP_PATTERNS = [
        r"^\s*from\s+core\.tools\.base\s+import\b.*$",
        r"^\s*from\s+langchain_core\.tools\s+import\s+tool\b.*$",
    ]

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        # 项目根目录（用于设置 PYTHONPATH）
        self._project_root = str(Path(__file__).parent.parent.parent.parent)
        self._python_executable = resolve_python_executable(
            self._project_root,
            env_var_names=("TRADINGAGENTS_SANDBOX_PYTHON_EXE", "TRADINGAGENTS_PYTHON_EXE"),
        )

    def run(
        self,
        code: str,
        spec: SkillSpec,
        test_input: Optional[Dict[str, Any]] = None,
    ) -> SandboxResult:
        """
        在沙箱中执行生成的代码

        Args:
            code: 完整的 Python 函数代码
            spec: Skill 规格书（用于确定函数名和测试输入）
            test_input: 测试输入参数（优先于 spec.test_input）

        Returns:
            SandboxResult: 执行结果
        """
        test_args = test_input or spec.test_input or {}
        start_time = time.time()

        # 构造执行脚本
        runner_script = self._build_runner_script(code, spec.tool_id, test_args)

        try:
            result = self._execute_in_subprocess(runner_script)
            result.execution_time = round(time.time() - start_time, 3)
            return result
        except Exception as e:
            logger.error(f"沙箱执行异常: {e}")
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time=round(time.time() - start_time, 3),
            )

    def run_diagnostic_script(
        self,
        script: str,
        *,
        allowed_tools: Optional[Sequence[str]] = None,
    ) -> SandboxResult:
        """执行构建期诊断脚本，并注入 hermes_tools RPC 等价 stub。

        该能力只供 Agentic Skill 生成阶段确认真实字段/接口返回形状，
        不允许进入最终 Skill 产物；最终代码仍由 StaticValidator 拦截 hermes_tools 等依赖。
        """
        start_time = time.time()
        logger.info(
            "🧪 [DiagnosticSandbox] start script_chars=%s allowed_tools=%s timeout=%s",
            len(script or ""),
            list(allowed_tools or []),
            self.timeout,
        )
        try:
            runner_script = self._build_diagnostic_runner_script(
                script,
                allowed_tools=allowed_tools,
            )
            result = self._execute_in_subprocess(runner_script)
            result.execution_time = round(time.time() - start_time, 3)
            logger.info(
                "🧪 [DiagnosticSandbox] done success=%s execution_time=%.3fs error=%s stdout_chars=%s stderr_chars=%s",
                result.success,
                result.execution_time,
                result.error,
                len(result.stdout or ""),
                len(result.stderr or ""),
            )
            return result
        except Exception as e:
            logger.error("诊断沙箱执行异常: %s", e)
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time=round(time.time() - start_time, 3),
            )

    def _strip_decorators_and_imports(self, code: str) -> str:
        """
        从生成代码中剥离装饰器和项目专有导入

        即使 CodeGenerator 的 prompt 已明确禁止装饰器，
        LLM 仍可能生成带有 @tool / @register_tool 的代码。
        这里做最后一道防线。
        """
        lines = code.split("\n")
        cleaned = []
        all_patterns = self._DECORATOR_PATTERNS + self._IMPORT_STRIP_PATTERNS
        for line in lines:
            skip = False
            for pat in all_patterns:
                if re.match(pat, line):
                    skip = True
                    break
            if not skip:
                cleaned.append(line)
        return "\n".join(cleaned)

    def _build_runner_script(
        self, code: str, func_name: str, test_args: Dict[str, Any]
    ) -> str:
        """构造沙箱执行脚本"""
        # 先剥离装饰器和项目导入
        clean_code = self._strip_decorators_and_imports(code)
        args_json = json.dumps(test_args, ensure_ascii=False)
        # 用 textwrap.dedent 确保缩进一致
        script = textwrap.dedent(f"""\
            import json
            import os
            import sys

            PROJECT_ROOT = r"{self._project_root}"
            if PROJECT_ROOT not in sys.path:
                sys.path.insert(0, PROJECT_ROOT)
            os.chdir(PROJECT_ROOT)

            # ===== 生成的代码 =====
            {textwrap.indent(clean_code, '            ').strip()}
            # ===== 结束 =====

            if __name__ == "__main__":
                try:
                    import types as _types
                    test_args = json.loads('''{args_json}''')
                    # 查找目标函数
                    func = None
                    for name, obj in list(locals().items()):
                        if callable(obj) and name == "{func_name}":
                            func = obj
                            break
                    if func is None:
                        # 回退：找第一个不以 _ 开头的用户定义函数
                        # 排除类型（如 datetime）、模块、内置函数、typing 类型、import 来的函数等非 Skill 函数
                        import typing as _typing
                        _skip_names = {{"json", "sys", "os", "_types", "_typing", "test_args", "func", "name", "obj"}}
                        for name, obj in list(locals().items()):
                            if name.startswith("_") or name in _skip_names:
                                continue
                            if not callable(obj):
                                continue
                            # 只接受函数（lambda 或 def），排除类/类型
                            if isinstance(obj, type):
                                continue
                            # 排除模块
                            if isinstance(obj, _types.ModuleType):
                                continue
                            # 排除内置函数
                            if isinstance(obj, _types.BuiltinFunctionType):
                                continue
                            # 排除 typing 类型（Optional, Dict, List, Any 等）
                            # typing._SpecialForm 是 callable 但不是 type，会被误认为函数
                            if hasattr(obj, "__module__") and getattr(obj, "__module__", "").startswith("typing"):
                                continue
                            # 排除 typing._GenericAlias 实例（如 Dict[str, Any]）
                            if hasattr(_typing, "_GenericAlias") and isinstance(obj, _typing._GenericAlias):
                                continue
                            if hasattr(_typing, "_SpecialForm") and isinstance(obj, _typing._SpecialForm):
                                continue
                            # 排除从 import 来的函数（非用户定义）
                            # 用户定义的函数 __module__ 是 "__main__"，import 来的函数 __module__ 是包路径
                            obj_module = getattr(obj, "__module__", "")
                            if obj_module and obj_module != "__main__":
                                continue
                            func = obj
                            break
                    if func is None:
                        print(json.dumps({{"__error__": "未找到可执行的函数"}}))
                        sys.exit(1)

                    result = func(**test_args)
                    print("__SANDBOX_OUTPUT_START__")
                    print(json.dumps(result, ensure_ascii=False, default=str))
                    print("__SANDBOX_OUTPUT_END__")
                except Exception as e:
                    print(json.dumps({{"__error__": str(e)}}), file=sys.stderr)
                    sys.exit(1)
        """)
        return script

    def _build_diagnostic_runner_script(
        self,
        script: str,
        *,
        allowed_tools: Optional[Sequence[str]] = None,
    ) -> str:
        """构造构建期诊断脚本，提供 hermes_tools stub。"""
        allowed = list(allowed_tools or (
            "run_readonly_query",
            "probe_interface",
            "inspect_collection_schema",
            "describe_runtime_helper",
        ))
        allowed_json = json.dumps(allowed, ensure_ascii=False)
        user_script = str(script or "")
        return textwrap.dedent(f"""\
            import json
            import os
            import sys
            import types

            PROJECT_ROOT = r"{self._project_root}"
            if PROJECT_ROOT not in sys.path:
                sys.path.insert(0, PROJECT_ROOT)
            os.chdir(PROJECT_ROOT)

            _ALLOWED_TOOLS = set(json.loads('''{allowed_json}'''))
            _CALL_COUNT = 0
            _MAX_CALLS = 12

            def _call_build_tool(name, *args, **kwargs):
                global _CALL_COUNT
                if name not in _ALLOWED_TOOLS:
                    raise PermissionError(f"diagnostic tool not allowed: {{name}}")
                _CALL_COUNT += 1
                if _CALL_COUNT > _MAX_CALLS:
                    raise RuntimeError("diagnostic tool call limit exceeded")
                from core.tools.external import recon_tools
                func = getattr(recon_tools, name, None)
                if not callable(func):
                    raise RuntimeError(f"diagnostic tool not found: {{name}}")
                raw = func(*args, **kwargs)
                try:
                    return json.loads(raw)
                except Exception:
                    return raw

            hermes_tools = types.ModuleType("hermes_tools")
            for _name in _ALLOWED_TOOLS:
                setattr(hermes_tools, _name, (lambda tool_name: (lambda *args, **kwargs: _call_build_tool(tool_name, *args, **kwargs)))(_name))
            sys.modules["hermes_tools"] = hermes_tools

            if __name__ == "__main__":
                try:
                    _globals = {{"__name__": "__diagnostic__"}}
                    exec({user_script!r}, _globals, _globals)
                    result = _globals.get("result", _globals.get("RESULT", None))
                    print("__SANDBOX_OUTPUT_START__")
                    print(json.dumps({{"result": result, "tool_call_count": _CALL_COUNT}}, ensure_ascii=False, default=str))
                    print("__SANDBOX_OUTPUT_END__")
                except Exception as e:
                    print(json.dumps({{"__error__": str(e)}}), file=sys.stderr)
                    sys.exit(1)
        """)

    def _execute_in_subprocess(self, script: str) -> SandboxResult:
        """在子进程中执行脚本"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            temp_path = f.name

        # 设置 PYTHONPATH 让子进程能找到项目模块（安全网）
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = self._project_root + (os.pathsep + existing if existing else "")

        try:
            logger.debug("Skill 沙箱使用 Python: %s", self._python_executable)
            proc = subprocess.run(
                [self._python_executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self._project_root,
                env=env,
            )

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            # 提取返回值
            output = None
            if "__SANDBOX_OUTPUT_START__" in stdout:
                start = stdout.index("__SANDBOX_OUTPUT_START__") + len("__SANDBOX_OUTPUT_START__")
                end = stdout.index("__SANDBOX_OUTPUT_END__")
                raw = stdout[start:end].strip()
                try:
                    output = json.loads(raw)
                except json.JSONDecodeError:
                    output = raw

            if proc.returncode != 0:
                error_msg = stderr
                if stderr:
                    try:
                        err_data = json.loads(stderr)
                        if "__error__" in err_data:
                            error_msg = err_data["__error__"]
                    except json.JSONDecodeError:
                        pass
                return SandboxResult(
                    success=False, output=output,
                    stdout=stdout, stderr=stderr, error=error_msg,
                )

            return SandboxResult(
                success=True, output=output,
                stdout=stdout, stderr=stderr,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"执行超时（{self.timeout}s）",
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

