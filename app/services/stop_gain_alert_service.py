# 止盈提醒服务
# 参考止损提醒实现，支持自动提取持仓分析止盈线，定时扫描并推送通知

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.favorites_service import FavoritesService
from app.services.intelligent_assistant_service import publish_notification

class StopGainAlertService:
    def __init__(self, scan_interval_minutes=10):
        self.scan_interval_minutes = scan_interval_minutes
        self.scheduler = BackgroundScheduler()
        self.favorites_service = FavoritesService()
        self._job = None

    def start(self):
        if not self._job:
            self._job = self.scheduler.add_job(self.run_once, 'interval', minutes=self.scan_interval_minutes)
            self.scheduler.start()
            logging.info(f"止盈提醒服务启动，间隔{self.scan_interval_minutes}分钟")

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
        if current_price and current_price >= stop_gain:
            publish_notification(
                user_id=item['user_id'],
                title=f"止盈提醒：{item['symbol']} 已达到止盈线",
                content=f"当前价格 {current_price} 已达到止盈线 {stop_gain}，请关注。"
            )

stop_gain_alert_service = StopGainAlertService()
