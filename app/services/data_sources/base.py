"""
Base classes and shared typing for data source adapters
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict
import pandas as pd


class DataSourceAdapter(ABC):
    """数据源适配器基类"""

    def __init__(self):
        self._priority: Optional[int] = None  # 动态优先级，从数据库加载

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        raise NotImplementedError

    @property
    def priority(self) -> int:
        """数据源优先级（数字越小优先级越高）"""
        # 如果有动态设置的优先级，使用动态优先级；否则使用默认优先级
        if self._priority is not None:
            return self._priority
        return self._get_default_priority()

    @abstractmethod
    def _get_default_priority(self) -> int:
        """获取默认优先级（子类实现）"""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        raise NotImplementedError

    @abstractmethod
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表"""
        raise NotImplementedError

    @abstractmethod
    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取每日基础财务数据"""
        raise NotImplementedError

    @abstractmethod
    def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        raise NotImplementedError

    # 新增：全市场实时快照（近实时价格/涨跌幅/成交额），键为6位代码
    @abstractmethod
    def get_realtime_quotes(self) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """返回 { '000001': {'close': 10.0, 'pct_chg': 1.2, 'amount': 1.2e8}, ... }"""
        raise NotImplementedError

    # 新增：K线与新闻抽象接口
    @abstractmethod
    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None):
        """获取K线，返回按时间正序的列表: [{time, open, high, low, close, volume, amount}]"""
        raise NotImplementedError

    @abstractmethod
    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """获取新闻/公告，返回 [{title, source, time, url, type}]，type in ['news','announcement']"""
        raise NotImplementedError

    def get_daily_ohlc(self, code: str, trade_date: str, adj: Optional[str] = None) -> Optional[Dict]:
        """
        获取指定日期的日线 OHLC 数据（可选复权方式）。

        Args:
            code: 6位股票代码
            trade_date: 交易日期，格式 YYYY-MM-DD 或 YYYYMMDD
            adj: 复权方式，None=不复权，"qfq"=前复权，"hfq"=后复权

        Returns:
            {"date": str, "open": float, "high": float, "low": float, "close": float} 或 None
        """
        # 默认实现：通过 get_kline 获取数据，筛选目标日期
        try:
            # 标准化目标日期格式为 YYYY-MM-DD
            target_date = trade_date.replace("-", "") if "-" in trade_date else trade_date
            if len(target_date) == 8:
                target_date = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}"

            # 根据目标日期与今天的距离，动态计算需要的 limit
            # 每年约 250 个交易日，预留 20% 余量
            from datetime import datetime
            try:
                target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                days_diff = (datetime.now() - target_dt).days
                # 至少 30 个交易日，最多 1500 个交易日（约6年）
                limit = max(30, min(1500, int(days_diff * 250 / 365 * 1.2) + 30))
            except (ValueError, TypeError):
                limit = 120  # 默认

            items = self.get_kline(code=code, period="day", limit=limit, adj=adj)
            if not items:
                return None

            for item in items:
                item_date = item.get("time", "")
                # 标准化 item 日期格式
                if len(item_date) == 8:
                    item_date = f"{item_date[:4]}-{item_date[4:6]}-{item_date[6:8]}"
                elif len(item_date) > 10:
                    item_date = item_date[:10]  # 截取 YYYY-MM-DD

                if item_date == target_date:
                    return {
                        "date": target_date,
                        "open": item.get("open"),
                        "high": item.get("high"),
                        "low": item.get("low"),
                        "close": item.get("close"),
                    }

            return None  # 目标日期不在返回数据中
        except Exception:
            return None
