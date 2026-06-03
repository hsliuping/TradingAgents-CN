"""
QMT (迅投 MiniQMT) 数据源适配器

通过 xtquant.xtdata 连接本地 MiniQMT 客户端获取行情数据。
前置条件：
  1. MiniQMT 客户端需已启动（仅 Windows 支持）
  2. 获取行情数据不需要登录券商账户
  3. 交易功能需要登录券商账户（本适配器不涉及交易）
新闻不支持，统一使用 AKShare 数据源。
"""
from typing import Optional, Dict, List, Any, Tuple
import logging
import os
import time
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)

# xtquant 可选依赖，未安装时适配器不可用
_xtdata = None
_xtdatacenter = None


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


def _get_xtdatacenter():
    """延迟导入 xtquant.xtdatacenter"""
    global _xtdatacenter
    if _xtdatacenter is None:
        try:
            from xtquant import xtdatacenter as xtdc  # type: ignore
            _xtdatacenter = xtdc
        except ImportError:
            logger.debug("xtquant.xtdatacenter 未安装，跳过 QMT 主动初始化")
            return None
    return _xtdatacenter


def _normalize_code(code: str) -> str:
    """将 6 位代码转为 xtdata 格式：000001.SZ / 600000.SH"""
    raw_code = str(code).strip().upper()
    if raw_code.endswith((".SH", ".SZ", ".BJ")):
        suffix = raw_code[-3:]
        digits = "".join(filter(str.isdigit, raw_code[:-3])).zfill(6)
        if len(digits) == 6:
            return f"{digits}{suffix}"

    code = raw_code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    code = "".join(filter(str.isdigit, code)).zfill(6)
    if not code or len(code) != 6:
        return ""
    if code.startswith(("50", "51", "52", "56", "58")):
        return f"{code}.SH"
    if code.startswith(("60", "68", "90")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "20", "15", "16", "18")):
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
        self._bootstrapped = False
        self._sector_data_prepared = False

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

    def _get_runtime_setting(self, name: str, default: Any = None) -> Any:
        env_value = os.getenv(name)
        if env_value not in (None, ""):
            return env_value

        try:
            from app.core.config import settings as app_settings
            return getattr(app_settings, name)
        except Exception:
            return default

    def _parse_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _parse_list(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raw = str(value).replace(";", ",").replace("\n", ",")
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _parse_port_range(self, value: Any) -> Optional[Tuple[int, int]]:
        if value is None or value == "":
            return None
        if isinstance(value, (list, tuple)) and len(value) == 2:
            try:
                return int(value[0]), int(value[1])
            except (TypeError, ValueError):
                return None

        text = str(value).strip()
        delimiter = "-" if "-" in text else "," if "," in text else None
        if not delimiter:
            return None
        parts = [part.strip() for part in text.split(delimiter) if part.strip()]
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None

    def _has_existing_connection(self, xt: Any) -> bool:
        """优先复用已启动的 MiniQMT 连接，避免默认配置误触发独立初始化。"""
        if xt is None:
            return False
        try:
            ticks = xt.get_full_tick([])
            if ticks is not None:
                self._available = True
                return True
            # get_full_tick([]) 可能返回空 dict，也视为可用
            self._available = True
            return True
        except Exception:
            return False

    def _should_initialize_connection(
        self,
        token: str,
        optimize_addresses: List[str],
        mirror_markets: List[str],
        mirror_enabled: bool,
        start_local_service: bool,
        listen_port: Any,
    ) -> bool:
        """仅在显式独立连接场景下执行 xtdatacenter 主动初始化。"""
        try:
            parsed_port = int(listen_port or 0)
        except (TypeError, ValueError):
            parsed_port = 0

        return any(
            [
                bool(token),
                bool(optimize_addresses),
                bool(mirror_markets),
                bool(mirror_enabled),
                bool(start_local_service),
                parsed_port > 0,
            ]
        )

    def _bootstrap_connection(self) -> None:
        if self._bootstrapped:
            return

        self._bootstrapped = True

        xt = _get_xtdata()
        xtdc = _get_xtdatacenter()
        if xt is None or xtdc is None:
            return

        data_dir = self._get_runtime_setting("QMT_DATA_DIR", "")
        token = self._get_runtime_setting("QMT_TOKEN", "")
        init_markets = self._parse_list(self._get_runtime_setting("QMT_INIT_MARKETS", ""))
        optimize_addresses = self._parse_list(self._get_runtime_setting("QMT_ALLOW_OPTIMIZE_ADDRESSES", ""))
        mirror_markets = self._parse_list(self._get_runtime_setting("QMT_KLINE_MIRROR_MARKETS", ""))
        mirror_enabled = self._parse_bool(self._get_runtime_setting("QMT_KLINE_MIRROR_ENABLED", False))
        start_local_service = self._parse_bool(self._get_runtime_setting("QMT_START_LOCAL_SERVICE", False))
        listen_port = self._get_runtime_setting("QMT_LISTEN_PORT", 0)
        listen_port_range = self._parse_port_range(self._get_runtime_setting("QMT_LISTEN_PORT_RANGE", "58620-58650"))

        if self._has_existing_connection(xt):
            logger.info("QMT: 检测到现有 MiniQMT 连接，跳过主动初始化")
            return

        should_initialize = self._should_initialize_connection(
            token=token,
            optimize_addresses=optimize_addresses,
            mirror_markets=mirror_markets,
            mirror_enabled=mirror_enabled,
            start_local_service=start_local_service,
            listen_port=listen_port,
        )
        if not should_initialize:
            logger.info(
                "QMT: 未检测到现有 MiniQMT 连接，且当前为默认 MiniQMT 模式，"
                "跳过 xtdatacenter 主动初始化，请先启动并保持 MiniQMT 客户端运行"
            )
            return

        try:
            if data_dir:
                xtdc.set_data_home_dir(str(data_dir))
            if token:
                xtdc.set_token(str(token))
            if optimize_addresses:
                xtdc.set_allow_optmize_address(optimize_addresses)
            if mirror_markets:
                xtdc.set_kline_mirror_markets(mirror_markets)
            elif mirror_enabled:
                xtdc.set_kline_mirror_enabled(True)
            if init_markets:
                xtdc.set_init_markets(init_markets)

            xtdc.init(start_local_service=start_local_service)

            port = 0
            try:
                port = int(listen_port or 0)
            except (TypeError, ValueError):
                port = 0

            if port > 0:
                listen_result = xtdc.listen(port=port)
            elif listen_port_range:
                listen_result = xtdc.listen(port=listen_port_range)
            else:
                listen_result = xtdc.listen(port=(58620, 58650))

            if isinstance(listen_result, tuple):
                connect_port = int(listen_result[-1])
            else:
                connect_port = int(listen_result)

            xt.connect(port=connect_port)
            logger.info(f"QMT: 已根据配置初始化连接，端口 {connect_port}")
        except Exception as e:
            logger.warning(f"QMT: 主动初始化连接失败，将回退到现有 MiniQMT 连接: {e}")

    def _prepare_sector_data(self) -> None:
        if self._sector_data_prepared:
            return

        # 默认不自动下载板块数据，避免 xt.download_sector_data / download_history_data2 卡死
        if self._parse_bool(self._get_runtime_setting("QMT_AUTO_DOWNLOAD_SECTOR", False)):
            xt = _get_xtdata()
            if xt is None:
                self._sector_data_prepared = True
                return

            try:
                logger.info("QMT: 正在下载板块数据（默认关闭）")
                xt.download_sector_data()
            except Exception as e:
                logger.debug(f"QMT: 下载板块数据失败，将继续尝试读取本地缓存: {e}")
            finally:
                self._sector_data_prepared = True
        else:
            self._sector_data_prepared = True

    def _download_history_if_needed(self, xt_code: str, xt_period: str) -> None:
        if not self._parse_bool(self._get_runtime_setting("QMT_AUTO_DOWNLOAD_HISTORY", True)):
            return

        xt = _get_xtdata()
        if xt is None:
            return

        start_time = str(self._get_runtime_setting("QMT_HISTORY_START_TIME", "") or "")
        try:
            xt.download_history_data(xt_code, period=xt_period, start_time=start_time, incrementally=True)
        except TypeError:
            try:
                xt.download_history_data(xt_code, period=xt_period, start_time=start_time)
            except Exception as e:
                logger.debug(f"QMT: 自动下载历史数据失败 {xt_code}: {e}")
        except Exception as e:
            logger.debug(f"QMT: 自动下载历史数据失败 {xt_code}: {e}")

    def _download_financial_if_needed(self, code: str, table_list: Optional[List[str]], start_time: str, end_time: str) -> None:
        if not self._parse_bool(self._get_runtime_setting("QMT_AUTO_DOWNLOAD_FINANCIAL", False)):
            return
        self.download_financial_data([code], table_list=table_list, start_time=start_time, end_time=end_time)

    def _is_etf_code(self, code: str) -> bool:
        code = str(code).strip().zfill(6)
        return code.startswith(("50", "51", "52", "56", "58", "15", "16", "18"))

    def is_available(self) -> bool:
        """检查 xtquant 是否可用且 MiniQMT 已连接"""
        # 快速短路：如果 QMT 在配置中未启用，直接返回 False（跳过约 2 秒连接超时）
        try:
            from app.core.config import settings as app_settings
            if not app_settings.QMT_UNIFIED_ENABLED:
                return False
        except Exception:
            pass

        self._bootstrap_connection()

        xt = _get_xtdata()
        if xt is None:
            return False
        if self._has_existing_connection(xt):
            return True

        logger.debug("QMT 不可用: 未检测到可复用的 MiniQMT 连接")
        return False

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表（通过沪深成分股组合）"""
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        try:
            start_time = time.perf_counter()

            # 沪深 A 股：通过板块获取（不等待板块数据下载）
            sector_query_start = time.perf_counter()
            sh_stocks = xt.get_stock_list_in_sector("沪深A股", 0) or []
            if not sh_stocks:
                sh_stocks = xt.get_stock_list_in_sector("沪市A股", 0) or []
                sz_stocks = xt.get_stock_list_in_sector("深市A股", 0) or []
                stocks = list(sh_stocks) + list(sz_stocks)
            else:
                stocks = list(sh_stocks)
            sector_query_elapsed = time.perf_counter() - sector_query_start

            if not stocks:
                logger.warning("QMT: 未获取到股票列表")
                return None

            max_count_raw = self._get_runtime_setting("QMT_STOCK_LIST_MAX_COUNT", 10000)
            detail_limit_raw = self._get_runtime_setting("QMT_STOCK_LIST_DETAIL_LIMIT", 300)
            detail_budget_raw = self._get_runtime_setting("QMT_STOCK_LIST_DETAIL_TIMEOUT_SECONDS", 5)
            try:
                max_count = max(1, int(str(max_count_raw)))
            except (TypeError, ValueError):
                max_count = 10000
            try:
                detail_lookup_limit = max(0, int(str(detail_limit_raw)))
            except (TypeError, ValueError):
                detail_lookup_limit = 300
            try:
                detail_time_budget = max(0.0, float(str(detail_budget_raw)))
            except (TypeError, ValueError):
                detail_time_budget = 5.0

            rows = []
            detail_lookup_count = 0
            detail_lookup_start = time.perf_counter()
            detail_budget_exhausted = False

            for xt_code in stocks[:max_count]:
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6:
                    continue

                use_detail_lookup = (
                    detail_lookup_count < detail_lookup_limit
                    and (time.perf_counter() - detail_lookup_start) < detail_time_budget
                )
                try:
                    name = ""
                    if use_detail_lookup:
                        detail = xt.get_instrument_detail(xt_code)
                        detail_lookup_count += 1
                        if detail and isinstance(detail, dict):
                            name = detail.get("InstrumentName", "") or detail.get("name", "")
                        elif detail and hasattr(detail, "InstrumentName"):
                            name = getattr(detail, "InstrumentName", "")
                    else:
                        detail_budget_exhausted = True
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
                total_elapsed = time.perf_counter() - start_time
                logger.info(
                    "QMT: 获取到 %s 只股票，板块查询 %.2fs，详情补充 %s/%s，详情预算 %.2fs，耗时 %.2fs%s",
                    len(df),
                    sector_query_elapsed,
                    detail_lookup_count,
                    min(len(stocks), max_count),
                    detail_time_budget,
                    total_elapsed,
                    "（已提前停止详情补充）" if detail_budget_exhausted else "",
                )
                return df
            return None
        except Exception as e:
            logger.error(f"QMT: 获取股票列表失败: {e}")
            return None

    def get_etf_list(self) -> Optional[pd.DataFrame]:
        """获取 ETF 列表（通过 QMT 板块列表和代码前缀过滤）"""
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None

        try:
            sector_candidates = [
                "沪深ETF",
                "ETF",
                "沪市ETF",
                "深市ETF",
                "上证ETF",
                "深证ETF",
                "场内基金",
            ]

            etf_codes: List[str] = []
            for sector_name in sector_candidates:
                try:
                    sector_codes = xt.get_stock_list_in_sector(sector_name, 0) or []
                    if sector_codes:
                        etf_codes.extend(list(sector_codes))
                except Exception:
                    continue

            unique_codes: List[str] = []
            seen_codes = set()
            for xt_code in etf_codes:
                code6 = _code_to_6digit(xt_code)
                if not self._is_etf_code(code6):
                    continue
                if code6 in seen_codes:
                    continue
                seen_codes.add(code6)
                unique_codes.append(xt_code)

            if not unique_codes:
                logger.warning("QMT: 未获取到 ETF 列表")
                return None

            rows = []
            for xt_code in unique_codes:
                code6 = _code_to_6digit(xt_code)
                try:
                    detail = xt.get_instrument_detail(xt_code)
                    name = ""
                    if detail and isinstance(detail, dict):
                        name = detail.get("InstrumentName", "") or detail.get("name", "")
                    elif detail and hasattr(detail, "InstrumentName"):
                        name = getattr(detail, "InstrumentName", "")
                    rows.append({
                        "symbol": code6,
                        "code": code6,
                        "ts_code": xt_code,
                        "name": name or code6,
                        "fund_type": "ETF",
                    })
                except Exception:
                    rows.append({"symbol": code6, "code": code6, "ts_code": xt_code, "name": code6, "fund_type": "ETF"})

            return pd.DataFrame(rows) if rows else None
        except Exception as e:
            logger.error(f"QMT: 获取 ETF 列表失败: {e}")
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

            self._download_history_if_needed(xt_code, xt_period)

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

            self._download_financial_if_needed(code, table_list, start_time, end_time)

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
