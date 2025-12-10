import logging
import logging.config
import sys
from pathlib import Path
import os
import platform

from app.core.logging_context import LoggingContextFilter, trace_id_var
from app.core.config import settings
from tradingagents.utils.runtime_paths import get_logs_dir, get_runtime_base_dir

# 🔥 在 Windows 上使用 concurrent-log-handler 避免文件占用问题
_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    try:
        from concurrent_log_handler import ConcurrentRotatingFileHandler
        _USE_CONCURRENT_HANDLER = True
    except ImportError:
        _USE_CONCURRENT_HANDLER = False
        logging.warning("concurrent-log-handler 未安装，在 Windows 上可能遇到日志轮转问题")
else:
    _USE_CONCURRENT_HANDLER = False

try:
    import tomllib as toml_loader  # Python 3.11+
except Exception:
    try:
        import tomli as toml_loader  # Python 3.10 fallback
    except Exception:
        toml_loader = None


def resolve_logging_cfg_path() -> Path:
    """根据环境选择日志配置文件路径（可能不存在）
    优先 docker 配置，其次默认配置。
    """
    profile = os.environ.get("LOGGING_PROFILE", "").lower()
    is_docker_env = os.environ.get("DOCKER", "").lower() in {"1", "true", "yes"} or Path("/.dockerenv").exists()
    cfg_candidate = "config/logging_docker.toml" if profile == "docker" or is_docker_env else "config/logging.toml"
    return Path(cfg_candidate)


class SimpleJsonFormatter(logging.Formatter):
    """Minimal JSON formatter without external deps."""
    def format(self, record: logging.LogRecord) -> str:
        import json
        obj = {
            "time": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "name": record.name,
            "level": record.levelname,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        return json.dumps(obj, ensure_ascii=False)


def _parse_size(size_str: str) -> int:
    """解析大小字符串（如 '10MB'）为字节数"""
    if isinstance(size_str, int):
        return size_str
    if isinstance(size_str, str) and size_str.upper().endswith("MB"):
        try:
            return int(float(size_str[:-2]) * 1024 * 1024)
        except Exception:
            return 10 * 1024 * 1024
    return 10 * 1024 * 1024


def _resolve_logs_dir(dir_value: str | Path) -> Path:
    """将日志目录解析到统一的运行时目录下"""
    base = get_runtime_base_dir(settings.RUNTIME_BASE_DIR)
    dir_path = Path(dir_value)
    if not dir_path.is_absolute():
        dir_path = base / dir_path
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _resolve_log_file(file_value: str | Path, default_dir: Path) -> str:
    """解析日志文件路径，确保位于运行时目录并创建父目录"""
    file_path = Path(file_value)
    if not file_path.is_absolute():
        file_path = default_dir / file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return str(file_path)


def setup_logging(log_level: str = "INFO"):
    """
    设置应用日志配置：
    1) 优先尝试从 config/logging.toml 读取并转化为 dictConfig
    2) 失败或不存在时，回退到内置默认配置
    """
    # 1) 若存在 TOML 配置且可解析，则优先使用
    try:
        cfg_path = resolve_logging_cfg_path()

        if cfg_path.exists() and toml_loader is not None:
            with cfg_path.open("rb") as f:
                toml_data = toml_loader.load(f)

            # 读取基础字段
            logging_root = toml_data.get("logging", {})
            level = logging_root.get("level", log_level)
            fmt_cfg = logging_root.get("format", {})
            fmt_console = fmt_cfg.get(
                "console", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            fmt_file = fmt_cfg.get(
                "file", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            # 确保文本格式包含 trace_id（若未显式包含）
            if "%(trace_id)" not in str(fmt_console):
                fmt_console = str(fmt_console) + " trace=%(trace_id)s"
            if "%(trace_id)" not in str(fmt_file):
                fmt_file = str(fmt_file) + " trace=%(trace_id)s"

            handlers_cfg = logging_root.get("handlers", {})
            file_handler_cfg = handlers_cfg.get("file", {})
            file_dir_cfg = file_handler_cfg.get("directory", "logs")
            file_level = file_handler_cfg.get("level", "DEBUG")
            max_bytes = file_handler_cfg.get("max_size", "10MB")
            # 支持 "10MB" 形式
            if isinstance(max_bytes, str) and max_bytes.upper().endswith("MB"):
                try:
                    max_bytes = int(float(max_bytes[:-2]) * 1024 * 1024)
                except Exception:
                    max_bytes = 10 * 1024 * 1024
            elif not isinstance(max_bytes, int):
                max_bytes = 10 * 1024 * 1024
            backup_count = int(file_handler_cfg.get("backup_count", 5))

            file_dir = _resolve_logs_dir(file_dir_cfg)

            # 从TOML配置读取各个日志文件路径
            main_handler_cfg = handlers_cfg.get("main", {})
            webapi_handler_cfg = handlers_cfg.get("webapi", {})
            worker_handler_cfg = handlers_cfg.get("worker", {})

            # 主日志文件（tradingagents.log）
            main_log = _resolve_log_file(
                main_handler_cfg.get("filename", Path(file_dir) / "tradingagents.log"),
                file_dir,
            )
            main_enabled = main_handler_cfg.get("enabled", True)
            main_level = main_handler_cfg.get("level", "INFO")
            main_max_bytes = _parse_size(main_handler_cfg.get("max_size", "100MB"))
            main_backup_count = int(main_handler_cfg.get("backup_count", 5))

            # WebAPI日志文件
            webapi_log = _resolve_log_file(
                webapi_handler_cfg.get("filename", Path(file_dir) / "webapi.log"),
                file_dir,
            )
            webapi_enabled = webapi_handler_cfg.get("enabled", True)
            webapi_level = webapi_handler_cfg.get("level", "DEBUG")
            webapi_max_bytes = _parse_size(webapi_handler_cfg.get("max_size", "100MB"))
            webapi_backup_count = int(webapi_handler_cfg.get("backup_count", 5))

            # Worker日志文件
            worker_log = _resolve_log_file(
                worker_handler_cfg.get("filename", Path(file_dir) / "worker.log"),
                file_dir,
            )
            worker_enabled = worker_handler_cfg.get("enabled", True)
            worker_level = worker_handler_cfg.get("level", "DEBUG")
            worker_max_bytes = _parse_size(worker_handler_cfg.get("max_size", "100MB"))
            worker_backup_count = int(worker_handler_cfg.get("backup_count", 5))

            # 错误日志文件
            error_handler_cfg = handlers_cfg.get("error", {})
            error_log = _resolve_log_file(
                error_handler_cfg.get("filename", Path(file_dir) / "error.log"),
                file_dir,
            )
            error_enabled = error_handler_cfg.get("enabled", True)
            error_level = error_handler_cfg.get("level", "WARNING")
            error_max_bytes = _parse_size(error_handler_cfg.get("max_size", "100MB"))
            error_backup_count = int(error_handler_cfg.get("backup_count", 5))

            # JSON 开关：保持向后兼容（json/mode 仅控制台）；新增 file_json/file_mode 控制文件 handler
            use_json_console = bool(fmt_cfg.get("json", False)) or str(fmt_cfg.get("mode", "")).lower() == "json"
            use_json_file = (
                bool(fmt_cfg.get("file_json", False))
                or bool(fmt_cfg.get("json_file", False))
                or str(fmt_cfg.get("file_mode", "")).lower() == "json"
            )

            # 构建处理器配置
            handlers_config = {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json_console_fmt" if use_json_console else "console_fmt",
                    "level": level,
                    "filters": ["request_context"],
                    "stream": sys.stdout,
                },
            }

            # 🔥 选择日志处理器类（Windows 使用 ConcurrentRotatingFileHandler）
            handler_class = "concurrent_log_handler.ConcurrentRotatingFileHandler" if _USE_CONCURRENT_HANDLER else "logging.handlers.RotatingFileHandler"

            # 主日志文件（tradingagents.log）
            if main_enabled:
                handlers_config["main_file"] = {
                    "class": handler_class,
                    "formatter": "json_file_fmt" if use_json_file else "file_fmt",
                    "level": main_level,
                    "filename": main_log,
                    "maxBytes": main_max_bytes,
                    "backupCount": main_backup_count,
                    "encoding": "utf-8",
                    "filters": ["request_context"],
                }

            # WebAPI日志文件
            if webapi_enabled:
                handlers_config["file"] = {
                    "class": handler_class,
                    "formatter": "json_file_fmt" if use_json_file else "file_fmt",
                    "level": webapi_level,
                    "filename": webapi_log,
                    "maxBytes": webapi_max_bytes,
                    "backupCount": webapi_backup_count,
                    "encoding": "utf-8",
                    "filters": ["request_context"],
                }

            # Worker日志文件
            if worker_enabled:
                handlers_config["worker_file"] = {
                    "class": handler_class,
                    "formatter": "json_file_fmt" if use_json_file else "file_fmt",
                    "level": worker_level,
                    "filename": worker_log,
                    "maxBytes": worker_max_bytes,
                    "backupCount": worker_backup_count,
                    "encoding": "utf-8",
                    "filters": ["request_context"],
                }

            # 添加错误日志处理器（如果启用）
            if error_enabled:
                handlers_config["error_file"] = {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "json_file_fmt" if use_json_file else "file_fmt",
                    "level": error_level,
                    "filename": error_log,
                    "maxBytes": error_max_bytes,
                    "backupCount": error_backup_count,
                    "encoding": "utf-8",
                    "filters": ["request_context"],
                }

            # 构建logger handlers列表
            main_handlers = ["console"]
            if main_enabled:
                main_handlers.append("main_file")
            if error_enabled:
                main_handlers.append("error_file")

            webapi_handlers = ["console"]
            if webapi_enabled:
                webapi_handlers.append("file")
            if main_enabled:
                webapi_handlers.append("main_file")
            if error_enabled:
                webapi_handlers.append("error_file")

            worker_handlers = ["console"]
            if worker_enabled:
                worker_handlers.append("worker_file")
            if main_enabled:
                worker_handlers.append("main_file")
            if error_enabled:
                worker_handlers.append("error_file")

            logging_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "filters": {
                    "request_context": {"()": "app.core.logging_context.LoggingContextFilter"}
                },
                "formatters": {
                    "console_fmt": {
                        "format": fmt_console,
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "file_fmt": {
                        "format": fmt_file,
                        "datefmt": "%Y-%m-%d %H:%M:%S",
                    },
                    "json_console_fmt": {
                        "()": "app.core.logging_config.SimpleJsonFormatter"
                    },
                    "json_file_fmt": {
                        "()": "app.core.logging_config.SimpleJsonFormatter"
                    },
                },
                "handlers": handlers_config,
                "loggers": {
                    "tradingagents": {
                        "level": "INFO",
                        "handlers": main_handlers,
                        "propagate": False
                    },
                    "webapi": {
                        "level": "INFO",
                        "handlers": webapi_handlers,
                        "propagate": False
                    },
                    "worker": {
                        "level": "DEBUG",
                        "handlers": worker_handlers,
                        "propagate": False
                    },
                    "uvicorn": {
                        "level": "INFO",
                        "handlers": webapi_handlers,
                        "propagate": False
                    },
                    "fastapi": {
                        "level": "INFO",
                        "handlers": webapi_handlers,
                        "propagate": False
                    },
                    "app": {
                        "level": "INFO",
                        "handlers": main_handlers,
                        "propagate": False
                    },
                },
                "root": {"level": level, "handlers": main_handlers},
            }

            logging.config.dictConfig(logging_config)
            logging.getLogger("webapi").info(f"Logging configured from {cfg_path}")
            return
    except Exception as e:
        # TOML 存在但加载失败，回退到默认配置
        logging.getLogger("webapi").warning(f"Failed to load logging.toml, fallback to defaults: {e}")

    # 2) 默认内置配置（与原先一致，但目录收敛到 runtime）
    log_dir = get_logs_dir(settings.RUNTIME_BASE_DIR)

    # 🔥 选择日志处理器类（Windows 使用 ConcurrentRotatingFileHandler）
    handler_class = "concurrent_log_handler.ConcurrentRotatingFileHandler" if _USE_CONCURRENT_HANDLER else "logging.handlers.RotatingFileHandler"

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"request_context": {"()": "app.core.logging_context.LoggingContextFilter"}},
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s trace=%(trace_id)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s trace=%(trace_id)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": log_level,
                "filters": ["request_context"],
                "stream": sys.stdout,
            },
            "file": {
                "class": handler_class,
                "formatter": "detailed",
                "level": "DEBUG",
                "filters": ["request_context"],
                "filename": str(log_dir / "webapi.log"),
                "maxBytes": 10485760,
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "worker_file": {
                "class": handler_class,
                "formatter": "detailed",
                "level": "DEBUG",
                "filters": ["request_context"],
                "filename": str(log_dir / "worker.log"),
                "maxBytes": 10485760,
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": handler_class,
                "formatter": "detailed",
                "level": "WARNING",
                "filters": ["request_context"],
                "filename": str(log_dir / "error.log"),
                "maxBytes": 10485760,
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "webapi": {"level": "INFO", "handlers": ["console", "file", "error_file"], "propagate": True},
            "worker": {"level": "DEBUG", "handlers": ["console", "worker_file", "error_file"], "propagate": False},
            "uvicorn": {"level": "INFO", "handlers": ["console", "file", "error_file"], "propagate": False},
            "fastapi": {"level": "INFO", "handlers": ["console", "file", "error_file"], "propagate": False},
        },
        "root": {"level": log_level, "handlers": ["console"]},
    }

    logging.config.dictConfig(logging_config)
    logging.getLogger("webapi").info("Logging configured successfully (built-in)")