#!/usr/bin/env python3
"""
统一日志管理器（已降级为无副作用便捷封装，见 docs/05-design/v4.0/logging-governance.md §5.3）

权威日志配置：
- app 进程：app/core/logging_config.py 的 dictConfig
- CLI / 独立进程入口：core/utils/logging_setup.py 的共享初始化函数

历史问题：本模块曾自配 handler 并 clear root logger 全部 handler，与 app 侧 dictConfig
互相覆盖、最终形态取决于 import 顺序。治理后本模块**不再自配任何 handler、不再触碰
root handlers**，仅保留 get_logger() 便捷函数、配置读取（供诊断展示）与 log_* 事件方法。
存量 import 不动，行为收敛到权威配置。
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import toml

# 注意：这里不能导入自己，会造成循环导入
# 在日志系统初始化前，使用标准库自举日志器，避免未定义引用
_bootstrap_logger = logging.getLogger("tradingagents.logging_manager")


class TradingAgentsLogger:
    """TradingAgents 日志管理器（无副作用：不配置 handler）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._load_default_config()
        self.loggers: Dict[str, logging.Logger] = {}
        self._setup_logging()

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认日志配置"""
        # 尝试从配置文件加载
        config = self._load_config_file()
        if config:
            return config

        # 从环境变量获取配置
        log_level = os.getenv('TRADINGAGENTS_LOG_LEVEL', 'INFO').upper()
        log_dir = os.getenv('TRADINGAGENTS_LOG_DIR', './logs')

        return {
            'level': log_level,
            'format': {
                'console': '%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
                'file': '%(asctime)s | %(name)-20s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
                'structured': 'json'
            },
            'handlers': {
                'console': {
                    'enabled': True,
                    'colored': True,
                    'level': log_level
                },
                'file': {
                    'enabled': True,
                    'level': 'DEBUG',
                    'max_size': '10MB',
                    'backup_count': 5,
                    'directory': log_dir
                },
                'error': {
                    'enabled': True,
                    'level': 'WARNING',  # 只记录WARNING及以上级别
                    'max_size': '10MB',
                    'backup_count': 5,
                    'directory': log_dir,
                    'filename': 'error.log'
                },
                'structured': {
                    'enabled': False,  # 默认关闭，可通过环境变量启用
                    'level': 'INFO',
                    'directory': log_dir
                }
            },
            'loggers': {
                'tradingagents': {'level': log_level},
                'web': {'level': log_level},
                'streamlit': {'level': 'WARNING'},  # Streamlit日志较多，设为WARNING
                'urllib3': {'level': 'WARNING'},    # HTTP请求日志较多
                'requests': {'level': 'WARNING'},
                'matplotlib': {'level': 'WARNING'}
            },
            'docker': {
                'enabled': os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true',
                'stdout_only': True  # Docker环境只输出到stdout
            }
        }

    def _load_config_file(self) -> Optional[Dict[str, Any]]:
        """从配置文件加载日志配置"""
        # 确定配置文件路径
        config_paths = [
            'config/logging_docker.toml' if os.getenv('DOCKER_CONTAINER') == 'true' else None,
            'config/logging.toml',
            './logging.toml'
        ]

        for config_path in config_paths:
            if config_path and Path(config_path).exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = toml.load(f)

                    # 转换配置格式
                    return self._convert_toml_config(config_data)
                except Exception as e:
                    _bootstrap_logger.warning(f"警告: 无法加载配置文件 {config_path}: {e}")
                    continue

        return None

    def _convert_toml_config(self, toml_config: Dict[str, Any]) -> Dict[str, Any]:
        """将TOML配置转换为内部配置格式"""
        logging_config = toml_config.get('logging', {})

        # 检查Docker环境
        is_docker = (
            os.getenv('DOCKER_CONTAINER') == 'true' or
            logging_config.get('docker', {}).get('enabled', False)
        )

        return {
            'level': logging_config.get('level', 'INFO'),
            'format': logging_config.get('format', {}),
            'handlers': logging_config.get('handlers', {}),
            'loggers': logging_config.get('loggers', {}),
            'docker': {
                'enabled': is_docker,
                'stdout_only': logging_config.get('docker', {}).get('stdout_only', True)
            },
            'performance': logging_config.get('performance', {}),
            'security': logging_config.get('security', {}),
            'business': logging_config.get('business', {})
        }

    def _setup_logging(self):
        """降级为无副作用初始化（日志治理 §5.3）

        只确保日志目录存在、按配置设置第三方 logger 级别；
        ❌ 不再自配 handler、❌ 不再 clear root handlers（那是权威配置的职责）。
        """
        handlers_cfg = self.config.get('handlers', {})
        file_cfg = handlers_cfg.get('file', {})
        if file_cfg.get('enabled', False):
            log_dir = Path(file_cfg.get('directory', './logs'))
            log_dir.mkdir(parents=True, exist_ok=True)

        # 配置特定日志器（仅级别，不涉及 handler）
        self._configure_specific_loggers()

    def _configure_specific_loggers(self):
        """配置特定的日志器（仅 setLevel）"""
        for logger_name, logger_config in self.config.get('loggers', {}).items():
            level_name = logger_config.get('level') if isinstance(logger_config, dict) else None
            if not level_name:
                continue
            logging.getLogger(logger_name).setLevel(getattr(logging, level_name, logging.INFO))

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]

    def log_analysis_start(self, logger: logging.Logger, stock_symbol: str, analysis_type: str, session_id: str):
        """记录分析开始"""
        logger.info(
            f"🚀 开始分析 - 股票: {stock_symbol}, 类型: {analysis_type}",
            extra={
                'stock_symbol': stock_symbol,
                'analysis_type': analysis_type,
                'session_id': session_id,
                'event_type': 'analysis_start',
                'timestamp': datetime.now().isoformat()
            }
        )

    def log_analysis_complete(self, logger: logging.Logger, stock_symbol: str, analysis_type: str,
                            session_id: str, duration: float, cost: float = 0):
        """记录分析完成"""
        logger.info(
            f"✅ 分析完成 - 股票: {stock_symbol}, 耗时: {duration:.2f}s, 成本: ¥{cost:.4f}",
            extra={
                'stock_symbol': stock_symbol,
                'analysis_type': analysis_type,
                'session_id': session_id,
                'duration': duration,
                'cost': cost,
                'event_type': 'analysis_complete',
                'timestamp': datetime.now().isoformat()
            }
        )

    def log_module_start(self, logger: logging.Logger, module_name: str, stock_symbol: str,
                        session_id: str, **extra_data):
        """记录模块开始分析"""
        logger.info(
            f"📊 [模块开始] {module_name} - 股票: {stock_symbol}",
            extra={
                'module_name': module_name,
                'stock_symbol': stock_symbol,
                'session_id': session_id,
                'event_type': 'module_start',
                'timestamp': datetime.now().isoformat(),
                **extra_data
            }
        )

    def log_module_complete(self, logger: logging.Logger, module_name: str, stock_symbol: str,
                           session_id: str, duration: float, success: bool = True,
                           result_length: int = 0, **extra_data):
        """记录模块完成分析"""
        status = "✅ 成功" if success else "❌ 失败"
        logger.info(
            f"📊 [模块完成] {module_name} - {status} - 股票: {stock_symbol}, 耗时: {duration:.2f}s",
            extra={
                'module_name': module_name,
                'stock_symbol': stock_symbol,
                'session_id': session_id,
                'duration': duration,
                'success': success,
                'result_length': result_length,
                'event_type': 'module_complete',
                'timestamp': datetime.now().isoformat(),
                **extra_data
            }
        )

    def log_module_error(self, logger: logging.Logger, module_name: str, stock_symbol: str,
                        session_id: str, duration: float, error: str, **extra_data):
        """记录模块分析错误"""
        logger.error(
            f"❌ [模块错误] {module_name} - 股票: {stock_symbol}, 耗时: {duration:.2f}s, 错误: {error}",
            extra={
                'module_name': module_name,
                'stock_symbol': stock_symbol,
                'session_id': session_id,
                'duration': duration,
                'error': error,
                'event_type': 'module_error',
                'timestamp': datetime.now().isoformat(),
                **extra_data
            },
            exc_info=True
        )

    def log_token_usage(self, logger: logging.Logger, provider: str, model: str,
                       input_tokens: int, output_tokens: int, cost: float, session_id: str):
        """记录Token使用"""
        logger.info(
            f"📊 Token使用 - {provider}/{model}: 输入={input_tokens}, 输出={output_tokens}, 成本=¥{cost:.6f}",
            extra={
                'provider': provider,
                'model': model,
                'tokens': {'input': input_tokens, 'output': output_tokens},
                'cost': cost,
                'session_id': session_id,
                'event_type': 'token_usage'
            }
        )


# 全局日志管理器实例
_logger_manager: Optional[TradingAgentsLogger] = None


def get_logger_manager() -> TradingAgentsLogger:
    """获取全局日志管理器实例"""
    global _logger_manager
    if _logger_manager is None:
        _logger_manager = TradingAgentsLogger()
    return _logger_manager


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器（便捷函数）"""
    return get_logger_manager().get_logger(name)


def setup_logging(config: Optional[Dict[str, Any]] = None):
    """设置项目日志系统（便捷函数，降级后不配置 handler，见类文档）"""
    global _logger_manager
    _logger_manager = TradingAgentsLogger(config)
    return _logger_manager
