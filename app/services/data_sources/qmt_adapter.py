"""
QMT (迅投 QMT 交易终端) 数据源适配器

通过 xtquant.xtdata 连接本地 QMT 交易终端获取行情数据，并通过 xtquant.xttrader
提供只读的持仓/资产查询能力。
前置条件：
    1. QMT 交易终端需已启动（仅 Windows 支持）
    2. 获取行情数据不需要登录券商账户
    3. 持仓/资产查询需要券商账户已在 QMT 交易终端中登录（本适配器不提供下单能力）
新闻不支持，统一使用 AKShare 数据源。
"""
from typing import Optional, Dict, List, Any, Tuple
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)

# xtquant 可选依赖，未安装时适配器不可用
_xtdata = None
_xtdatacenter = None
_xttrader = None


def _iter_qmt_root_candidates() -> List[Path]:
    """收集 QMT 安装根路径候选，用于自动发现 xtquant 包。"""
    raw_candidates: List[Path] = []
    configured = os.getenv("QMT_DATA_DIR", "")
    if configured:
        raw_candidates.append(Path(configured).expanduser())

    raw_candidates.extend([
        Path(r"D:\gjzq\bin.x64"),
        Path(r"D:\gjzq"),
        Path(r"C:\gjzq\bin.x64"),
        Path(r"C:\gjzq"),
    ])

    seen: set[str] = set()
    roots: List[Path] = []
    for base in raw_candidates:
        for candidate in (base, base.parent, base.parent.parent):
            try:
                resolved = candidate.resolve()
            except Exception:
                continue
            if not resolved.exists():
                continue
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            roots.append(resolved)
    return roots


def _ensure_qmt_python_path() -> Optional[str]:
    """将 QMT 自带的 xtquant/site-packages 加入 sys.path。"""
    for root in _iter_qmt_root_candidates():
        for site_packages in (
            root / "Lib" / "site-packages",
            root / "bin.x64" / "Lib" / "site-packages",
        ):
            xtquant_dir = site_packages / "xtquant"
            if not xtquant_dir.is_dir():
                continue

            site_packages_str = str(site_packages)
            if site_packages_str not in sys.path:
                sys.path.insert(0, site_packages_str)
                logger.info("QMT: 已添加 xtquant 路径 %s", site_packages_str)
            return site_packages_str
    return None


def _get_xtdata():
    """延迟导入 xtquant.xtdata"""
    global _xtdata
    if _xtdata is None:
        try:
            _ensure_qmt_python_path()
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
            _ensure_qmt_python_path()
            from xtquant import xtdatacenter as xtdc  # type: ignore
            _xtdatacenter = xtdc
        except ImportError:
            logger.debug("xtquant.xtdatacenter 未安装，跳过 QMT 主动初始化")
            return None
    return _xtdatacenter


def _get_xttrader():
    """延迟导入 xtquant.xttrader"""
    global _xttrader
    if _xttrader is None:
        try:
            _ensure_qmt_python_path()
            from xtquant import xttrader as xtt  # type: ignore
            _xttrader = xtt
        except ImportError:
            logger.debug("xtquant.xttrader 未安装，跳过 QMT 持仓查询")
            return None
    return _xttrader


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
    """QMT 数据源适配器（需 QMT 交易终端运行，新闻用 AKShare）"""

    _UNAVAILABLE_CACHE_UNTIL = 0.0
    _AVAILABLE_CACHE_UNTIL = 0.0
    _AVAILABILITY_PROBE_UNTIL = 0.0
    _UNAVAILABLE_CACHE_SECONDS = 30.0
    _AVAILABLE_CACHE_SECONDS = 10.0
    _PROBE_GUARD_SECONDS = 5.0

    def __init__(self):
        super().__init__()
        self._available: Optional[bool] = None
        self._bootstrapped = False
        self._sector_data_prepared = False
        # 数据质量统计
        self._quality_stats: Dict[str, Any] = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "last_error": None,
            "last_error_time": None,
            "by_method": {},
        }

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

    def _safe_int(self, value) -> Optional[int]:
        try:
            if value is None or value == "" or (hasattr(value, "__int__") and str(value) == "nan"):
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _resolve_qmt_userdata_dir(self) -> Optional[str]:
        """解析 QMT userdata 目录，用于 xttrader 只读查询。"""
        raw_candidates: List[Path] = []
        configured = self._get_runtime_setting("QMT_DATA_DIR", "")
        if configured:
            raw_candidates.append(Path(str(configured)).expanduser())

        raw_candidates.extend([
            Path(r"D:\gjzq\userdata"),
            Path(r"D:\gjzq\userdata_mini"),
            Path(r"D:\gjzq\bin.x64"),
            Path(r"D:\gjzq"),
            Path(r"C:\gjzq\userdata"),
            Path(r"C:\gjzq\userdata_mini"),
            Path(r"C:\gjzq\bin.x64"),
            Path(r"C:\gjzq"),
        ])

        seen: set[str] = set()
        for base in raw_candidates:
            for candidate in (
                base,
                base.parent,
                base.parent.parent,
            ):
                try:
                    resolved = candidate.resolve()
                except Exception:
                    continue
                if not resolved.exists():
                    continue
                key = str(resolved).lower()
                if key in seen:
                    continue
                seen.add(key)

                if resolved.name.lower() in {"userdata", "userdata_mini"}:
                    return str(resolved)

                for child_name in ("userdata", "userdata_mini"):
                    child = resolved / child_name
                    if child.is_dir():
                        return str(child)

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

    def query_account_snapshot(self, account_id: str, account_type: str = "STOCK") -> Optional[Dict[str, Any]]:
        """只读查询 QMT 账户快照，返回持仓 DataFrame 和账户资产摘要。"""
        account_id = str(account_id or "").strip()
        if not account_id:
            logger.warning("QMT: 账户号为空，无法查询账户快照")
            return None

        xttrader = _get_xttrader()
        if xttrader is None:
            logger.warning("QMT: xttrader 不可用，无法查询账户快照")
            return None

        userdata_dir = self._resolve_qmt_userdata_dir()
        if not userdata_dir:
            logger.warning("QMT: 未找到 userdata 目录，无法查询账户快照")
            return None

        try:
            from xtquant.xttype import StockAccount  # type: ignore
        except ImportError:
            logger.warning("QMT: xttype 不可用，无法构建账户对象")
            return None

        trader = None
        try:
            session = int(time.time() * 1000) % 2147483647
            trader = xttrader.XtQuantTrader(userdata_dir, session)
            trader.start()
            connect_result = trader.connect()
            if connect_result != 0:
                logger.warning("QMT: 交易客户端连接失败，返回码=%s", connect_result)
                return None

            account = StockAccount(account_id, account_type)
            positions = trader.query_stock_positions(account) or []
            asset = trader.query_stock_asset(account)
            xt = _get_xtdata()

            rows: List[Dict[str, Any]] = []
            for item in positions:
                stock_code = getattr(item, "stock_code", "") or getattr(item, "m_strStockCode", "")
                code6 = _code_to_6digit(stock_code)
                volume = self._safe_int(getattr(item, "volume", None))
                if not code6 or volume is None or volume <= 0:
                    continue

                can_use_volume = self._safe_int(getattr(item, "can_use_volume", None))
                open_price = self._safe_float(getattr(item, "open_price", None))
                market_value = self._safe_float(getattr(item, "market_value", None))
                frozen_volume = self._safe_int(getattr(item, "frozen_volume", None))
                on_road_volume = self._safe_int(getattr(item, "on_road_volume", None))
                yesterday_volume = self._safe_int(getattr(item, "yesterday_volume", None))

                xt_code = _normalize_code(code6)
                name = code6
                if xt is not None and xt_code:
                    try:
                        name = self._get_instrument_name(xt, xt_code, code6)
                    except Exception:
                        name = code6

                notes = f"QMT 持仓导入 | 账户 {account_id}"
                if can_use_volume is not None and can_use_volume != volume:
                    notes += f" | 可用 {can_use_volume}"
                if frozen_volume is not None and frozen_volume > 0:
                    notes += f" | 冻结 {frozen_volume}"
                if on_road_volume is not None and on_road_volume > 0:
                    notes += f" | 在途 {on_road_volume}"
                if yesterday_volume is not None and yesterday_volume > 0:
                    notes += f" | 昨仓 {yesterday_volume}"

                rows.append({
                    "code": code6,
                    "name": name,
                    "market": "CN",
                    "currency": "CNY",
                    "quantity": volume,
                    "cost_price": round(open_price, 4) if open_price is not None else 0.0,
                    "buy_date": None,
                    "notes": notes,
                    "qmt_stock_code": stock_code,
                    "can_use_quantity": can_use_volume,
                    "market_value": market_value,
                    "frozen_volume": frozen_volume,
                    "on_road_volume": on_road_volume,
                    "yesterday_volume": yesterday_volume,
                })

            columns = [
                "code", "name", "market", "currency", "quantity", "cost_price",
                "buy_date", "notes", "qmt_stock_code", "can_use_quantity",
                "market_value", "frozen_volume", "on_road_volume", "yesterday_volume",
            ]
            df = pd.DataFrame(rows, columns=columns)

            market_value_total = 0.0
            if not df.empty and "market_value" in df.columns:
                market_value_total = float(df["market_value"].fillna(0).sum())

            asset_cash = self._safe_float(getattr(asset, "cash", None)) if asset is not None else None
            asset_frozen_cash = self._safe_float(getattr(asset, "frozen_cash", None)) if asset is not None else None
            asset_market_value = self._safe_float(getattr(asset, "market_value", None)) if asset is not None else None
            asset_total_asset = self._safe_float(getattr(asset, "total_asset", None)) if asset is not None else None

            if asset_market_value is None:
                asset_market_value = round(market_value_total, 2)
            if asset_total_asset is None and asset_cash is not None:
                asset_total_asset = round(asset_cash + (asset_market_value or 0.0), 2)

            asset_summary = {
                "cash": asset_cash,
                "frozen_cash": asset_frozen_cash,
                "market_value": asset_market_value,
                "total_asset": asset_total_asset,
            }

            if asset is not None:
                logger.info(
                    "QMT: 持仓查询完成，账户=%s，持仓=%s 只，现金=%s，总资产=%s",
                    account_id,
                    len(df),
                    getattr(asset, "cash", None),
                    getattr(asset, "total_asset", None),
                )
            else:
                logger.info("QMT: 持仓查询完成，账户=%s，持仓=%s 只", account_id, len(df))

            return {
                "account_id": account_id,
                "account_type": account_type,
                "positions_df": df,
                "asset": asset_summary,
            }
        except Exception as e:
            logger.error(f"QMT: 查询账户快照失败: {e}")
            return None
        finally:
            if trader is not None:
                try:
                    trader.stop()
                except Exception:
                    pass

    def query_account_positions(self, account_id: str, account_type: str = "STOCK") -> Optional[pd.DataFrame]:
        """只读查询 QMT 账户持仓，返回可导入持仓的 DataFrame。"""
        snapshot = self.query_account_snapshot(account_id, account_type)
        if snapshot is None:
            return None
        return snapshot.get("positions_df")

    def _has_existing_connection(self, xt: Any) -> bool:
        """优先复用已启动的 QMT 连接，避免默认配置误触发独立初始化。"""
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
            logger.info("QMT: 检测到现有 QMT 连接，跳过主动初始化")
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
                "QMT: 未检测到现有 QMT 连接，且当前为默认 QMT 模式，"
                "跳过 xtdatacenter 主动初始化，请先启动并保持 QMT 交易终端运行"
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
            logger.warning(f"QMT: 主动初始化连接失败，将回退到现有 QMT 连接: {e}")

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

    def _mark_qmt_available(self) -> None:
        type(self)._AVAILABLE_CACHE_UNTIL = time.monotonic() + self._AVAILABLE_CACHE_SECONDS
        type(self)._UNAVAILABLE_CACHE_UNTIL = 0.0
        self._available = True

    def _mark_qmt_unavailable(self) -> None:
        type(self)._UNAVAILABLE_CACHE_UNTIL = time.monotonic() + self._UNAVAILABLE_CACHE_SECONDS
        type(self)._AVAILABLE_CACHE_UNTIL = 0.0
        self._available = False

    def is_available(self) -> bool:
        """检查 xtquant 是否可用且 QMT 已连接"""
        now = time.monotonic()
        if now < type(self)._UNAVAILABLE_CACHE_UNTIL:
            return False
        if now < type(self)._AVAILABLE_CACHE_UNTIL:
            return True
        if now < type(self)._AVAILABILITY_PROBE_UNTIL:
            logger.debug("QMT 可用性探测正在进行，当前请求快速跳过")
            return False

        # 快速短路：如果 QMT 在配置中未启用，直接返回 False（跳过连接探测）
        try:
            from app.core.config import settings as app_settings
            if not app_settings.QMT_UNIFIED_ENABLED:
                self._mark_qmt_unavailable()
                return False
        except Exception:
            pass

        type(self)._AVAILABILITY_PROBE_UNTIL = now + self._PROBE_GUARD_SECONDS
        try:
            self._bootstrap_connection()

            xt = _get_xtdata()
            if xt is None:
                self._mark_qmt_unavailable()
                return False
            if self._has_existing_connection(xt):
                self._mark_qmt_available()
                return True

            logger.debug("QMT 不可用: 未检测到可复用的 QMT 连接")
            self._mark_qmt_unavailable()
            return False
        finally:
            type(self)._AVAILABILITY_PROBE_UNTIL = 0.0

    # ==================== 数据质量监控 ====================

    def _record_quality(self, method: str, success: bool, error: Optional[str] = None, duration_ms: float = 0) -> None:
        """记录数据获取质量指标。"""
        self._quality_stats["total_calls"] += 1
        if success:
            self._quality_stats["success_calls"] += 1
        else:
            self._quality_stats["failed_calls"] += 1
            self._quality_stats["last_error"] = error
            self._quality_stats["last_error_time"] = datetime.now().isoformat()

        by_method = self._quality_stats["by_method"]
        if method not in by_method:
            by_method[method] = {"total": 0, "success": 0, "failed": 0, "avg_duration_ms": 0, "last_error": None}
        m = by_method[method]
        m["total"] += 1
        if success:
            m["success"] += 1
        else:
            m["failed"] += 1
            m["last_error"] = error
        if duration_ms > 0:
            m["avg_duration_ms"] = (m["avg_duration_ms"] * (m["total"] - 1) + duration_ms) / m["total"]

    def get_quality_stats(self) -> Dict[str, Any]:
        """获取数据质量统计。"""
        stats = dict(self._quality_stats)
        stats["success_rate"] = (
            stats["success_calls"] / stats["total_calls"] * 100
            if stats["total_calls"] > 0 else 0
        )
        return stats

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
        """获取每日基础数据（通过 get_market_data_ex 日线）"""
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
            # get_market_data_ex 的 start_time/end_time 需要 YYYYMMDD 格式
            trade_date_compact = trade_date.replace("-", "")

            data = xt.get_market_data_ex(
                field_list=["open", "high", "low", "close", "volume", "amount"],
                stock_list=codes,
                period="1d",
                start_time=trade_date_compact,
                end_time=trade_date_compact,
            )
            if not data or not isinstance(data, dict):
                return None

            rows = []
            for xt_code, df in data.items():
                if df is None:
                    continue
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6:
                    continue
                close, vol, amt = None, None, None
                if isinstance(df, pd.DataFrame) and not df.empty:
                    row0 = df.iloc[0]
                    close = row0.get("close")
                    vol = row0.get("volume")
                    amt = row0.get("amount")
                elif isinstance(df, dict):
                    close = df.get("close")
                    vol = df.get("volume")
                    amt = df.get("amount")
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
        """查找最新交易日期（用上证指数最近一根日线判断，轻量高效）"""
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        try:
            data = xt.get_market_data_ex(
                field_list=["close"],
                stock_list=["000001.SH"],
                period="1d",
                count=1,
            )
            if data and isinstance(data, dict):
                for xt_code, df in data.items():
                    if df is not None and not df.empty:
                        latest = df.index[-1]
                        # index 可能是字符串或 Timestamp
                        return str(latest)[:10].replace("-", "")
            # 兜底
            return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        except Exception as e:
            logger.error(f"QMT: find_latest_trade_date 失败: {e}")
            return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    def get_realtime_quotes(self, symbols: Optional[List[str]] = None) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """获取实时快照

        Args:
            symbols: 可选，指定股票代码列表（6位纯数字），为空则获取全市场
        """
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        try:
            # 将6位代码转为 xtdata 格式（如 300750 -> 300750.SZ）
            # 不传 symbols 时用市场代码 ['SH', 'SZ'] 获取沪深全市场行情
            xt_codes = []
            if symbols:
                for s in symbols:
                    code = _normalize_code(str(s).strip())
                    if code:
                        xt_codes.append(code)
            else:
                xt_codes = ["SH", "SZ", "BJ"]

            ticks = xt.get_full_tick(xt_codes)
            if not ticks or not isinstance(ticks, dict):
                return None
            # A股+ETF有效前缀：00/30/20(深市A股) 60/68(沪市A股) 8/4/9(北交所)
            # 50/51/52/56/58(沪市ETF) 15/16/18(深市ETF)
            # 排除债券等：10/11/12/13/18/19/7x 等
            _STOCK_ETF_PREFIXES = ("00", "30", "20", "60", "68", "50", "51", "52", "56", "58", "15", "16", "18", "8", "4", "9")

            result: Dict[str, Dict[str, Optional[float]]] = {}
            for xt_code, t in ticks.items():
                if t is None:
                    continue
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6:
                    continue
                if not code6.startswith(_STOCK_ETF_PREFIXES):
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
        1. 使用前需确保 QMT 已有所需数据
        2. 如果本地没有数据，先调用 download_history_data 下载
        3. 推荐使用 get_market_data_ex 接口
        """
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None
        _start = time.perf_counter()
        try:
            xt_code = _normalize_code(code)
            if not xt_code:
                self._record_quality("get_kline", False, "invalid_code")
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
                self._record_quality("get_kline", True, duration_ms=(time.perf_counter() - _start) * 1000)
                return items
            self._record_quality("get_kline", False, "no_data_format")
            return None
        except Exception as e:
            logger.error(f"QMT: get_kline 失败: {e}", exc_info=True)
            self._record_quality("get_kline", False, str(e)[:200], (time.perf_counter() - _start) * 1000)
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

    # ==================== 大盘/行业分析辅助接口 ====================

    @staticmethod
    def _is_market_session() -> bool:
        """判断当前是否在A股交易时段（含收盘后30分钟缓冲期）。"""
        try:
            from app.utils.trading_time import is_trading_time
            return is_trading_time()
        except Exception:
            # 无法判断时，保守返回 True，让实时快照先尝试
            return True

    def get_limit_stats(self, trade_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取涨跌停统计（优先实时快照，盘后自动切换历史日线）

        Args:
            trade_date: 交易日期（格式 YYYY-MM-DD 或 YYYYMMDD），为空则取最近交易日

        Returns:
            dict: {
                "up_limit": 涨停数,
                "down_limit": 跌停数,
                "rising": 上涨数,
                "falling": 下跌数,
                "flat": 平盘数,
                "total": 总数,
                "up_limit_stocks": [(code, name, pct), ...],  # 涨停股前20
                "down_limit_stocks": [(code, name, pct), ...],  # 跌停股前20
                "source": "realtime" | "history",
            }
        """
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None

        # 盘后/休市直接走历史日线，避免无效的实时快照请求
        if not self._is_market_session():
            logger.info("QMT: 当前非交易时段，直接使用历史日线回算涨跌停")
            result = self._get_limit_stats_history(xt, trade_date)
            if result:
                result["source"] = "history"
            return result

        # 盘中先尝试实时快照
        result = self._get_limit_stats_realtime(xt)
        if result and result.get("total", 0) > 0:
            result["source"] = "realtime"
            return result

        # 实时快照无数据，切换到历史日线
        logger.info("QMT: 实时快照无涨跌停数据，切换到历史日线回算")
        result = self._get_limit_stats_history(xt, trade_date)
        if result:
            result["source"] = "history"
        return result

    def _get_limit_stats_realtime(self, xt) -> Optional[Dict[str, Any]]:
        """基于实时快照的涨跌停统计。"""
        try:
            ticks = xt.get_full_tick(["SH", "SZ", "BJ"])
            if not ticks or not isinstance(ticks, dict):
                return None

            _STOCK_PREFIXES = ("00", "30", "20", "60", "68", "8", "4")
            _EXCLUDE_PREFIXES = ("000", "399", "899", "204", "1318")

            up_limit_stocks = []
            down_limit_stocks = []
            rising = 0
            falling = 0
            flat = 0

            for xt_code, t in ticks.items():
                if t is None:
                    continue
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6 or not code6.startswith(_STOCK_PREFIXES):
                    continue
                if code6.startswith(_EXCLUDE_PREFIXES):
                    continue

                last_price = getattr(t, "lastPrice", None) or (t.get("lastPrice") if isinstance(t, dict) else None)
                pct = getattr(t, "pctChange", None) or (t.get("pctChange") if isinstance(t, dict) else None)
                up_stop = getattr(t, "upStopPrice", None) or (t.get("upStopPrice") if isinstance(t, dict) else None)
                down_stop = getattr(t, "downStopPrice", None) or (t.get("downStopPrice") if isinstance(t, dict) else None)

                if last_price is None or pct is None:
                    continue

                try:
                    last_price = float(last_price)
                    pct = float(pct)
                    up_stop = float(up_stop) if up_stop is not None else None
                    down_stop = float(down_stop) if down_stop is not None else None
                except (ValueError, TypeError):
                    continue

                is_up_limit = self._check_up_limit(code6, pct, last_price, up_stop)
                is_down_limit = self._check_down_limit(code6, pct, last_price, down_stop)

                if is_up_limit:
                    name = self._get_instrument_name(xt, xt_code, code6)
                    up_limit_stocks.append((code6, name, pct))
                elif is_down_limit:
                    name = self._get_instrument_name(xt, xt_code, code6)
                    down_limit_stocks.append((code6, name, pct))
                elif pct > 0:
                    rising += 1
                elif pct < 0:
                    falling += 1
                else:
                    flat += 1

            return {
                "up_limit": len(up_limit_stocks),
                "down_limit": len(down_limit_stocks),
                "rising": rising,
                "falling": falling,
                "flat": flat,
                "total": len(up_limit_stocks) + len(down_limit_stocks) + rising + falling + flat,
                "up_limit_stocks": sorted(up_limit_stocks, key=lambda x: x[2], reverse=True)[:20],
                "down_limit_stocks": sorted(down_limit_stocks, key=lambda x: x[2])[:20],
            }
        except Exception as e:
            logger.error(f"QMT: 实时快照涨跌停统计失败: {e}")
            return None

    def _get_limit_stats_history(self, xt, trade_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """基于历史日线的涨跌停统计（盘后降级）。"""
        try:
            # 获取沪深A股列表
            stock_list = xt.get_stock_list_in_sector("沪深A股")
            if not stock_list:
                return None

            # 直接用 get_market_data_ex + count=1 获取最近一条日线
            # 不需要 download_history_data2，QMT 本地缓存已有数据
            stock_codes = list(stock_list)

            # 分批获取（每批1000只，避免内存问题）
            batch_size = 1000
            all_rows = []  # [(code6, name, close, preClose, pct)]

            for i in range(0, len(stock_codes), batch_size):
                batch = stock_codes[i:i + batch_size]
                try:
                    data = xt.get_market_data_ex([], batch, "1d", count=1)
                except Exception:
                    continue

                if not data:
                    continue

                for xt_code, df in data.items():
                    if df is None or df.empty:
                        continue
                    code6 = _code_to_6digit(xt_code)
                    if len(code6) != 6:
                        continue

                    row = df.iloc[-1]
                    close = row.get("close")
                    pre_close = row.get("preClose")
                    suspend = row.get("suspendFlag", 0)

                    if close is None or pre_close is None or pre_close == 0:
                        continue
                    if suspend and int(suspend) != 0:
                        continue

                    try:
                        close = float(close)
                        pre_close = float(pre_close)
                    except (ValueError, TypeError):
                        continue

                    pct = (close - pre_close) / pre_close * 100
                    name = self._get_instrument_name(xt, xt_code, code6)
                    all_rows.append((code6, name, close, pre_close, pct))

            if not all_rows:
                return None

            up_limit_stocks = []
            down_limit_stocks = []
            rising = 0
            falling = 0
            flat = 0

            for code6, name, close, pre_close, pct in all_rows:
                # 用 close / pre_close 判断是否触及涨跌停价
                up_stop = round(pre_close * 1.1, 2) if code6.startswith(("60", "00")) else \
                          round(pre_close * 1.2, 2) if code6.startswith(("30", "68")) else \
                          round(pre_close * 1.3, 2) if code6.startswith(("8", "4")) else None
                down_stop = round(pre_close * 0.9, 2) if code6.startswith(("60", "00")) else \
                            round(pre_close * 0.8, 2) if code6.startswith(("30", "68")) else \
                            round(pre_close * 0.7, 2) if code6.startswith(("8", "4")) else None

                is_up_limit = False
                if up_stop and close >= up_stop:
                    is_up_limit = True
                elif pct >= 9.9 and code6.startswith(("60", "00")):
                    is_up_limit = True
                elif pct >= 19.9 and code6.startswith(("30", "68")):
                    is_up_limit = True
                elif pct >= 29.9 and code6.startswith(("8", "4")):
                    is_up_limit = True

                is_down_limit = False
                if down_stop and close <= down_stop:
                    is_down_limit = True
                elif pct <= -9.9 and code6.startswith(("60", "00")):
                    is_down_limit = True
                elif pct <= -19.9 and code6.startswith(("30", "68")):
                    is_down_limit = True
                elif pct <= -29.9 and code6.startswith(("8", "4")):
                    is_down_limit = True

                if is_up_limit:
                    up_limit_stocks.append((code6, name, pct))
                elif is_down_limit:
                    down_limit_stocks.append((code6, name, pct))
                elif pct > 0:
                    rising += 1
                elif pct < 0:
                    falling += 1
                else:
                    flat += 1

            return {
                "up_limit": len(up_limit_stocks),
                "down_limit": len(down_limit_stocks),
                "rising": rising,
                "falling": falling,
                "flat": flat,
                "total": len(up_limit_stocks) + len(down_limit_stocks) + rising + falling + flat,
                "up_limit_stocks": sorted(up_limit_stocks, key=lambda x: x[2], reverse=True)[:20],
                "down_limit_stocks": sorted(down_limit_stocks, key=lambda x: x[2])[:20],
            }
        except Exception as e:
            logger.error(f"QMT: 历史日线涨跌停统计失败: {e}")
            return None

    @staticmethod
    def _check_up_limit(code6: str, pct: float, last_price: float, up_stop: Optional[float]) -> bool:
        """判断是否涨停。"""
        if up_stop and up_stop > 0 and last_price >= up_stop * 0.998:
            return True
        if pct >= 9.9 and code6.startswith(("60", "00")):
            return True
        if pct >= 19.9 and code6.startswith(("30", "68")):
            return True
        if pct >= 29.9 and code6.startswith(("8", "4")):
            return True
        return False

    @staticmethod
    def _check_down_limit(code6: str, pct: float, last_price: float, down_stop: Optional[float]) -> bool:
        """判断是否跌停。"""
        if down_stop and down_stop > 0 and last_price <= down_stop * 1.002:
            return True
        if pct <= -9.9 and code6.startswith(("60", "00")):
            return True
        if pct <= -19.9 and code6.startswith(("30", "68")):
            return True
        if pct <= -29.9 and code6.startswith(("8", "4")):
            return True
        return False

    @staticmethod
    def _get_instrument_name(xt, xt_code: str, code6: str) -> str:
        """获取股票名称。"""
        try:
            detail = xt.get_instrument_detail(xt_code)
            if detail and isinstance(detail, dict):
                return detail.get("InstrumentName", code6)
        except Exception:
            pass
        return code6

    def get_amount_ranking(self, top_n: int = 20, trade_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """获取成交额排名（优先实时快照，盘后自动切换历史日线）

        Args:
            top_n: 返回前N只
            trade_date: 交易日期（格式 YYYY-MM-DD 或 YYYYMMDD），为空则取最近交易日

        Returns:
            list: [{"code": str, "name": str, "amount": float, "pct_chg": float}, ...]
        """
        if not self.is_available():
            return None
        xt = _get_xtdata()
        if xt is None:
            return None

        # 盘后/休市直接走历史日线
        if not self._is_market_session():
            logger.info("QMT: 当前非交易时段，直接使用历史日线获取成交额排名")
            return self._get_amount_ranking_history(xt, top_n, trade_date)

        # 盘中先尝试实时快照
        result = self._get_amount_ranking_realtime(xt, top_n)
        # 如果实时快照返回了数据但涨跌幅缺失过多（盘后快照残留），走历史降级
        if result:
            missing_pct = sum(1 for r in result if r.get("pct_chg") is None)
            if missing_pct > len(result) * 0.5:
                logger.info("QMT: 实时快照涨跌幅缺失过多，切换到历史日线")
                result = self._get_amount_ranking_history(xt, top_n, trade_date)
        if result:
            return result

        # 盘后降级：历史日线
        logger.info("QMT: 实时快照无成交额数据，切换到历史日线")
        return self._get_amount_ranking_history(xt, top_n, trade_date)

    def _get_amount_ranking_realtime(self, xt, top_n: int) -> Optional[List[Dict[str, Any]]]:
        """基于实时快照的成交额排名。"""
        try:
            ticks = xt.get_full_tick(["SH", "SZ", "BJ"])
            if not ticks or not isinstance(ticks, dict):
                return None

            _STOCK_PREFIXES = ("00", "30", "20", "60", "68", "8", "4")
            _EXCLUDE_PREFIXES = ("000", "399", "899", "204", "1318")
            rows = []

            for xt_code, t in ticks.items():
                if t is None:
                    continue
                code6 = _code_to_6digit(xt_code)
                if len(code6) != 6 or not code6.startswith(_STOCK_PREFIXES):
                    continue
                if code6.startswith(_EXCLUDE_PREFIXES):
                    continue

                amt = getattr(t, "amount", None) or (t.get("amount") if isinstance(t, dict) else None)
                pct = getattr(t, "pctChange", None) or (t.get("pctChange") if isinstance(t, dict) else None)

                if amt is None:
                    continue
                try:
                    amt = float(amt)
                    pct = float(pct) if pct is not None else None
                except (ValueError, TypeError):
                    continue

                # 过滤掉成交额为0的（盘后快照残留）
                if amt <= 0:
                    continue

                name = self._get_instrument_name(xt, xt_code, code6)
                rows.append({"code": code6, "name": name, "amount": amt, "pct_chg": pct})

            if not rows:
                return None
            rows.sort(key=lambda x: x["amount"], reverse=True)
            return rows[:top_n]
        except Exception as e:
            logger.error(f"QMT: 实时快照成交额排名失败: {e}")
            return None

    def _get_amount_ranking_history(self, xt, top_n: int, trade_date: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """基于历史日线的成交额排名（盘后降级）。"""
        try:
            stock_list = xt.get_stock_list_in_sector("沪深A股")
            if not stock_list:
                return None

            stock_codes = list(stock_list)
            batch_size = 1000
            rows = []

            for i in range(0, len(stock_codes), batch_size):
                batch = stock_codes[i:i + batch_size]
                try:
                    data = xt.get_market_data_ex([], batch, "1d", count=1)
                except Exception:
                    continue

                if not data:
                    continue

                for xt_code, df in data.items():
                    if df is None or df.empty:
                        continue
                    code6 = _code_to_6digit(xt_code)
                    if len(code6) != 6:
                        continue

                    row = df.iloc[-1]
                    amt = row.get("amount")
                    close = row.get("close")
                    pre_close = row.get("preClose")
                    suspend = row.get("suspendFlag", 0)

                    if amt is None or close is None or pre_close is None or pre_close == 0:
                        continue
                    if suspend and int(suspend) != 0:
                        continue

                    try:
                        amt = float(amt)
                        close = float(close)
                        pre_close = float(pre_close)
                    except (ValueError, TypeError):
                        continue

                    if amt <= 0:
                        continue

                    pct = (close - pre_close) / pre_close * 100
                    name = self._get_instrument_name(xt, xt_code, code6)
                    rows.append({"code": code6, "name": name, "amount": amt, "pct_chg": pct})

            if not rows:
                return None
            rows.sort(key=lambda x: x["amount"], reverse=True)
            return rows[:top_n]
        except Exception as e:
            logger.error(f"QMT: 历史日线成交额排名失败: {e}")
            return None

