"""
动态映射配置加载器

从 config/mappings/ 目录加载 YAML 配置文件，支持：
- 缓存与 TTL 过期
- 基于文件修改时间的热重载
- 配置文件缺失时回退到内置默认值
- 线程安全的读取
"""

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_MAPPINGS_DIR = _PROJECT_ROOT / "config" / "mappings"

# 缓存 TTL（秒）
_CACHE_TTL = 300  # 5 分钟


class MappingLoader:
    """动态映射配置加载器"""

    def __init__(
        self,
        mappings_dir: Optional[Path] = None,
        cache_ttl: int = _CACHE_TTL,
    ):
        self._mappings_dir = mappings_dir or _DEFAULT_MAPPINGS_DIR
        self._cache_ttl = cache_ttl
        self._lock = threading.Lock()
        # cache key -> (data, file_mtime, load_time)
        self._cache: Dict[str, tuple] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, filename: str, key: str, default: Any = None) -> Any:
        """获取指定配置文件中的某个键值。

        Args:
            filename: 配置文件名（不含扩展名），如 ``"provider_mappings"``
            key: 配置键名
            default: 键不存在时的默认值

        Returns:
            配置值，或 *default*
        """
        data = self.load(filename)
        return data.get(key, default)

    def load(self, filename: str) -> Dict[str, Any]:
        """加载整个配置文件并返回其字典内容。

        带缓存：同一文件在 TTL 内只读取一次，文件修改时间变化时自动重载。
        """
        cache_key = filename
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                data, mtime, load_time = cached
                if time.time() - load_time < self._cache_ttl:
                    return data

        # 在锁外执行 I/O，避免长时间持锁
        file_path = self._resolve_path(filename)
        data, mtime = self._load_file(file_path)

        with self._lock:
            # 双重检查：另一个线程可能已经更新了缓存
            existing = self._cache.get(cache_key)
            if existing is not None and existing[1] >= mtime and time.time() - existing[2] < self._cache_ttl:
                return existing[0]
            self._cache[cache_key] = (data, mtime, time.time())

        return data

    def reload(self, filename: Optional[str] = None) -> None:
        """强制清除缓存，下次访问时重新加载。

        Args:
            filename: 指定文件名清除对应缓存；为 None 时清除所有缓存。
        """
        with self._lock:
            if filename is None:
                self._cache.clear()
            else:
                self._cache.pop(filename, None)

    def list_files(self) -> list:
        """列出所有可用的映射配置文件名（不含扩展名）。"""
        if not self._mappings_dir.is_dir():
            return []
        return sorted(
            p.stem for p in self._mappings_dir.glob("*.yaml")
        )

    # ------------------------------------------------------------------
    # Convenience methods for commonly used mappings
    # ------------------------------------------------------------------

    def get_llm_provider_names(self) -> Dict[str, str]:
        return self.get("provider_mappings", "llm_provider_names", {})

    def get_data_source_names(self) -> Dict[str, str]:
        return self.get("provider_mappings", "data_source_names", {})

    def get_llm_env_key_mapping(self) -> Dict[str, str]:
        return self.get("provider_mappings", "llm_env_key_mapping", {})

    def get_data_source_env_key_mapping(self) -> Dict[str, str]:
        return self.get("provider_mappings", "data_source_env_key_mapping", {})

    def get_model_prefixes(self) -> Dict[str, str]:
        return self.get("provider_mappings", "model_prefixes", {})

    def get_model_provider_map(self) -> Dict[str, str]:
        return self.get("provider_mappings", "model_provider_map", {})

    def get_provider_normalization(self) -> Dict[str, str]:
        return self.get("provider_mappings", "provider_normalization", {})

    def get_aggregator_providers(self) -> Dict[str, Any]:
        return self.get("provider_mappings", "aggregator_providers", {})

    def get_market_category_map(self) -> Dict[str, str]:
        return self.get("market_mappings", "market_category_map", {})

    def get_market_type_names(self) -> Dict[str, str]:
        return self.get("market_mappings", "market_type_names", {})

    def get_market_currency_map(self) -> Dict[str, str]:
        return self.get("market_mappings", "market_currency_map", {})

    def get_initial_cash_by_market(self) -> Dict[str, float]:
        return self.get("market_mappings", "initial_cash_by_market", {})

    def get_data_source_priority(self) -> Dict[str, list]:
        return self.get("market_mappings", "data_source_priority", {})

    def get_period_map(self, source: str = "yahoo") -> Dict[str, str]:
        """获取周期映射。

        Args:
            source: 数据源类型，"yahoo" | "akshare" | "tushare"
        """
        key = f"period_map_{source}"
        return self.get("market_mappings", key, {})

    def get_adjust_map(self) -> Dict[str, str]:
        return self.get("market_mappings", "adjust_map", {})

    def get_cache_ttl_config(self) -> Dict[str, Dict[str, int]]:
        return self.get("market_mappings", "cache_ttl", {})

    def get_tushare_rate_limits(self) -> Dict[str, Dict[str, int]]:
        return self.get("market_mappings", "tushare_rate_limits", {})

    def get_numeric_to_depth(self) -> Dict[int, str]:
        return self.get("analysis_mappings", "numeric_to_depth", {})

    def get_depth_to_numeric(self) -> Dict[str, int]:
        return self.get("analysis_mappings", "depth_to_numeric", {})

    def get_analyst_steps(self) -> Dict[str, Dict[str, str]]:
        return self.get("analysis_mappings", "analyst_steps", {})

    def get_base_time_per_depth(self) -> Dict[int, int]:
        return self.get("analysis_mappings", "base_time_per_depth", {})

    def get_model_time_multiplier(self) -> Dict[str, float]:
        return self.get("analysis_mappings", "model_time_multiplier", {})

    def get_depth_time_multiplier(self) -> Dict[int, float]:
        return self.get("analysis_mappings", "depth_time_multiplier", {})

    def get_action_translation(self) -> Dict[str, str]:
        return self.get("analysis_mappings", "action_translation", {})

    def get_status_mapping(self) -> Dict[str, str]:
        return self.get("analysis_mappings", "status_mapping", {})

    def get_http_method_names(self) -> Dict[str, str]:
        return self.get("analysis_mappings", "http_method_names", {})

    def get_module_titles(self) -> Dict[str, str]:
        return self.get("ui_mappings", "module_titles", {})

    def get_capability_badges(self) -> Dict[int, Dict[str, str]]:
        return self.get("ui_mappings", "capability_badges", {})

    def get_role_badges(self) -> Dict[str, Dict[str, str]]:
        return self.get("ui_mappings", "role_badges", {})

    def get_feature_badges(self) -> Dict[str, Dict[str, str]]:
        return self.get("ui_mappings", "feature_badges", {})

    def get_sensitive_keys(self) -> list:
        return self.get("ui_mappings", "sensitive_keys", [])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, filename: str) -> Path:
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            return self._mappings_dir / filename
        return self._mappings_dir / f"{filename}.yaml"

    def _load_file(self, file_path: Path) -> tuple:
        """加载 YAML 文件，返回 (data, mtime)。文件不存在时返回空字典。"""
        if not file_path.is_file():
            logger.warning("映射配置文件不存在: %s，使用空配置", file_path)
            return {}, 0.0
        try:
            mtime = file_path.stat().st_mtime
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data is None:
                data = {}
            return data, mtime
        except Exception as e:
            logger.error("加载映射配置文件失败 %s: %s", file_path, e)
            return {}, 0.0


# 全局单例
_mapping_loader: Optional[MappingLoader] = None
_init_lock = threading.Lock()


def get_mapping_loader() -> MappingLoader:
    """获取全局映射加载器单例。"""
    global _mapping_loader
    if _mapping_loader is None:
        with _init_lock:
            if _mapping_loader is None:
                _mapping_loader = MappingLoader()
    return _mapping_loader
