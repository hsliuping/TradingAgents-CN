"""
进度日志处理器
监控TradingAgents的日志输出，自动更新进度跟踪器
"""

import logging
import re
import threading
from typing import Dict, Optional
from .tracker import RedisProgressTracker
from .log_contract import MONITORED_LOGGERS, PROGRESS_KEYWORDS, PROGRESS_LOG_PATTERNS

logger = logging.getLogger(__name__)


class ProgressLogHandler(logging.Handler):
    """进度日志处理器，监控TradingAgents日志并更新进度"""

    def __init__(self):
        super().__init__()
        self._trackers: Dict[str, RedisProgressTracker] = {}
        self._lock = threading.Lock()

        # 日志模式匹配（⚠️ 显式契约表：改日志文案必须同步改 log_contract.PROGRESS_LOG_PATTERNS）
        self.progress_patterns = PROGRESS_LOG_PATTERNS

        logger.info("📊 [进度日志] 日志处理器初始化完成")

    def register_tracker(self, task_id: str, tracker: RedisProgressTracker):
        """注册进度跟踪器"""
        with self._lock:
            self._trackers[task_id] = tracker
            logger.info(f"📊 [进度日志] 注册跟踪器: {task_id}")

    def unregister_tracker(self, task_id: str):
        """注销进度跟踪器"""
        with self._lock:
            if task_id in self._trackers:
                del self._trackers[task_id]
                logger.info(f"📊 [进度日志] 注销跟踪器: {task_id}")

    def emit(self, record):
        """处理日志记录"""
        try:
            message = record.getMessage()

            # 检查是否是我们关心的日志消息
            progress_message = self._extract_progress_message(message)
            if not progress_message:
                return

            # 查找匹配的跟踪器（减少锁持有时间）
            trackers_copy = {}
            with self._lock:
                trackers_copy = self._trackers.copy()

            # 在锁外面处理跟踪器更新
            for task_id, tracker in trackers_copy.items():
                try:
                    # 检查跟踪器状态
                    if hasattr(tracker, 'progress_data') and tracker.progress_data.get('status') == 'running':
                        tracker.update_progress(progress_message)
                        logger.debug(f"📊 [进度日志] 更新进度: {task_id} -> {progress_message}")
                        break  # 只更新第一个匹配的跟踪器
                except Exception as e:
                    logger.warning(f"📊 [进度日志] 更新失败: {task_id} - {e}")

        except Exception as e:
            # 不要让日志处理器的错误影响主程序
            logger.error(f"📊 [进度日志] 日志处理错误: {e}")

    def _extract_progress_message(self, message: str) -> Optional[str]:
        """从日志消息中提取进度信息"""
        message_lower = message.lower()

        # 检查是否包含进度相关的关键词（契约表 log_contract.PROGRESS_KEYWORDS）
        if not any(keyword in message_lower for keyword in PROGRESS_KEYWORDS):
            return None

        # 匹配具体的进度模式
        for pattern, progress_msg in self.progress_patterns.items():
            if re.search(pattern, message_lower):
                return progress_msg

        return None

    def _extract_stock_symbol(self, message: str) -> Optional[str]:
        """从消息中提取股票代码"""
        # 匹配常见的股票代码格式
        patterns = [
            r'\b(\d{6})\b',  # 6位数字（A股）
            r'\b([A-Z]{1,5})\b',  # 1-5位大写字母（美股）
            r'\b(\d{4,5}\.HK)\b',  # 港股格式
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)

        return None


# 全局日志处理器实例
_progress_log_handler = None
_handler_lock = threading.Lock()


def get_progress_log_handler() -> ProgressLogHandler:
    """获取全局进度日志处理器实例"""
    global _progress_log_handler

    with _handler_lock:
        if _progress_log_handler is None:
            _progress_log_handler = ProgressLogHandler()

            # 将处理器添加到相关的日志记录器（契约表 log_contract.MONITORED_LOGGERS）
            loggers_to_monitor = list(MONITORED_LOGGERS)

            for logger_name in loggers_to_monitor:
                target_logger = logging.getLogger(logger_name)
                target_logger.addHandler(_progress_log_handler)
                target_logger.setLevel(logging.INFO)

            logger.info(f"📊 [进度日志] 已注册到 {len(loggers_to_monitor)} 个日志记录器")

    return _progress_log_handler


def register_analysis_tracker(task_id: str, tracker: RedisProgressTracker):
    """注册分析跟踪器到日志监控"""
    handler = get_progress_log_handler()
    handler.register_tracker(task_id, tracker)


def unregister_analysis_tracker(task_id: str):
    """从日志监控中注销分析跟踪器"""
    handler = get_progress_log_handler()
    handler.unregister_tracker(task_id)

