"""共享的最简日志初始化（日志治理 §5.3，见 docs/05-design/v4.0/logging-governance.md）。

用途：CLI 入口 / 独立脚本进程的统一日志初始化，替代散落的 `logging.basicConfig`。
app 进程的权威配置仍是 `app/core/logging_config.py` 的 dictConfig，本模块只服务
非 app 进程的入口（core.mcp、cli 工具、demo 入口等）。

约定：
- 一律通过本函数配置，❌ 禁止在业务代码里裸调 `logging.basicConfig` 或直接操根 logger handlers
- 幂等：同进程重复调用不会叠加 handler（除非 force=True）
"""
from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

_DEFAULT_FMT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_cli_logging(
    level: str = "INFO",
    *,
    console: bool = True,
    log_file: str | None = None,
    fmt: str | None = None,
    datefmt: str | None = None,
    force: bool = False,
) -> None:
    """最简 console（+ 可选文件）日志配置。

    Args:
        level: 根日志级别
        console: 是否输出到 stdout（Rich/交互式 TUI 可关掉保持界面清爽）
        log_file: 可选日志文件（10MB x 5 轮转，与 config/logging.toml 口径一致）
        fmt/datefmt: 自定义格式
        force: 强制重新配置（覆盖既有 handler）
    """
    global _configured
    if _configured and not force:
        return
    root = logging.getLogger()
    if root.handlers and not force:
        # 已有权威配置（如 app dictConfig）在先，不再叠加
        return

    fmt = fmt or _DEFAULT_FMT
    datefmt = datefmt or _DEFAULT_DATEFMT

    handlers: dict = {}
    active: list[str] = []
    if console:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": sys.stdout,
        }
        active.append("console")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(log_path),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        }
        active.append("file")
    if not active:
        return

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": fmt, "datefmt": datefmt}},
            "handlers": handlers,
            "root": {"level": level, "handlers": active},
        }
    )
    _configured = True
