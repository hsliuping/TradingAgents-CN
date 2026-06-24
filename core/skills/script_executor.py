"""
脚本型 Skill 执行器

负责执行本地脚本型 Skill（从 ClawHub 安装的 Skill 包）。

核心功能：
1. {baseDir} 变量替换 - 将 Skill 包目录路径注入脚本执行环境
2. 脚本执行 - 通过子进程执行 scripts/*.py
3. 凭证注入 - 将配置的环境变量注入子进程（阶段 2 实现）

执行流程：
    1. 从 MongoDB doc 中获取 skill_dir 和 script_path
    2. 设置 baseDir 环境变量为 skill_dir
    3. 注入凭证环境变量（如有）
    4. 执行 scripts/*.py，传入参数
    5. 捕获 stdout/stderr，返回结果
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScriptSkillExecutor:
    """脚本型 Skill 执行器

    用于执行从 ClawHub 安装的本地 Skill 包中的 Python 脚本。
    支持 {baseDir} 变量替换和凭证注入。
    """

    # 默认执行超时（秒）
    DEFAULT_TIMEOUT = 60
    # {baseDir} 变量名（OpenClaw 标准）
    BASE_DIR_VAR = "baseDir"

    @staticmethod
    def execute_cli(
        skill_dir: str,
        script_path: str,
        args: Optional[List[str]] = None,
        credentials: Optional[Dict[str, str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        python_executable: Optional[str] = None,
    ) -> Dict[str, Any]:
        """以命令行参数方式执行 Skill 脚本

        适用于期望命令行参数的脚本（如 fetch_data.py "查询内容" --start-date ...）。

        Args:
            skill_dir: Skill 包目录绝对路径
            script_path: 脚本相对路径（如 "scripts/fetch_data.py"）
            args: 命令行参数列表（如 ["美联储利率政策", "--start-date", "2025-01-01T00:00:00"]）
            credentials: 凭证环境变量
            timeout: 超时秒数
            python_executable: Python 解释器

        Returns:
            {success, result, stdout, stderr, error, execution_time_ms, exit_code}
        """
        start = time.time()

        skill_dir_path = Path(skill_dir).resolve()
        full_script_path = skill_dir_path / script_path

        if not full_script_path.exists():
            return {
                "success": False, "result": None, "stdout": "", "stderr": "",
                "error": f"脚本文件不存在: {full_script_path}",
                "execution_time_ms": int((time.time() - start) * 1000), "exit_code": -1,
            }

        # 构建环境变量
        env = os.environ.copy()
        env[ScriptSkillExecutor.BASE_DIR_VAR] = str(skill_dir_path)
        if credentials:
            for key, value in credentials.items():
                if value is not None:
                    env[key] = str(value)

        # 构建命令：python script.py arg1 arg2 ...
        # 默认使用当前 Python 解释器（确保与项目使用同一 venv 的依赖）
        if not python_executable:
            python_executable = sys.executable or "python"
        cmd = [python_executable, str(full_script_path)]
        if args:
            cmd.extend(args)

        logger.info(
            f"🔧 CLI 执行: {' '.join(cmd)} (cwd={skill_dir_path.name}, timeout={timeout}s)"
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
                cwd=str(skill_dir_path),
                encoding="utf-8",
                errors="replace",
            )

            execution_time_ms = int((time.time() - start) * 1000)

            if result.returncode == 0:
                parsed = ScriptSkillExecutor._parse_output(result.stdout)
                return {
                    "success": True,
                    "result": parsed,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": None if not result.stderr else result.stderr,
                    "execution_time_ms": execution_time_ms,
                    "exit_code": 0,
                }
            else:
                # 把 stderr 和 stdout 都带上，方便诊断
                error_msg = (result.stderr or "").strip() or (result.stdout or "").strip() or f"退出码: {result.returncode}"
                return {
                    "success": False,
                    "result": None,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": error_msg,
                    "execution_time_ms": execution_time_ms,
                    "exit_code": result.returncode,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False, "result": None, "stdout": "", "stderr": "",
                "error": f"执行超时（{timeout}秒）",
                "execution_time_ms": int((time.time() - start) * 1000), "exit_code": -1,
            }
        except Exception as e:
            logger.error(f"❌ CLI 执行异常: {e}", exc_info=True)
            return {
                "success": False, "result": None, "stdout": "", "stderr": "",
                "error": str(e),
                "execution_time_ms": int((time.time() - start) * 1000), "exit_code": -1,
            }

    @staticmethod
    def execute(
        skill_dir: str,
        script_path: str,
        args: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        python_executable: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行 Skill 脚本

        Args:
            skill_dir: Skill 包目录绝对路径（用于 {baseDir} 替换）
            script_path: 脚本相对路径（如 "scripts/fetch_data.py"）
            args: 传递给脚本的参数（通过 stdin 传入 JSON）
            credentials: 凭证环境变量（阶段 2 实现，当前可选）
            timeout: 超时秒数
            python_executable: Python 解释器路径

        Returns:
            {
                "success": bool,
                "result": Any,  # stdout 解析结果
                "stdout": str,  # 原始 stdout
                "stderr": str,
                "error": Optional[str],
                "execution_time_ms": int,
                "exit_code": int
            }
        """
        start = time.time()

        # 构建脚本完整路径
        skill_dir_path = Path(skill_dir).resolve()
        full_script_path = skill_dir_path / script_path

        if not full_script_path.exists():
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": f"脚本文件不存在: {full_script_path}",
                "execution_time_ms": int((time.time() - start) * 1000),
                "exit_code": -1,
            }

        # 构建环境变量
        env = os.environ.copy()
        # {baseDir} 替换：将 Skill 包目录路径注入环境变量
        env[ScriptSkillExecutor.BASE_DIR_VAR] = str(skill_dir_path)
        # 凭证注入（阶段 2 实现，当前可选）
        if credentials:
            for key, value in credentials.items():
                if value is not None:
                    env[key] = str(value)

        # 构建命令
        # 默认使用当前 Python 解释器（确保与项目使用同一 venv 的依赖）
        if not python_executable:
            python_executable = sys.executable or "python"
        cmd = [python_executable, str(full_script_path)]

        # 准备输入参数（通过 stdin 传入 JSON）
        input_data = json.dumps(args, ensure_ascii=False) if args else ""

        try:
            logger.info(
                f"🔧 执行脚本型 Skill: {cmd[0]} {full_script_path.name} "
                f"(skill_dir={skill_dir_path.name}, timeout={timeout}s)"
            )

            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout,
                cwd=str(skill_dir_path),
                encoding="utf-8",
                errors="replace",
            )

            execution_time_ms = int((time.time() - start) * 1000)

            if result.returncode == 0:
                # 尝试解析 stdout 为 JSON
                parsed_result = ScriptSkillExecutor._parse_output(result.stdout)
                return {
                    "success": True,
                    "result": parsed_result,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": None if not result.stderr else result.stderr,
                    "execution_time_ms": execution_time_ms,
                    "exit_code": 0,
                }
            else:
                return {
                    "success": False,
                    "result": None,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": result.stderr or f"脚本退出码: {result.returncode}",
                    "execution_time_ms": execution_time_ms,
                    "exit_code": result.returncode,
                }

        except subprocess.TimeoutExpired:
            execution_time_ms = int((time.time() - start) * 1000)
            logger.warning(f"⏰ 脚本执行超时（{timeout}s）: {full_script_path}")
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": f"执行超时（{timeout}秒）",
                "execution_time_ms": execution_time_ms,
                "exit_code": -1,
            }
        except FileNotFoundError as e:
            execution_time_ms = int((time.time() - start) * 1000)
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": f"Python 解释器不存在: {python_executable} ({e})",
                "execution_time_ms": execution_time_ms,
                "exit_code": -1,
            }
        except Exception as e:
            execution_time_ms = int((time.time() - start) * 1000)
            logger.error(f"❌ 脚本执行异常: {e}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "exit_code": -1,
            }

    @staticmethod
    def replace_base_dir(text: str, skill_dir: str) -> str:
        """替换文本中的 Skill 包目录变量

        OpenClaw Skill 标准中，脚本和指令使用以下变量引用 Skill 包根目录：
        - {baseDir} - OpenClaw 官方标准变量
        - ${baseDir} - Shell 风格变量
        - <skill_dir> - 部分 ClawHub Skill 使用的变量（如 ifind-repilot）

        此函数将所有这些变量替换为实际的 skill_dir 路径。

        Args:
            text: 包含变量的文本
            skill_dir: Skill 包目录绝对路径

        Returns:
            替换后的文本
        """
        if not text:
            return text
        # 统一路径分隔符（Windows 兼容）
        normalized_dir = skill_dir.replace("\\", "/")
        return (
            text
            .replace("{baseDir}", normalized_dir)
            .replace("${baseDir}", normalized_dir)
            .replace("<skill_dir>", normalized_dir)
        )

    @staticmethod
    def prepare_script_args(skill_doc: Dict[str, Any], call_args: Dict[str, Any]) -> Dict[str, Any]:
        """准备脚本调用参数

        从 Skill doc 中提取 skill_dir 和 script_path，
        并对参数值进行 {baseDir} 替换。

        Args:
            skill_doc: MongoDB 中的 Skill 文档
            call_args: 调用参数

        Returns:
            {
                "skill_dir": str,
                "script_path": str,
                "args": Dict (已替换 {baseDir}),
                "credentials": Dict (从 doc 提取，阶段 2 实现)
            }
        """
        skill_dir = skill_doc.get("skill_dir", "")
        impl = skill_doc.get("implementation") or {}
        script_path = impl.get("script_path", "")

        # 对参数值进行 {baseDir} 替换
        prepared_args = {}
        for key, value in call_args.items():
            if isinstance(value, str):
                prepared_args[key] = ScriptSkillExecutor.replace_base_dir(value, skill_dir)
            else:
                prepared_args[key] = value

        return {
            "skill_dir": skill_dir,
            "script_path": script_path,
            "args": prepared_args,
            "credentials": {},  # 阶段 2 实现：从 skill_credentials 集合加载
        }

    @staticmethod
    def _parse_output(stdout: str) -> Any:
        """解析脚本输出

        优先尝试解析为 JSON，失败则返回原始字符串。

        Args:
            stdout: 脚本标准输出

        Returns:
            解析后的结果（dict/list/str）
        """
        if not stdout:
            return None

        stdout_stripped = stdout.strip()

        # 尝试直接解析为 JSON
        try:
            return json.loads(stdout_stripped)
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试从输出中提取 JSON 块（可能在 markdown 代码块中）
        import re
        json_block_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", stdout_stripped, re.DOTALL)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                pass

        # 尝试查找 __SANDBOX_OUTPUT_START__ / __SANDBOX_OUTPUT_END__ 标记
        sandbox_match = re.search(
            r"__SANDBOX_OUTPUT_START__\s*(.*?)\s*__SANDBOX_OUTPUT_END__",
            stdout_stripped,
            re.DOTALL,
        )
        if sandbox_match:
            try:
                return json.loads(sandbox_match.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                return sandbox_match.group(1).strip()

        # 返回原始字符串（截断过长的输出）
        if len(stdout_stripped) > 5000:
            return stdout_stripped[:5000] + "...(truncated)"
        return stdout_stripped
