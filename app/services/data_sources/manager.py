"""
Data source manager that orchestrates multiple adapters with priority and optional consistency checks
"""
from typing import List, Optional, Tuple, Dict
import logging
import time
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter
from .local_adapter import LocalAdapter
from .tushare_adapter import TushareAdapter
from .akshare_adapter import AKShareAdapter
from .baostock_adapter import BaoStockAdapter
from .qmt_adapter import QMTAdapter

logger = logging.getLogger(__name__)


class DataSourceManager:
    """
    数据源管理器
    - 管理多个适配器，基于优先级排序
    - 提供 fallback 获取能力
    - 可选：一致性检查（若依赖存在）
    """

    def __init__(self):
        self._configured_enabled_map: Dict[str, bool] = {}
        self.adapters: List[DataSourceAdapter] = [
            LocalAdapter(),      # 本地数据源（用户通过API导入）
            TushareAdapter(),
            AKShareAdapter(),
            BaoStockAdapter(),
            QMTAdapter(),        # 迅投 QMT（需 QMT 运行，新闻用 AKShare）
        ]

        # 使用统一的数据源优先级模块加载配置
        self._load_priority_from_unified_config()

        # 按优先级排序（数字越大优先级越高，所以降序排列）
        self.adapters.sort(key=lambda x: x.priority, reverse=True)

        try:
            from .data_consistency_checker import DataConsistencyChecker  # type: ignore
            self.consistency_checker = DataConsistencyChecker()
        except Exception:
            logger.warning("⚠️ 数据一致性检查器不可用")
            self.consistency_checker = None

    def _load_priority_from_unified_config(self):
        """使用统一配置模块加载数据源优先级"""
        try:
            from app.core.unified_config import UnifiedConfigManager

            config = UnifiedConfigManager()
            data_source_configs = config.get_data_source_configs()

            # 创建名称到优先级的映射
            priority_map = {}
            for ds_config in data_source_configs:
                data_source_name = ds_config.type.lower()
                priority = ds_config.priority
                enabled = ds_config.enabled

                self._configured_enabled_map[data_source_name] = bool(enabled)

                if enabled:
                    priority_map[data_source_name] = priority

            # 🔥 强制 .env 开关覆盖（.env 优先级最高，无视数据库缓存）
            self._apply_dotenv_overrides()

            # 更新各个 Adapter 的优先级
            for adapter in self.adapters:
                if adapter.name in priority_map:
                    adapter._priority = priority_map[adapter.name]
                else:
                    adapter._priority = adapter._get_default_priority()

        except Exception as e:
            logger.warning(f"⚠️ 从统一配置加载优先级失败: {e}，使用默认优先级")
            import traceback
            logger.warning(f"堆栈跟踪:\n{traceback.format_exc()}")
            # 使用默认优先级
            for adapter in self.adapters:
                adapter._priority = adapter._get_default_priority()

    def _apply_dotenv_overrides(self):
        """强制应用 .env 中的数据源开关（最高优先级）

        通过 Pydantic BaseSettings 读取 .env 中显式设置的值。
        多个 key 按优先级排列，第一个被显式设置的值生效。
        """
        try:
            from app.core.config import settings as runtime_settings

            # 按优先级排列：用户实际在 .env 中设置的 key 放前面
            env_overrides = {
                "baostock": ["BAOSTOCK_UNIFIED_ENABLED", "ENABLE_BAOSTOCK"],
                "tushare": ["ENABLE_TUSHARE"],
            }

            for adapter_name, env_keys in env_overrides.items():
                effective_key = None
                env_val = None

                for key in env_keys:
                    val = getattr(runtime_settings, key, None)

                    # 只有当值为 False（禁用）时才覆盖。
                    # True 可能是 Pydantic 默认值，不要用默认 True 去覆盖数据库的 False。
                    if val is False:
                        env_val = False
                        effective_key = key
                        break

                if effective_key:
                    old_val = self._configured_enabled_map.get(adapter_name)
                    self._configured_enabled_map[adapter_name] = env_val
                    logger.info(f"🔧 [DataSourceManager] .env 禁用 ({effective_key}): {adapter_name} enabled=False (原={old_val})")
        except Exception as e:
            logger.warning(f"⚠️ [DataSourceManager] .env 覆盖失败: {e}")

    def get_available_adapters(self) -> List[DataSourceAdapter]:
        available: List[DataSourceAdapter] = []
        for adapter in self.adapters:
            if self._configured_enabled_map.get(adapter.name) is False:
                logger.info(f"Data source {adapter.name} is disabled in unified config, skipping availability probe")
                continue

            if adapter.is_available():
                available.append(adapter)
                logger.info(
                    f"Data source {adapter.name} is available (priority: {adapter.priority})"
                )
            else:
                log_message = f"Data source {adapter.name} is not available"
                if adapter.name == "qmt":
                    logger.info(log_message)
                else:
                    logger.warning(log_message)
        return available

    def get_stock_list_with_fallback(self, preferred_sources: Optional[List[str]] = None, exclude_local: bool = False) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        获取股票列表，支持指定优先数据源

        Args:
            preferred_sources: 优先使用的数据源列表，例如 ['akshare', 'baostock']
                             如果为 None，则按照默认优先级顺序
            exclude_local: 是否排除本地数据源（同步操作时应设为 True）

        Returns:
            (DataFrame, source_name) 或 (None, None)
        """
        available_adapters = self.get_available_adapters()

        # 排除本地数据源（用于同步操作）
        if exclude_local:
            available_adapters = [a for a in available_adapters if a.name != 'local']
            logger.info("🚫 排除本地数据源（local），仅使用外部数据源进行同步")

        # 如果指定了优先数据源，重新排序
        if preferred_sources:
            logger.info(f"Using preferred data sources: {preferred_sources}")
            # 创建优先级映射
            priority_map = {name: idx for idx, name in enumerate(preferred_sources)}
            # 将指定的数据源排在前面，其他的保持原顺序
            preferred = [a for a in available_adapters if a.name in priority_map]
            others = [a for a in available_adapters if a.name not in priority_map]
            # 按照 preferred_sources 的顺序排序
            preferred.sort(key=lambda a: priority_map.get(a.name, 999))
            available_adapters = preferred + others
            logger.info(f"Reordered adapters: {[a.name for a in available_adapters]}")

        for adapter in available_adapters:
            try:
                adapter_start = time.perf_counter()
                logger.info(f"Trying to fetch stock list from {adapter.name}")
                df = adapter.get_stock_list()
                if df is not None and not df.empty:
                    logger.info(
                        "Stock list fetch succeeded from %s: records=%s elapsed=%.2fs",
                        adapter.name,
                        len(df),
                        time.perf_counter() - adapter_start,
                    )
                    return df, adapter.name
                logger.warning(
                    "Stock list fetch returned empty from %s after %.2fs",
                    adapter.name,
                    time.perf_counter() - adapter_start,
                )
            except Exception as e:
                logger.error(
                    "Failed to fetch stock list from %s after %.2fs: %s",
                    adapter.name,
                    time.perf_counter() - adapter_start,
                    e,
                )
                continue
        return None, None

    def get_daily_basic_with_fallback(self, trade_date: str, preferred_sources: Optional[List[str]] = None) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        获取每日基础数据，支持指定优先数据源

        Args:
            trade_date: 交易日期
            preferred_sources: 优先使用的数据源列表

        Returns:
            (DataFrame, source_name) 或 (None, None)
        """
        available_adapters = self.get_available_adapters()

        # 如果指定了优先数据源，重新排序
        if preferred_sources:
            priority_map = {name: idx for idx, name in enumerate(preferred_sources)}
            preferred = [a for a in available_adapters if a.name in priority_map]
            others = [a for a in available_adapters if a.name not in priority_map]
            preferred.sort(key=lambda a: priority_map.get(a.name, 999))
            available_adapters = preferred + others

        for adapter in available_adapters:
            try:
                logger.info(f"Trying to fetch daily basic data from {adapter.name}")
                df = adapter.get_daily_basic(trade_date)
                if df is not None and not df.empty:
                    return df, adapter.name
            except Exception as e:
                logger.error(f"Failed to fetch daily basic data from {adapter.name}: {e}")
                continue
        return None, None

    def find_latest_trade_date_with_fallback(self, preferred_sources: Optional[List[str]] = None) -> Optional[str]:
        """
        查找最新交易日期，支持指定优先数据源

        Args:
            preferred_sources: 优先使用的数据源列表

        Returns:
            交易日期字符串（YYYYMMDD格式）或 None
        """
        available_adapters = self.get_available_adapters()

        # 如果指定了优先数据源，重新排序
        if preferred_sources:
            priority_map = {name: idx for idx, name in enumerate(preferred_sources)}
            preferred = [a for a in available_adapters if a.name in priority_map]
            others = [a for a in available_adapters if a.name not in priority_map]
            preferred.sort(key=lambda a: priority_map.get(a.name, 999))
            available_adapters = preferred + others

        for adapter in available_adapters:
            try:
                trade_date = adapter.find_latest_trade_date()
                if trade_date:
                    return trade_date
            except Exception as e:
                logger.error(f"Failed to find trade date from {adapter.name}: {e}")
                continue
        return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    def get_realtime_quotes_with_fallback(self) -> Tuple[Optional[Dict], Optional[str]]:
        """
        获取全市场实时快照，按适配器优先级依次尝试，返回首个成功结果
        Returns: (quotes_dict, source_name)
        quotes_dict 形如 { '000001': {'close': 10.0, 'pct_chg': 1.2, 'amount': 1.2e8}, ... }
        """
        available_adapters = self.get_available_adapters()
        for adapter in available_adapters:
            try:
                logger.info(f"Trying to fetch realtime quotes from {adapter.name}")
                data = adapter.get_realtime_quotes()
                if data:
                    return data, adapter.name
            except Exception as e:
                logger.error(f"Failed to fetch realtime quotes from {adapter.name}: {e}")
                continue
        return None, None


    def get_daily_basic_with_consistency_check(
        self, trade_date: str
    ) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[Dict]]:
        """
        使用一致性检查获取每日基础数据

        Returns:
            Tuple[DataFrame, source_name, consistency_report]
        """
        available_adapters = self.get_available_adapters()
        if len(available_adapters) < 2:
            df, source = self.get_daily_basic_with_fallback(trade_date)
            return df, source, None
        primary_adapter = available_adapters[0]
        secondary_adapter = available_adapters[1]
        try:
            logger.info(
                f"🔍 获取数据进行一致性检查: {primary_adapter.name} vs {secondary_adapter.name}"
            )
            primary_data = primary_adapter.get_daily_basic(trade_date)
            secondary_data = secondary_adapter.get_daily_basic(trade_date)
            if primary_data is None or primary_data.empty:
                logger.warning(f"⚠️ 主数据源{primary_adapter.name}失败，使用fallback")
                df, source = self.get_daily_basic_with_fallback(trade_date)
                return df, source, None
            if secondary_data is None or secondary_data.empty:
                logger.warning(f"⚠️ 次数据源{secondary_adapter.name}失败，使用主数据源")
                return primary_data, primary_adapter.name, None
            if self.consistency_checker:
                consistency_result = self.consistency_checker.check_daily_basic_consistency(
                    primary_data,
                    secondary_data,
                    primary_adapter.name,
                    secondary_adapter.name,
                )
                final_data, resolution_strategy = self.consistency_checker.resolve_data_conflicts(
                    primary_data, secondary_data, consistency_result
                )
                consistency_report = {
                    'is_consistent': consistency_result.is_consistent,
                    'confidence_score': consistency_result.confidence_score,
                    'recommended_action': consistency_result.recommended_action,
                    'resolution_strategy': resolution_strategy,
                    'differences': consistency_result.differences,
                    'primary_source': primary_adapter.name,
                    'secondary_source': secondary_adapter.name,
                }
                logger.info(
                    f"📊 数据一致性检查完成: 置信度={consistency_result.confidence_score:.2f}, 策略={consistency_result.recommended_action}"
                )
                return final_data, primary_adapter.name, consistency_report
            else:
                logger.warning("⚠️ 一致性检查器不可用，使用主数据源")
                return primary_data, primary_adapter.name, None
        except Exception as e:
            logger.error(f"❌ 一致性检查失败: {e}")
            df, source = self.get_daily_basic_with_fallback(trade_date)
            return df, source, None



    def get_kline_with_fallback(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """按优先级尝试获取K线，返回(items, source)"""
        available_adapters = self.get_available_adapters()
        for adapter in available_adapters:
            try:
                logger.info(f"Trying to fetch kline from {adapter.name}")
                items = adapter.get_kline(code=code, period=period, limit=limit, adj=adj)
                if items:
                    return items, adapter.name
            except Exception as e:
                logger.error(f"Failed to fetch kline from {adapter.name}: {e}")
                continue
        return None, None

    def get_news_with_fallback(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """按优先级尝试获取新闻与公告，返回(items, source)"""
        available_adapters = self.get_available_adapters()
        for adapter in available_adapters:
            try:
                logger.info(f"Trying to fetch news from {adapter.name}")
                items = adapter.get_news(code=code, days=days, limit=limit, include_announcements=include_announcements)
                if items:
                    return items, adapter.name
            except Exception as e:
                logger.error(f"Failed to fetch news from {adapter.name}: {e}")
                continue
        return None, None

    def get_daily_ohlc_with_fallback(self, code: str, trade_date: str, adj: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        按优先级尝试获取指定日期的日线 OHLC 数据。

        Args:
            code: 6位股票代码
            trade_date: 交易日期，格式 YYYY-MM-DD 或 YYYYMMDD
            adj: 复权方式，None=不复权，"qfq"=前复权，"hfq"=后复权

        Returns:
            (ohlc_dict, source_name) 或 (None, None)
            ohlc_dict: {"date", "open", "high", "low", "close"}
        """
        available_adapters = self.get_available_adapters()
        for adapter in available_adapters:
            try:
                logger.info(f"Trying to fetch daily OHLC from {adapter.name} (adj={adj})")
                ohlc = adapter.get_daily_ohlc(code=code, trade_date=trade_date, adj=adj)
                if ohlc:
                    return ohlc, adapter.name
            except Exception as e:
                logger.error(f"Failed to fetch daily OHLC from {adapter.name}: {e}")
                continue
        return None, None
