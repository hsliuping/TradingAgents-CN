import logging
import logging.config
import sys
from pathlib import Path
import os
import platform

from app.core.logging_context import LoggingContextFilter, trace_id_var

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

def setup_logging(log_level: str = "INFO"):
    """
    设置应用日志配置：
    1) 优先尝试从 config/logging.toml 读取并转化为 dictConfig
    2) 失败或不存在时，回退到内置默认配置
    """
    # 1) 若存在 TOML 配置且可解析，则优先使用
    try:
        cfg_path = resolve_logging_cfg_path()
        print(f"🔍 [setup_logging] 日志配置文件路径: {cfg_path}")
        print(f"🔍 [setup_logging] 配置文件存在: {cfg_path.exists()}")
        print(f"🔍 [setup_logging] TOML加载器可用: {toml_loader is not None}")

        if cfg_path.exists() and toml_loader is not None:
            with cfg_path.open("rb") as f:
                toml_data = toml_loader.load(f)

            print(f"🔍 [setup_logging] 成功加载TOML配置")

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
            file_dir = file_handler_cfg.get("directory", "./logs")
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

            Path(file_dir).mkdir(parents=True, exist_ok=True)

            # 从TOML配置读取各个日志文件路径
            main_handler_cfg = handlers_cfg.get("main", {})
            webapi_handler_cfg = handlers_cfg.get("webapi", {})
            worker_handler_cfg = handlers_cfg.get("worker", {})

            print(f"🔍 [setup_logging] handlers配置: {list(handlers_cfg.keys())}")
            print(f"🔍 [setup_logging] main_handler_cfg: {main_handler_cfg}")
            print(f"🔍 [setup_logging] webapi_handler_cfg: {webapi_handler_cfg}")
            print(f"🔍 [setup_logging] worker_handler_cfg: {worker_handler_cfg}")

            # 主日志文件（tradingagents.log）
            main_log = main_handler_cfg.get("filename", str(Path(file_dir) / "tradingagents.log"))
            main_enabled = main_handler_cfg.get("enabled", True)
            main_level = main_handler_cfg.get("level", "INFO")
            main_max_bytes = _parse_size(main_handler_cfg.get("max_size", "100MB"))
            main_backup_count = int(main_handler_cfg.get("backup_count", 5))

            print(f"🔍 [setup_logging] 主日志文件配置:")
            print(f"  - 文件路径: {main_log}")
            print(f"  - 是否启用: {main_enabled}")
            print(f"  - 日志级别: {main_level}")
            print(f"  - 最大大小: {main_max_bytes} bytes")
            print(f"  - 备份数量: {main_backup_count}")

            # WebAPI日志文件
            webapi_log = webapi_handler_cfg.get("filename", str(Path(file_dir) / "webapi.log"))
            webapi_enabled = webapi_handler_cfg.get("enabled", True)
            webapi_level = webapi_handler_cfg.get("level", "DEBUG")
            webapi_max_bytes = _parse_size(webapi_handler_cfg.get("max_size", "100MB"))
            webapi_backup_count = int(webapi_handler_cfg.get("backup_count", 5))

            print(f"🔍 [setup_logging] WebAPI日志文件: {webapi_log}, 启用: {webapi_enabled}")

            # Worker日志文件
            worker_log = worker_handler_cfg.get("filename", str(Path(file_dir) / "worker.log"))
            worker_enabled = worker_handler_cfg.get("enabled", True)
            worker_level = worker_handler_cfg.get("level", "DEBUG")
            worker_max_bytes = _parse_size(worker_handler_cfg.get("max_size", "100MB"))
            worker_backup_count = int(worker_handler_cfg.get("backup_count", 5))

            print(f"🔍 [setup_logging] Worker日志文件: {worker_log}, 启用: {worker_enabled}")

            # 错误日志文件
            error_handler_cfg = handlers_cfg.get("error", {})
            error_dir = error_handler_cfg.get("directory", file_dir)
            error_filename = error_handler_cfg.get("filename", "error.log")
            # 如果 filename 是相对路径，则与 directory 组合
            if not Path(error_filename).is_absolute():
                error_log = str(Path(error_dir) / error_filename)
            else:
                error_log = error_filename
            error_enabled = error_handler_cfg.get("enabled", True)
            error_level = error_handler_cfg.get("level", "WARNING")
            error_max_bytes = _parse_size(error_handler_cfg.get("max_size", "100MB"))
            error_backup_count = int(error_handler_cfg.get("backup_count", 5))

            print(f"🔍 [setup_logging] 错误日志文件配置:")
            print(f"  - 文件路径: {error_log}")
            print(f"  - 是否启用: {error_enabled}")
            print(f"  - 日志级别: {error_level}")

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

            print(f"🔍 [setup_logging] 开始构建handlers配置")

            # 🔥 选择日志处理器类（Windows 使用 ConcurrentRotatingFileHandler）
            handler_class = "concurrent_log_handler.ConcurrentRotatingFileHandler" if _USE_CONCURRENT_HANDLER else "logging.handlers.RotatingFileHandler"

            # 主日志文件（tradingagents.log）
            if main_enabled:
                print(f"✅ [setup_logging] 添加 main_file handler: {main_log} (使用 {handler_class})")
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
            else:
                print(f"⚠️ [setup_logging] main_file handler 未启用")

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
                    "class": handler_class,  # 🔥 使用与主日志相同的处理器类
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

            print(f"🔍 [setup_logging] main_handlers: {main_handlers}")

            webapi_handlers = ["console"]
            if webapi_enabled:
                webapi_handlers.append("file")
            if main_enabled:
                webapi_handlers.append("main_file")
            if error_enabled:
                webapi_handlers.append("error_file")

            print(f"🔍 [setup_logging] webapi_handlers: {webapi_handlers}")

            worker_handlers = ["console"]
            if worker_enabled:
                worker_handlers.append("worker_file")
            if main_enabled:
                worker_handlers.append("main_file")
            if error_enabled:
                worker_handlers.append("error_file")

            print(f"🔍 [setup_logging] worker_handlers: {worker_handlers}")

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

            print(f"🔍 [setup_logging] 最终handlers配置: {list(handlers_config.keys())}")
            print(f"🔍 [setup_logging] 开始应用 dictConfig")

            logging.config.dictConfig(logging_config)

            print(f"✅ [setup_logging] dictConfig 应用成功")

            logging.getLogger("webapi").info(f"Logging configured from {cfg_path}")

            # 测试主日志文件是否可写
            if main_enabled:
                test_logger = logging.getLogger("tradingagents")
                test_logger.info(f"🔍 测试主日志文件写入: {main_log}")
                print(f"🔍 [setup_logging] 已向 tradingagents logger 写入测试日志")

            return
    except Exception as e:
        # TOML 存在但加载失败，回退到默认配置
        logging.getLogger("webapi").warning(f"Failed to load logging.toml, fallback to defaults: {e}")

    # 2) 默认内置配置（与原先一致）
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

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
                "filename": "logs/webapi.log",
                "maxBytes": 10485760,
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "worker_file": {
                "class": handler_class,
                "formatter": "detailed",
                "level": "DEBUG",
                "filters": ["request_context"],
                "filename": "logs/worker.log",
                "maxBytes": 10485760,
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": handler_class,
                "formatter": "detailed",
                "level": "WARNING",
                "filters": ["request_context"],
                "filename": "logs/error.log",
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