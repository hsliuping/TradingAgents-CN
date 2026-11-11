"""
P2 数据源管理体系收敛验证测试（方案一：委托式收敛）

验证点：
1. 两套 DataSourceManager（A: tradingagents/dataflows/data_source_manager.py，
   B: app/services/data_sources/manager.py）对同一优先级配置给出一致顺序
2. QMT（B 专属 SDK 数据源）的插入位置符合 B 的业务约定（紧随 akshare）
3. A 不感知 QMT（保持开源版/Pro 版分发约束：禁止 import core/pro/* 或 app/*）
4. 默认优先级唯一定义在 A，B 适配器默认值委托 A
5. 对外接口（公共方法）保持增量兼容
"""
import ast
from pathlib import Path
from types import SimpleNamespace

from tradingagents.dataflows import data_source_manager as dsm

PROJECT_ROOT = Path(__file__).resolve().parents[2]
A_SOURCE_PATH = PROJECT_ROOT / "tradingagents" / "dataflows" / "data_source_manager.py"

# .env/运行时强制开关（与 A 的 ENV_FORCE_DISABLE_KEYS 保持一致）
ENV_KEYS = ("BAOSTOCK_UNIFIED_ENABLED", "ENABLE_BAOSTOCK", "ENABLE_TUSHARE")

# 同一份优先级配置（priority 数字越大优先级越高）：期望顺序 baostock > akshare > tushare > local
BASE_CONFIGS = [
    {"name": "本地数据", "type": "local", "enabled": True, "priority": 1},
    {"name": "Tushare", "type": "tushare", "enabled": True, "priority": 2},
    {"name": "AKShare", "type": "akshare", "enabled": True, "priority": 3},
    {"name": "BaoStock", "type": "baostock", "enabled": True, "priority": 4},
]
EXPECTED_BASE_ORDER = ["baostock", "akshare", "tushare", "local"]


class _StubAdapter:
    """最小适配器替身（避免真实适配器构造副作用，如 TushareProvider 初始化）"""

    def __init__(self, name: str, default_priority: int):
        self.name = name
        self._priority = None
        self._default = default_priority

    @property
    def priority(self) -> int:
        return self._priority if self._priority is not None else self._default

    def _get_default_priority(self) -> int:
        return self._default


def _set_env(monkeypatch, env=None):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)


def _build_a(monkeypatch, configs, env=None):
    """构造 A 侧 DataSourceManager（绕过构造器副作用，注入同一份配置）"""
    import app.core.database as app_database

    _set_env(monkeypatch, env)
    monkeypatch.setattr(dsm, "load_data_source_configs", lambda: [dict(c) for c in configs])

    def _no_db():
        raise RuntimeError("tests: 禁止触达 MongoDB")

    monkeypatch.setattr(app_database, "get_mongo_db_sync", _no_db)

    mgr = dsm.DataSourceManager.__new__(dsm.DataSourceManager)
    mgr.available_sources = [
        dsm.ChinaDataSource.LOCAL,
        dsm.ChinaDataSource.TUSHARE,
        dsm.ChinaDataSource.AKSHARE,
        dsm.ChinaDataSource.BAOSTOCK,
    ]
    return mgr


def _a_order(monkeypatch, configs, env=None):
    mgr = _build_a(monkeypatch, configs, env)
    return [s.value for s in mgr.get_data_source_priority_order(None)]


def _build_b(monkeypatch, configs, env=None):
    """构造 B 侧 DataAdapterOrchestrator（注入同一份配置 + StubAdapter）"""
    from app.core.unified_config import UnifiedConfigManager
    from app.services.data_sources import manager as ds_manager_b

    env = env or {}
    monkeypatch.setattr(
        UnifiedConfigManager, "get_data_source_configs", lambda self: [dict(c) for c in configs]
    )
    monkeypatch.setattr(ds_manager_b, "_read_runtime_setting", lambda key: env.get(key))

    mgr = ds_manager_b.DataAdapterOrchestrator.__new__(ds_manager_b.DataAdapterOrchestrator)
    mgr._configured_enabled_map = {}
    mgr.adapters = [
        _StubAdapter("local", dsm.get_default_source_priority("local")),
        _StubAdapter("tushare", dsm.get_default_source_priority("tushare")),
        _StubAdapter("akshare", dsm.get_default_source_priority("akshare")),
        _StubAdapter("baostock", dsm.get_default_source_priority("baostock")),
        _StubAdapter("qmt", dsm.get_default_source_priority("akshare")),
    ]
    mgr._load_priority_from_unified_config()
    return mgr


def _b_order(monkeypatch, configs, env=None, include_qmt=False):
    """B 的有效顺序：adapters 按优先级排序后剔除配置/环境禁用的源（同 get_available_adapters 口径）"""
    mgr = _build_b(monkeypatch, configs, env)
    names = [
        a.name for a in mgr.adapters
        if mgr._configured_enabled_map.get(a.name) is not False
    ]
    return names if include_qmt else [n for n in names if n != "qmt"]


# ==================== 1. 两套 manager 顺序一致 ====================


def test_same_priority_config_same_order(monkeypatch):
    """同一优先级配置下，A、B 两套 manager 给出一致顺序"""
    a_order = _a_order(monkeypatch, BASE_CONFIGS)
    b_order = _b_order(monkeypatch, BASE_CONFIGS)
    assert a_order == EXPECTED_BASE_ORDER
    assert b_order == a_order


def test_disabled_source_consistent(monkeypatch):
    """配置中禁用的数据源，A、B 同时排除（tushare enabled=False）"""
    configs = [
        dict(c, enabled=False) if c["type"] == "tushare" else dict(c) for c in BASE_CONFIGS
    ]
    a_order = _a_order(monkeypatch, configs)
    b_order = _b_order(monkeypatch, configs)
    assert "tushare" not in a_order
    assert a_order == b_order == ["baostock", "akshare", "local"]


def test_env_force_disable_consistent(monkeypatch):
    """.env 显式 False 强制禁用，A、B 同时排除（baostock/tushare）"""
    env = {"BAOSTOCK_UNIFIED_ENABLED": "False", "ENABLE_TUSHARE": "0"}
    a_order = _a_order(monkeypatch, BASE_CONFIGS, env=env)
    b_order = _b_order(monkeypatch, BASE_CONFIGS, env=env)
    assert "baostock" not in a_order and "tushare" not in a_order
    assert a_order == b_order == ["akshare", "local"]


def test_unconfigured_sources_appended_consistent(monkeypatch):
    """配置缺失的已知数据源按默认优先级追加尾部，A、B 一致（保降级链）"""
    configs = [
        {"name": "本地数据", "type": "local", "enabled": True, "priority": 1},
        {"name": "AKShare", "type": "akshare", "enabled": True, "priority": 5},
    ]
    a_order = _a_order(monkeypatch, configs)
    b_order = _b_order(monkeypatch, configs)
    expected = ["akshare", "local", "tushare", "baostock"]
    assert a_order == expected
    assert b_order == a_order


def test_env_true_does_not_override_disabled_config(monkeypatch):
    """.env/运行时默认 True 不覆盖配置中的 enabled=False"""
    configs = [
        dict(c, enabled=False) if c["type"] == "baostock" else dict(c) for c in BASE_CONFIGS
    ]
    env = {"BAOSTOCK_UNIFIED_ENABLED": "True"}
    a_order = _a_order(monkeypatch, configs, env=env)
    b_order = _b_order(monkeypatch, configs, env=env)
    assert "baostock" not in a_order
    assert a_order == b_order == ["akshare", "tushare", "local"]


# ==================== 2. QMT 插入位置（B 的业务约定） ====================


def test_qmt_inserted_right_after_akshare(monkeypatch):
    """配置未声明 qmt 时：插入到 akshare 之后（与 AKShare 同级、紧随其后）"""
    order = _b_order(monkeypatch, BASE_CONFIGS, include_qmt=True)
    assert order == ["baostock", "akshare", "qmt", "tushare", "local"]


def test_qmt_config_position_respected(monkeypatch):
    """配置显式声明 qmt 优先级位置时以配置为准，不再二次插入"""
    configs = BASE_CONFIGS + [{"name": "QMT", "type": "qmt", "enabled": True, "priority": 10}]
    order = _b_order(monkeypatch, configs, include_qmt=True)
    assert order == ["qmt", "baostock", "akshare", "tushare", "local"]


def test_qmt_insert_rule_unit(monkeypatch):
    """_insert_qmt_source 业务约定：紧随 akshare；无 akshare 追加末尾；已存在/禁用不插入"""
    mgr = _build_b(monkeypatch, BASE_CONFIGS)
    mgr._configured_enabled_map = {"qmt": True}
    assert mgr._insert_qmt_source(["baostock", "akshare", "tushare"]) == [
        "baostock", "akshare", "qmt", "tushare",
    ]
    assert mgr._insert_qmt_source(["local", "tushare"]) == ["local", "tushare", "qmt"]
    assert mgr._insert_qmt_source(["qmt", "akshare"]) == ["qmt", "akshare"]
    mgr._configured_enabled_map = {"qmt": False}
    assert mgr._insert_qmt_source(["akshare", "tushare"]) == ["akshare", "tushare"]


# ==================== 3. A 不感知 QMT（分发约束） ====================


def test_a_unaware_of_qmt():
    """A 不得出现任何 QMT 代码/字符串，且不得 import core/pro/* 与 app/*（app.core.database 除外）"""
    src = A_SOURCE_PATH.read_text(encoding="utf-8")
    assert "qmt" not in src.lower(), "体系 A 不得感知 QMT（B 专属 SDK 数据源）"

    tree = ast.parse(src)
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 包内相对导入不限制
                continue
            modules = [node.module or ""]
        for mod in modules:
            assert not mod.startswith("core.pro"), f"A 禁止 import core/pro/*: {mod}"
            if mod == "app" or mod.startswith("app."):
                assert mod == "app.core.database", f"A 仅允许 app.core.database 惰性入口: {mod}"


def test_a_order_filters_qmt_from_config(monkeypatch):
    """即使配置里声明了 qmt，A 的降级链也不包含 qmt（未识别源被过滤）"""
    configs = BASE_CONFIGS + [{"name": "QMT", "type": "qmt", "enabled": True, "priority": 10}]
    a_order = _a_order(monkeypatch, configs)
    assert "qmt" not in a_order
    assert a_order == EXPECTED_BASE_ORDER


# ==================== 4. 默认优先级唯一定义在 A ====================


def test_default_priority_delegated_to_a():
    """B 各适配器的默认优先级委托 A 的 get_default_source_priority（值保持 10/3/2/1 不变）"""
    from app.services.data_sources.akshare_adapter import AKShareAdapter
    from app.services.data_sources.baostock_adapter import BaoStockAdapter
    from app.services.data_sources.local_adapter import LocalAdapter
    from app.services.data_sources.qmt_adapter import QMTAdapter
    from app.services.data_sources.tushare_adapter import TushareAdapter

    assert LocalAdapter._get_default_priority(None) == dsm.get_default_source_priority("local") == 10
    assert TushareAdapter._get_default_priority(None) == dsm.get_default_source_priority("tushare") == 3
    assert AKShareAdapter._get_default_priority(None) == dsm.get_default_source_priority("akshare") == 2
    assert BaoStockAdapter._get_default_priority(None) == dsm.get_default_source_priority("baostock") == 1
    # QMT 与 AKShare 同级（B 专属源，排序插入规则见 manager.QMT_INSERT_AFTER）
    assert QMTAdapter._get_default_priority(None) == dsm.get_default_source_priority("akshare")


def test_default_source_priority_is_single_source():
    """DEFAULT_SOURCE_PRIORITY 是默认顺序的唯一定义处"""
    assert dsm.DEFAULT_SOURCE_PRIORITY == {
        "local": 10, "tushare": 3, "akshare": 2, "baostock": 1,
    }
    assert dsm.get_default_source_priority("UNKNOWN") == 0


# ==================== 5. 对外接口增量兼容 ====================


def test_public_interfaces_unchanged():
    """两个 manager 的公共方法全部保留（不删除任何公共方法）"""
    from app.core import unified_config
    from app.services.data_sources import manager as ds_manager_b

    a_methods = [
        "get_data_source_priority_order",
        "_check_available_sources",
        "_get_datasource_configs_from_db",
    ]
    for name in a_methods:
        assert hasattr(dsm.DataSourceManager, name), f"A 丢失方法: {name}"

    b_methods = [
        "get_available_adapters",
        "get_stock_list_with_fallback",
        "get_daily_basic_with_fallback",
        "find_latest_trade_date_with_fallback",
        "get_realtime_quotes_with_fallback",
        "get_daily_basic_with_consistency_check",
        "get_kline_with_fallback",
        "get_news_with_fallback",
        "get_daily_ohlc_with_fallback",
        "_load_priority_from_unified_config",
        "_insert_qmt_source",
        "_apply_dotenv_overrides",
    ]
    for name in b_methods:
        assert hasattr(ds_manager_b.DataAdapterOrchestrator, name), f"B 丢失方法: {name}"
    assert ds_manager_b.DataAdapterOrchestrator.QMT_INSERT_AFTER == "akshare"

    # A 暴露的唯一事实源函数
    for name in (
        "DEFAULT_SOURCE_PRIORITY",
        "normalize_source_name",
        "get_default_source_priority",
        "resolve_env_forced_enabled",
        "resolve_enabled_source_map",
        "resolve_data_source_priority_order",
        "load_data_source_configs",
    ):
        assert hasattr(dsm, name), f"A 缺少事实源成员: {name}"

    # unified_config 的旧入口保留（deprecated 兼容壳）
    assert hasattr(unified_config, "_apply_env_overrides")
    assert hasattr(unified_config, "_ENV_OVERRIDE_MAP")


def test_unified_config_env_override_no_default_flip(monkeypatch):
    """修复旧 bug：.env/运行时默认 True 不得把配置中的 enabled=False 翻回 True"""
    from app.core import config as app_config
    from app.core import unified_config

    fake_settings = SimpleNamespace(
        ENABLE_BAOSTOCK=True, BAOSTOCK_UNIFIED_ENABLED=True, ENABLE_TUSHARE=True
    )
    monkeypatch.setattr(app_config, "settings", fake_settings)
    ds = SimpleNamespace(name="BaoStock", type="baostock", enabled=False)
    unified_config._apply_env_overrides([ds])
    assert ds.enabled is False


def test_unified_config_env_override_forced_disable(monkeypatch):
    """.env 显式 False 时强制禁用（兼容壳语义与 A 一致）"""
    from app.core import config as app_config
    from app.core import unified_config

    fake_settings = SimpleNamespace(ENABLE_BAOSTOCK=False)
    monkeypatch.setattr(app_config, "settings", fake_settings)
    ds = SimpleNamespace(name="BaoStock", type="baostock", enabled=True)
    unified_config._apply_env_overrides([ds])
    assert ds.enabled is False
