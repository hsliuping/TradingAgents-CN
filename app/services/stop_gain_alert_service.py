# 止盈提醒服务
# 参考止损提醒实现，支持自动提取持仓分析止盈线，定时扫描并推送通知

import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from app.models.notification import NotificationCreate
from app.services.favorites_service import FavoritesService
from app.services.notifications_service import get_notifications_service

logger = logging.getLogger(__name__)


class StopGainAlertService:
    def __init__(self, scan_interval_minutes=10):
        self.scan_interval_minutes = scan_interval_minutes
        self.scheduler = BackgroundScheduler()
        self.favorites_service = FavoritesService()
        self._job = None
        self._loop = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """由 main 在 lifespan 中调用，用于在调度器线程中安全执行异步通知。"""
        self._loop = loop

    def start(self):
        if not self._job:
            self._job = self.scheduler.add_job(self.run_once, 'interval', minutes=self.scan_interval_minutes)
            self.scheduler.start()
            logger.info(f"止盈提醒服务启动，间隔{self.scan_interval_minutes}分钟")

    def run_once(self):
        watch_items = self._load_watch_items()
        for item in watch_items:
            stop_gain = self._extract_stop_gain(item)
            if stop_gain:
                self._check_and_notify(item, stop_gain)

    def _load_watch_items(self):
        return self.favorites_service.list_favorites()

    def _extract_stop_gain(self, item):
        # 优先取用户设置的止盈线，否则取最新持仓分析报告的止盈线
        if 'alert_gain_price' in item and item['alert_gain_price']:
            return item['alert_gain_price']
        if 'analysis_report' in item and item['analysis_report']:
            report = item['analysis_report']
            if isinstance(report, dict) and 'stop_gain' in report:
                return report['stop_gain']
        return None

    def _check_and_notify(self, item, stop_gain):
        # 仅示例，实际需接入行情数据
        current_price = item.get('current_price')
        if not current_price or current_price < stop_gain:
            return
        user_id = item.get('user_id')
        symbol = item.get('symbol', '')
        if not user_id:
            return
        payload = NotificationCreate(
            user_id=str(user_id),
            type="alert",
            title=f"止盈提醒：{symbol} 已达到止盈线",
            content=f"当前价格 {current_price} 已达到止盈线 {stop_gain}，请关注。",
            source="stop_gain_alert",
            severity="success",
        )
        if self._loop and not self._loop.is_closed():
            try:
                async def _publish():
                    await get_notifications_service().create_and_publish(payload)
                asyncio.run_coroutine_threadsafe(_publish(), self._loop)
            except Exception as e:
                logger.warning("止盈提醒推送失败(忽略): %s", e)
        else:
            logger.debug("止盈提醒跳过推送：未设置或已关闭的 event_loop")

stop_gain_alert_service = StopGainAlertService()
