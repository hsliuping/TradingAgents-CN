"""
进度日志处理器
监控TradingAgents的日志输出，自动更新进度跟踪器
"""

import logging
import re
import threading
from typing import Dict, Optional
from .tracker import RedisProgressTracker

logger = logging.getLogger("app.services.progress_log_handler")


class ProgressLogHandler(logging.Handler):
    """进度日志处理器，监控TradingAgents日志并更新进度"""

    def __init__(self):
        super().__init__()
        self._trackers: Dict[str, RedisProgressTracker] = {}
        self._lock = threading.Lock()

        # 日志模式匹配
        self.progress_patterns = {
            # 基础阶段
            r"验证.*股票代码|检查.*数据源": "📋 准备阶段",
            r"检查.*API.*密钥|环境.*配置": "🔧 环境检查",
            r"预估.*成本|成本.*估算": "💰 成本估算",
            r"配置.*参数|参数.*设置": "⚙️ 参数设置",
            r"初始化.*引擎|启动.*引擎": "🚀 启动引擎",

            # 分析师阶段
            r"市场分析师.*开始|开始.*市场分析|市场.*数据.*分析": "📊 市场分析师正在分析",
            r"基本面分析师.*开始|开始.*基本面分析|财务.*数据.*分析": "💼 基本面分析师正在分析",
            r"新闻分析师.*开始|开始.*新闻分析|新闻.*数据.*分析": "📰 新闻分析师正在分析",
            r"社交媒体分析师.*开始|开始.*社交媒体分析|情绪.*分析": "💬 社交媒体分析师正在分析",

            # 研究团队阶段
            r"看涨研究员|多头研究员|bull.*researcher|积极证据研究员": "🐂 积极证据研究员构建论据",
            r"看跌研究员|空头研究员|bear.*researcher|谨慎证据研究员": "🐻 谨慎证据研究员识别风险",
            r"研究.*辩论|辩论.*开始|debate.*start|多情景研究": "🎯 多情景研究进行中",
            r"研究经理|research.*manager|研究整合员": "👔 研究整合员汇总",

            # 研究整合阶段
            r"交易员.*决策|trader.*decision|制定.*交易策略|研究整合员.*汇总|研究整合.*意见": "🧩 研究整合员汇总",

            # 风险管理阶段
            r"激进.*风险|risky.*risk|高弹性情景": "🔥 高弹性情景研究",
            r"保守.*风险|conservative.*risk|防御情景": "🛡️ 防御情景研究",
            r"中性.*风险|neutral.*risk|基准情景": "⚖️ 基准情景研究",
            r"风险经理|risk.*manager|风险评估师": "🎯 风险评估师形成结论",

            # 最终阶段
            r"信号处理|signal.*process|结果处理": "📡 结果处理",
            r"生成.*报告|report.*generat": "📊 生成研究报告",
            r"分析.*完成|analysis.*complet": "✅ 研究完成",
        }

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

        # 检查是否包含进度相关的关键词
        progress_keywords = [
            "开始", "完成", "分析", "处理", "执行", "生成",
            "start", "complete", "analysis", "process", "execute", "generate"
        ]

        if not any(keyword in message_lower for keyword in progress_keywords):
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

            # 将处理器添加到相关的日志记录器
            loggers_to_monitor = [
                "agents",
                "tradingagents",
                "agents.analysts",
                "agents.researchers",
                "agents.traders",
                "agents.managers",
                "agents.risk_mgmt",
            ]

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

