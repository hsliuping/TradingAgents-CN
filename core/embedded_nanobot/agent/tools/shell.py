import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any

from core.embedded_nanobot.agent.tools.base import Tool
from core.embedded_nanobot.security.network import contains_internal_url


class ExecTool(Tool):
    _MAX_TIMEOUT = 600
    _MAX_OUTPUT = 10_000

    def __init__(self, timeout: int = 60, working_dir: str | None = None, deny_patterns: list[str] | None = None, allow_patterns: list[str] | None = None, restrict_to_workspace: bool = False, path_append: str = ""):
        self.timeout = timeout
        self.working_dir = working_dir
        self.deny_patterns = deny_patterns or [r"\brm\s+-[rf]{1,2}\b", r"\bdel\s+/[fq]\b", r"\brmdir\s+/s\b", r"(?:^|[;&|]\s*)format\b", r"\b(mkfs|diskpart)\b", r"\bdd\s+if=", r">\s*/dev/sd", r"\b(shutdown|reboot|poweroff)\b", r":\(\)\s*\{.*\};\s*:"]
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self.path_append = path_append

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"command": {"type": "string"}, "working_dir": {"type": "string"}, "timeout": {"type": "integer", "minimum": 1, "maximum": 600}}, "required": ["command"]}

    async def execute(self, command: str, working_dir: str | None = None, timeout: int | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error
        effective_timeout = min(timeout or self.timeout, self._MAX_TIMEOUT)
        env = os.environ.copy()
        if self.path_append:
            env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd, env=env)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=effective_timeout)
            except asyncio.TimeoutError:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                finally:
                    if sys.platform != "win32":
                        try:
                            os.waitpid(process.pid, os.WNOHANG)
                        except (ProcessLookupError, ChildProcessError):
                            pass
                return f"Error: Command timed out after {effective_timeout} seconds"
            output_parts: list[str] = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            output_parts.append(f"\nExit code: {process.returncode}")
            result = "\n".join(output_parts) if output_parts else "(no output)"
            if len(result) > self._MAX_OUTPUT:
                half = self._MAX_OUTPUT // 2
                result = result[:half] + f"\n\n... ({len(result) - self._MAX_OUTPUT:,} chars truncated) ...\n\n" + result[-half:]
            return result
        except Exception as exc:
            return f"Error executing command: {exc}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        lower = command.strip().lower()
        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"
        if self.allow_patterns and not any(re.search(pattern, lower) for pattern in self.allow_patterns):
            return "Error: Command blocked by safety guard (not in allowlist)"
        if contains_internal_url(command):
            return "Error: Command blocked by safety guard (internal/private URL detected)"
        if self.restrict_to_workspace:
            if "..\\" in command or "../" in command:
                return "Error: Command blocked by safety guard (path traversal detected)"
            cwd_path = Path(cwd).resolve()
            for raw in self._extract_absolute_paths(command):
                try:
                    p = Path(os.path.expandvars(raw.strip())).expanduser().resolve()
                except Exception:
                    continue
                if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                    return "Error: Command blocked by safety guard (path outside working dir)"
        return None

    @staticmethod
    def _extract_absolute_paths(command: str) -> list[str]:
        win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)
        posix_paths = re.findall(r"(?:^|[\s|>'\"])(/[^\s\"'>;|<]+)", command)
        home_paths = re.findall(r"(?:^|[\s|>'\"])(~[^\s\"'>;|<]*)", command)
        return win_paths + posix_paths + home_paths