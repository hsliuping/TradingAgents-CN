"""
MCP 调用错误语义（P5：失败 vs 空数据区分）

历史教训：tdx-mcp 曾遇 DNS 解析失败，当时的修复把"请求失败"当成"空数据"
处理，业务层大量回退导致策略语义漂移（见
docs/05-design/v4.0/data-architecture-problems-and-optimization.md §6）。

约定：
  - 请求失败（DNS / 超时 / HTTP 非 200 / 连接异常 / 协议错误）→ 打日志标
    + 上抛 McpTransportError（携带结构化 error_code），绝不伪装成空数据；
  - 请求成功但结果为空 → 正常返回"空数据"结果，不报错，业务层只在此时
    按"无数据"处理（回退与否走既定降级策略）。
"""

import re
import socket
from typing import Any, Dict, Iterator, Optional


class McpErrorCodes:
    """MCP 调用失败的结构化错误码（transport 层）"""

    DNS_FAILURE = "dns_failure"          # DNS 解析失败
    TIMEOUT = "timeout"                  # 请求超时
    HTTP_ERROR = "http_error"            # HTTP 非 2xx
    CONNECTION_ERROR = "connection_error"  # 连接失败/被拒/中断
    PROTOCOL_ERROR = "protocol_error"    # MCP 协议层错误（JSON-RPC error）
    TOOL_ERROR = "tool_error"            # 工具执行成功返回，但 isError=True
    UNKNOWN = "unknown_error"            # 其他未识别失败


class McpCallError(Exception):
    """MCP 调用失败基类（带结构化 error_code，绝不等价于"空数据"）"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        server: Optional[str] = None,
        tool: Optional[str] = None,
    ):
        self.error_code = error_code
        self.server = server
        self.tool = tool
        self.detail = message
        super().__init__(
            f"[MCP][CALL_ERROR][{error_code}] server={server} tool={tool}: {message}"
        )


class McpTransportError(McpCallError):
    """MCP 传输层请求失败（DNS/超时/HTTP 非 200/连接异常）。

    与"请求成功但无数据"严格区分：业务层不得把本异常当空数据吞掉，
    应按既定降级策略处理（试下一数据源或上抛）。
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        server: Optional[str] = None,
        tool: Optional[str] = None,
    ):
        super().__init__(error_code, message, server=server, tool=tool)


# --------------------------------------------------------------------------
# 异常链遍历 & 错误码分类
# --------------------------------------------------------------------------

def _iter_exc_chain(exc: BaseException) -> Iterator[BaseException]:
    """深度遍历异常链（含 __cause__/__context__ 与 ExceptionGroup）"""
    seen = set()
    stack = [exc]
    while stack:
        e = stack.pop()
        if id(e) in seen:
            continue
        seen.add(id(e))
        yield e
        if isinstance(e, BaseExceptionGroup):
            stack.extend(e.exceptions)
        if e.__cause__ is not None:
            stack.append(e.__cause__)
        if e.__context__ is not None:
            stack.append(e.__context__)


_DNS_MESSAGE_PATTERNS = (
    "getaddrinfo failed",
    "name resolution",
    "nodename nor servname",
    "name or service not known",
    "temporary failure in name resolution",
    "dns",
)

_HTTP_STATUS_RE = re.compile(r"(?:HTTP[^0-9]{0,10}|status(?: code)?[^0-9]{0,5})(\d{3})", re.I)


def _extract_http_status(e: BaseException) -> Optional[int]:
    """从异常上提取 HTTP 状态码（httpx/aiohttp/urllib 风格）"""
    resp = getattr(e, "response", None)
    status = getattr(resp, "status_code", None)
    if status is None:
        status = getattr(e, "status", None)
    if isinstance(status, int):
        return status
    m = _HTTP_STATUS_RE.search(str(e))
    if m:
        return int(m.group(1))
    return None


def classify_transport_error(exc: BaseException) -> str:
    """把底层异常归类为 McpErrorCodes 中的错误码（沿异常链深度匹配）"""
    for e in _iter_exc_chain(exc):
        # DNS 失败优先于 OSError（socket.gaierror 是 OSError 子类）
        if isinstance(e, socket.gaierror):
            return McpErrorCodes.DNS_FAILURE
        # Python 3.11: asyncio.TimeoutError / concurrent.futures.TimeoutError
        # 均为 TimeoutError 别名/子类
        if isinstance(e, TimeoutError):
            return McpErrorCodes.TIMEOUT
        status = _extract_http_status(e)
        if status is not None and not (200 <= status < 300):
            return McpErrorCodes.HTTP_ERROR
        msg = str(e).lower()
        if any(p in msg for p in _DNS_MESSAGE_PATTERNS):
            return McpErrorCodes.DNS_FAILURE
        if isinstance(e, ConnectionError):
            return McpErrorCodes.CONNECTION_ERROR
        if "McpError" in type(e).__name__:
            return McpErrorCodes.PROTOCOL_ERROR
        if isinstance(e, OSError):
            return McpErrorCodes.CONNECTION_ERROR
    return McpErrorCodes.UNKNOWN


def to_transport_error(
    exc: BaseException,
    *,
    server: Optional[str] = None,
    tool: Optional[str] = None,
) -> McpTransportError:
    """把任意底层异常转换为带错误码的 McpTransportError"""
    code = classify_transport_error(exc)
    return McpTransportError(
        code,
        f"{type(exc).__name__}: {exc}",
        server=server,
        tool=tool,
    )


def call_error_from_exception(
    exc: BaseException,
    *,
    server: Optional[str] = None,
    tool: Optional[str] = None,
) -> Dict[str, Any]:
    """把异常转为结构化错误摘要（用于不抛异常的接口，如连接测试）"""
    if isinstance(exc, McpCallError):
        code = exc.error_code
    else:
        code = classify_transport_error(exc)
    return {"error_code": code, "error": str(exc), "server": server, "tool": tool}
