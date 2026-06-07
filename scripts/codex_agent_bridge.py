#!/usr/bin/env python3
"""
Local Codex Agent HTTP bridge.

The TradingAgents backend runs inside Docker and cannot execute the macOS Codex
CLI directly. This small host-side bridge exposes a local HTTP endpoint that
invokes `codex exec` and returns the final message as JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional


DEFAULT_CODEX_PATH = "/Applications/Codex.app/Contents/Resources/codex"


class CodexBridgeError(RuntimeError):
    """Raised when Codex bridge execution fails."""


@dataclass
class BridgeConfig:
    codex_binary: str
    workspace: str
    model: Optional[str] = None
    sandbox: str = "read-only"
    timeout: int = 900


def default_codex_binary() -> str:
    return (
        os.getenv("CODEX_AGENT_CODEX_BIN", "").strip()
        or shutil.which("codex")
        or DEFAULT_CODEX_PATH
    )


def config_from_env() -> BridgeConfig:
    return BridgeConfig(
        codex_binary=default_codex_binary(),
        workspace=os.getenv("CODEX_AGENT_WORKSPACE", os.getcwd()).strip() or os.getcwd(),
        model=os.getenv("CODEX_AGENT_MODEL", "").strip() or None,
        sandbox=os.getenv("CODEX_AGENT_SANDBOX", "read-only").strip() or "read-only",
        timeout=int(os.getenv("CODEX_AGENT_TIMEOUT", "900")),
    )


def build_codex_command(config: BridgeConfig, output_path: str) -> List[str]:
    command = [
        config.codex_binary,
        "exec",
        "--cd",
        config.workspace,
        "--sandbox",
        config.sandbox,
        "--skip-git-repo-check",
        "--ephemeral",
        "--color",
        "never",
        "--output-last-message",
        output_path,
    ]
    if config.model:
        command.extend(["--model", config.model])
    command.append("-")
    return command


def build_codex_prompt(payload: Mapping[str, Any]) -> str:
    prompt = str(payload.get("prompt") or "").strip()
    context = payload.get("context") if isinstance(payload.get("context"), Mapping) else {}
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    stock_code = context.get("stock_code") or context.get("symbol") or "未知"
    market_type = context.get("market_type") or "未知"
    analysis_date = context.get("analysis_date") or "未知"
    research_depth = context.get("research_depth") or "标准"

    return f"""你是 TradingAgents-CN 平台中的只读 Codex Agent 股票分析引擎。

请不要修改文件、不要下单、不要执行任何有副作用的操作。请基于用户任务和上下文输出 Markdown 股票分析报告。

用户任务：
{prompt or "请生成股票分析报告。"}

核心上下文：
- 股票代码：{stock_code}
- 市场类型：{market_type}
- 分析日期：{analysis_date}
- 研究深度：{research_depth}

任务上下文 JSON：
```json
{context_json}
```

输出要求：
- 使用中文 Markdown
- 明确说明数据限制，不要编造精确行情
- 包含核心结论、技术/市场分析、基本面分析、新闻情绪、风险因素、最终建议
- 最终建议请在“买入、持有、卖出、观望”中选择一个
"""


def run_codex_agent(
    payload: Mapping[str, Any],
    config: BridgeConfig,
    runner: Callable[..., Any] = subprocess.run,
) -> Dict[str, Any]:
    prompt = build_codex_prompt(payload)

    with tempfile.TemporaryDirectory(prefix="codex-agent-bridge-") as tmp_dir:
        output_path = str(Path(tmp_dir) / "last_message.md")
        command = build_codex_command(config, output_path)
        completed = runner(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=config.timeout,
            cwd=config.workspace,
        )

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise CodexBridgeError(f"Codex CLI 执行失败: {detail}")

        output_file = Path(output_path)
        content = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else ""
        if not content:
            content = (completed.stdout or "").strip()
        if not content:
            raise CodexBridgeError("Codex CLI 没有返回分析内容")

        return {
            "content": content,
            "agent_engine": "codex",
            "model_info": f"Codex CLI ({config.model or 'default model'})",
            "tokens_used": 0,
        }


class CodexBridgeHandler(BaseHTTPRequestHandler):
    server_version = "CodexAgentBridge/1.0"

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send_json({"status": "ok", "service": "codex-agent-bridge"})
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/analyze":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return

        if not self._authorized():
            self._send_json({"error": "unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
            return

        try:
            payload = self._read_json_body()
            result = run_codex_agent(payload, self.server.config)  # type: ignore[attr-defined]
            self._send_json(result)
        except CodexBridgeError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
        except subprocess.TimeoutExpired:
            self._send_json({"error": "Codex CLI 执行超时"}, status=HTTPStatus.GATEWAY_TIMEOUT)
        except Exception as exc:
            self._send_json({"error": f"Codex bridge 内部错误: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[codex-agent-bridge] {self.address_string()} - {format % args}")

    def _authorized(self) -> bool:
        api_key = getattr(self.server, "api_key", "")  # type: ignore[attr-defined]
        if not api_key:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {api_key}"

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("request body must be a JSON object")
        return data

    def _send_json(self, payload: Mapping[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CodexBridgeServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], config: BridgeConfig, api_key: str):
        super().__init__(server_address, CodexBridgeHandler)
        self.config = config
        self.api_key = api_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local Codex Agent HTTP bridge")
    parser.add_argument("--host", default=os.getenv("CODEX_AGENT_BRIDGE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CODEX_AGENT_BRIDGE_PORT", "8787")))
    parser.add_argument("--api-key", default=os.getenv("CODEX_AGENT_BRIDGE_API_KEY", ""))
    args = parser.parse_args()

    config = config_from_env()
    server = CodexBridgeServer((args.host, args.port), config=config, api_key=args.api_key)
    print(
        f"[codex-agent-bridge] listening on http://{args.host}:{args.port} "
        f"workspace={config.workspace} codex={config.codex_binary}"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
