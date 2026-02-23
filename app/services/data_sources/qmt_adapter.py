"""
QMT (迅投 MiniQMT) 数据源适配器

通过 xtquant.xtdata 连接本地 MiniQMT 客户端获取行情数据。
前置条件：
  1. MiniQMT 客户端需已启动（仅 Windows 支持）
  2. 获取行情数据不需要登录券商账户
  3. 交易功能需要登录券商账户（本适配器不涉及交易）
新闻不支持，统一使用 AKShare 数据源。
"""
from typing import Optional, Dict, List, Any
import logging
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)

# xtquant 可选依赖，未安装时适配器不可用
_xtdata = None


def _get_xtdata():
    """延迟导入 xtquant.xtdata"""
    global _xtdata
    if _xtdata is None:
        try:
            import xtquant.xtdata as xt  # type: ignore
            _xtdata = xt
        except ImportError:
            logger.debug("xtquant 未安装，QMT 适配器不可用")
            return None
    return _xtdata


def _normalize_code(code: str) -> str:
    """将 6 位代码转为 xtdata 格式：000001.SZ / 600000.SH"""
    code = str(code).strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    code = "".join(filter(str.isdigit, code)).zfill(6)
    if not code or len(code) != 6:
        return ""
    if code.startswith(("60", "68", "90")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "20", "15", "16")):
        return f"{code}.SZ"
    if code.startswith(("8", "4", "92")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _code_to_6digit(xt_code: str) -> str:
    """xtdata 代码转 6 位纯数字"""
    s = str(xt_code).split(".")[0]
    return "".join(filter(str.isdigit, s)).zfill(6)


class QMTAdapter(DataSourceAdapter):
    """QMT 数据源适配器（需 MiniQMT 运行，新闻用 AKShare）"""

    def __init__(self):
        super().__init__()
        self._available: Optional[bool] = None

    @property
    def name(self) -> str:
        return "qmt"

    def _get_default_priority(self) -> int:
        return 2  # 与 AKShare 同级，数字越大优先级越高

    def _safe_float(self, value) -> Optional[float]:
        try:
            if value is None or value == "" or (hasattr(value, "__float__") and str(value) == "nan"):
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def is_available(self) -> bool:
        """检查 xtquant 是否可用且 MiniQMT 已连接"""
        xt = _get_xtdata()
        if xt is None:
            return False
        try:
            # 尝试简单调用以检测 MiniQMT 是否已连接
            ticks = xt.get_full_tick([])
            if ticks is not None:
                self._available = True
                return True
            # get_full_tick([]) 可能返回空 dict，也算可用
            return True
        except Exception as e:
            logger.debug(f"QMT 不可用: {e}")
            return False

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表（通过沪深成分股组合）"""
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        try:
            # 沪深 A 股：通过板块获取
            sh_stocks = xt.get_stock_list_in_sector("沪深A股", 0) or []
            if not sh_stocks:
                sh_stocks = xt.get_stock_list_in_sector("沪市A股", 0) or []
                sz_stocks = xt.get_stock_list_in_sector("深市A股", 0) or []
                stocks = list(sh_stocks) + list(sz_stocks)
            else:
                stocks = list(sh_stocks)

            if not stocks:
                logger.warning("QMT: 未获取到股票列表")
                return None

            rows = []
            for xt_code in stocks[:10000]:  # 限制数量
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6:
                    continue
                try:
                    detail = xt.get_instrument_detail(xt_code)
                    name = ""
                    if detail and isinstance(detail, dict):
                        name = detail.get("InstrumentName", "") or detail.get("name", "")
                    elif detail and hasattr(detail, "InstrumentName"):
                        name = getattr(detail, "InstrumentName", "")
                    rows.append({
                        "symbol": code6,
                        "ts_code": xt_code,
                        "name": name or code6,
                        "market": "",
                        "area": "",
                        "industry": "",
                        "list_date": "",
                    })
                except Exception:
                    rows.append({"symbol": code6, "ts_code": xt_code, "name": code6, "market": "", "area": "", "industry": "", "list_date": ""})

            if rows:
                df = pd.DataFrame(rows)
                logger.info(f"QMT: 获取到 {len(df)} 只股票")
                return df
            return None
        except Exception as e:
            logger.error(f"QMT: 获取股票列表失败: {e}")
            return None

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取每日基础数据（通过 get_market_data 日线，PE/PB 可能缺失）"""
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        try:
            stock_list = self.get_stock_list()
            if stock_list is None or stock_list.empty:
                return None
            codes = stock_list["ts_code"].head(500).tolist()
            trade_date_str = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            data = xt.get_market_data(
                field_list=["open", "high", "low", "close", "volume", "amount"],
                stock_list=codes,
                period="1d",
                start_time=trade_date_str,
                end_time=trade_date_str,
            )
            if not data or not isinstance(data, dict):
                return None
            rows = []
            for xt_code, v in data.items():
                if v is None:
                    continue
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6:
                    continue
                close, vol, amt = None, None, None
                if isinstance(v, pd.DataFrame) and not v.empty:
                    row0 = v.iloc[0]
                    close = row0.get("close")
                    vol = row0.get("volume")
                    amt = row0.get("amount")
                elif isinstance(v, dict):
                    close = v.get("close")
                    vol = v.get("volume")
                    amt = v.get("amount")
                rows.append({
                    "ts_code": xt_code,
                    "trade_date": trade_date,
                    "close": self._safe_float(close),
                    "vol": self._safe_float(vol),
                    "amount": self._safe_float(amt),
                    "total_mv": None,
                    "circ_mv": None,
                    "pe": None,
                    "pb": None,
                    "turnover_rate": None,
                })
            if rows:
                return pd.DataFrame(rows)
            return None
        except Exception as e:
            logger.error(f"QMT: 获取 daily_basic 失败: {e}")
            return None

    def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        if not self.is_available():
            return None
        try:
            from datetime import date
            d = date.today()
            for _ in range(10):
                s = d.strftime("%Y%m%d")
                if self.get_daily_basic(s) is not None:
                    return s
                d -= timedelta(days=1)
            return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        except Exception as e:
            logger.error(f"QMT: find_latest_trade_date 失败: {e}")
            return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    def get_realtime_quotes(self) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """获取全市场实时快照"""
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        try:
            ticks = xt.get_full_tick([])
            if not ticks or not isinstance(ticks, dict):
                return None
            result: Dict[str, Dict[str, Optional[float]]] = {}
            for xt_code, t in ticks.items():
                if t is None:
                    continue
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6:
                    continue
                last_price = getattr(t, "lastPrice", None) or (t.get("lastPrice") if isinstance(t, dict) else None)
                pct = getattr(t, "pctChange", None) or (t.get("pctChange") if isinstance(t, dict) else None)
                amt = getattr(t, "amount", None) or (t.get("amount") if isinstance(t, dict) else None)
                result[code6] = {
                    "close": float(last_price) if last_price is not None else None,
                    "pct_chg": float(pct) if pct is not None else None,
                    "amount": float(amt) if amt is not None else None,
                }
            if result:
                logger.info(f"QMT: 获取到 {len(result)} 只股票实时行情")
                return result
            return None
        except Exception as e:
            logger.error(f"QMT: 获取实时行情失败: {e}")
            return None

    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """获取 K 线数据

        根据迅投官方文档：
        1. 使用前需确保 MiniQMT 已有所需数据
        2. 如果本地没有数据，先调用 download_history_data 下载
        3. 推荐使用 get_market_data_ex 接口
        """
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        try:
            xt_code = _normalize_code(code)
            if not xt_code:
                return None
            period_map = {
                "day": "1d",
                "week": "1w",
                "month": "1mon",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "60m": "1h",
            }
            xt_period = period_map.get(period, "1d")

            # 根据官方文档，使用 get_market_data_ex 接口
            # 传入空的 field_list 表示获取所有字段
            data = xt.get_market_data_ex(
                field_list=[],  # 空列表表示获取所有字段
                stock_list=[xt_code],
                period=xt_period,
                count=limit  # 获取最近 N 条数据
            )
            if not data or xt_code not in data:
                return None
            df = data[xt_code]
            if df is None or (hasattr(df, "empty") and df.empty):
                return None
            # xtdata 返回 {stock_code: pd.DataFrame}
            if isinstance(df, pd.DataFrame):
                df = df.tail(limit)
                items = []
                for idx, row in df.iterrows():
                    # get_market_data_ex 使用 DataFrame 的索引作为时间
                    # 索引通常是 pandas Timestamp 或时间戳
                    if hasattr(idx, 'strftime'):
                        # pandas Timestamp 对象
                        date_str = idx.strftime("%Y-%m-%d")
                    elif isinstance(idx, (int, float)):
                        # 时间戳（毫秒）
                        from datetime import datetime
                        date_str = datetime.fromtimestamp(idx / 1000).strftime("%Y-%m-%d")
                    elif isinstance(idx, str) and len(idx) == 8 and idx.isdigit():
                        # YYYYMMDD 格式，转换为 YYYY-MM-DD
                        date_str = f"{idx[:4]}-{idx[4:6]}-{idx[6:8]}"
                    else:
                        # 其他格式，直接转字符串
                        date_str = str(idx)

                    items.append({
                        "date": date_str,
                        "open": self._safe_float(row.get("open")),
                        "high": self._safe_float(row.get("high")),
                        "low": self._safe_float(row.get("low")),
                        "close": self._safe_float(row.get("close")),
                        "volume": self._safe_float(row.get("volume")),
                        "amount": self._safe_float(row.get("amount")),
                    })
                return items
            return None
        except Exception as e:
            logger.error(f"QMT: get_kline 失败: {e}", exc_info=True)
            return None

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True) -> Optional[List[Dict]]:
        """QMT 不支持新闻，返回 None，由 DataSourceManager 回退到 AKShare"""
        logger.debug("QMT: 不支持新闻，请使用 AKShare")
        return None

    # ==================== 财务数据接口（扩展功能） ====================

    def download_financial_data(
        self,
        stock_list: List[str],
        table_list: Optional[List[str]] = None,
        start_time: str = '',
        end_time: str = '',
        callback=None
    ) -> bool:
        """
        下载财务数据到本地

        Args:
            stock_list: 股票代码列表（6位代码，会自动转换为 QMT 格式）
            table_list: 财务报表类型列表，支持：
                - 'Balance': 资产负债表
                - 'Income': 利润表
                - 'CashFlow': 现金流量表
                - 'Pershareindex': 每股指标（主要指标）
                - 'Capital': 股本表
                - 'Top10holder': 十大股东
                - 'Top10flowholder': 十大流通股东
                - 'Holdernum': 股东数
            start_time: 起始时间（YYYYMMDD），按披露日期筛选
            end_time: 结束时间（YYYYMMDD），按披露日期筛选
            callback: 进度回调函数，参数为 dict:
                - total: 总任务数
                - finished: 已完成数
                - stockcode: 当前股票代码
                - message: 消息

        Returns:
            bool: 下载是否成功
        """
        if not self.is_available():
            return False
        xt = _get_xtdata()
        if xt is None:
            return False

        try:
            # 转换股票代码为 QMT 格式
            xt_codes = []
            for code in stock_list:
                xt_code = _normalize_code(code)
                if xt_code:
                    xt_codes.append(xt_code)

            if not xt_codes:
                logger.warning("QMT: 没有有效的股票代码")
                return False

            # 默认下载所有报表
            if table_list is None:
                table_list = [
                    'Balance',          # 资产负债表
                    'Income',           # 利润表
                    'CashFlow',         # 现金流量表
                    'Pershareindex',    # 每股指标
                    'Capital',          # 股本表
                ]

            logger.info(f"QMT: 开始下载财务数据 - {len(xt_codes)} 只股票, {len(table_list)} 种报表")

            # 使用 download_financial_data2（带回调）
            xt.download_financial_data2(
                stock_list=xt_codes,
                table_list=table_list,
                start_time=start_time,
                end_time=end_time,
                callback=callback
            )

            logger.info(f"QMT: 财务数据下载完成")
            return True

        except Exception as e:
            logger.error(f"QMT: 下载财务数据失败: {e}", exc_info=True)
            return False

    def get_financial_data(
        self,
        code: str,
        table_list: Optional[List[str]] = None,
        start_time: str = '',
        end_time: str = '',
        report_type: str = 'report_time'
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        获取财务数据（从本地缓存）

        Args:
            code: 股票代码（6位代码）
            table_list: 财务报表类型列表，默认获取主要报表
            start_time: 起始时间（YYYYMMDD）
            end_time: 结束时间（YYYYMMDD）
            report_type: 报表筛选方式
                - 'report_time': 按截止日期筛选
                - 'announce_time': 按披露日期筛选

        Returns:
            dict: {table_name: DataFrame} 或 None
                例如: {'Income': DataFrame, 'Balance': DataFrame}
        """
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None

        try:
            xt_code = _normalize_code(code)
            if not xt_code:
                return None

            # 默认获取主要报表
            if table_list is None:
                table_list = [
                    'Pershareindex',    # 每股指标
                    'Income',           # 利润表
                    'Balance',          # 资产负债表
                ]

            # 获取财务数据
            data = xt.get_financial_data(
                stock_list=[xt_code],
                table_list=table_list,
                start_time=start_time,
                end_time=end_time,
                report_type=report_type
            )

            if not data or xt_code not in data:
                return None

            stock_data = data[xt_code]

            # 过滤掉空的 DataFrame
            result = {}
            for table_name, df in stock_data.items():
                if df is not None and not df.empty:
                    result[table_name] = df

            return result if result else None

        except Exception as e:
            logger.error(f"QMT: 获取财务数据失败 {code}: {e}", exc_info=True)
            return None
