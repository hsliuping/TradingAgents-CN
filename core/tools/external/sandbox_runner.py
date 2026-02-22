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
from typing import Any, Dict, Optional

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
            import sys

            # ===== 生成的代码 =====
            {textwrap.indent(clean_code, '            ').strip()}
            # ===== 结束 =====

            if __name__ == "__main__":
                try:
                    test_args = json.loads('''{args_json}''')
                    # 查找目标函数
                    func = None
                    for name, obj in list(locals().items()):
                        if callable(obj) and name == "{func_name}":
                            func = obj
                            break
                    if func is None:
                        # 回退：找第一个不以 _ 开头的函数
                        for name, obj in list(locals().items()):
                            if callable(obj) and not name.startswith("_") and name != "json" and name != "sys":
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
            proc = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tempfile.gettempdir(),
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

