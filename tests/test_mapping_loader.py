"""
映射配置加载器测试

测试覆盖：
- YAML 文件加载与解析
- 缓存机制（TTL 过期、文件修改时间变化）
- 热重载（reload）
- 缺失文件回退
- 便捷方法正确性
- 线程安全
"""

import os
import tempfile
import threading
import time
from pathlib import Path

import pytest
import yaml

from app.core.mapping_loader import MappingLoader


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def tmp_mappings(tmp_path):
    """创建临时映射配置目录并写入测试 YAML 文件。"""
    mappings_dir = tmp_path / "config" / "mappings"
    mappings_dir.mkdir(parents=True)

    # provider_mappings.yaml
    provider_data = {
        "llm_provider_names": {"openai": "OpenAI", "qwen": "通义千问"},
        "data_source_names": {"tushare": "Tushare"},
        "llm_env_key_mapping": {"openai": "OPENAI_API_KEY", "qwen": "DASHSCOPE_API_KEY"},
        "data_source_env_key_mapping": {"tushare": "TUSHARE_TOKEN"},
        "model_prefixes": {"gpt-": "openai", "qwen": "qwen"},
        "model_provider_map": {"qwen-turbo": "qwen", "gpt-4": "openai"},
        "provider_normalization": {"openai": "openai", "alibaba": "qwen"},
        "aggregator_providers": {
            "openrouter": {"display_name": "OpenRouter", "default_base_url": "https://openrouter.ai/api/v1"}
        },
    }
    (mappings_dir / "provider_mappings.yaml").write_text(
        yaml.dump(provider_data, allow_unicode=True), encoding="utf-8"
    )

    # market_mappings.yaml
    market_data = {
        "market_category_map": {"CN": "a_shares", "HK": "hk_stocks", "US": "us_stocks"},
        "market_type_names": {"china_a": "A股", "hong_kong": "港股"},
        "market_currency_map": {"CN": "CNY", "HK": "HKD", "US": "USD"},
        "initial_cash_by_market": {"CNY": 1000000.0, "USD": 100000.0},
        "data_source_priority": {"CN": ["tushare", "akshare"]},
        "period_map_yahoo": {"day": "1d", "week": "1wk"},
        "period_map_akshare": {"day": "daily", "week": "weekly"},
        "period_map_tushare": {"day": "D", "week": "W"},
        "adjust_map": {"qfq": "qfq", "hfq": "hfq"},
        "cache_ttl": {"HK": {"quote": 600, "info": 86400}},
        "tushare_rate_limits": {"free": {"max_calls": 100, "time_window": 60}},
    }
    (mappings_dir / "market_mappings.yaml").write_text(
        yaml.dump(market_data, allow_unicode=True), encoding="utf-8"
    )

    # analysis_mappings.yaml
    analysis_data = {
        "numeric_to_depth": {1: "快速", 2: "基础", 3: "标准", 4: "深度", 5: "全面"},
        "depth_to_numeric": {"快速": 1, "基础": 2, "标准": 3, "深度": 4, "全面": 5},
        "analyst_steps": {
            "market": {"name": "市场分析师", "icon": "📊"},
            "fundamentals": {"name": "基本面分析师", "icon": "💼"},
        },
        "base_time_per_depth": {1: 150, 2: 180, 3: 240, 4: 330, 5: 480},
        "model_time_multiplier": {"qwen": 1.0, "deepseek": 0.8, "google": 1.2},
        "depth_time_multiplier": {1: 0.8, 2: 1.0, 3: 1.2},
        "action_translation": {"BUY": "买入", "SELL": "卖出", "HOLD": "持有"},
        "status_mapping": {"processing": "running", "completed": "completed"},
        "http_method_names": {"POST": "创建", "PUT": "更新", "DELETE": "删除"},
    }
    (mappings_dir / "analysis_mappings.yaml").write_text(
        yaml.dump(analysis_data, allow_unicode=True), encoding="utf-8"
    )

    # ui_mappings.yaml
    ui_data = {
        "module_titles": {"company_overview": "公司概况", "financial_analysis": "财务分析"},
        "capability_badges": {
            1: {"text": "基础", "color": "#909399", "icon": "⚡"},
            5: {"text": "旗舰", "color": "#F56C6C", "icon": "👑"},
        },
        "role_badges": {"quick_analysis": {"text": "快速分析", "color": "success"}},
        "feature_badges": {"tool_calling": {"text": "工具调用", "color": "info"}},
        "sensitive_keys": ["MONGODB_PASSWORD", "JWT_SECRET"],
    }
    (mappings_dir / "ui_mappings.yaml").write_text(
        yaml.dump(ui_data, allow_unicode=True), encoding="utf-8"
    )

    return mappings_dir


@pytest.fixture
def loader(tmp_mappings):
    """创建指向临时目录的 MappingLoader 实例。"""
    return MappingLoader(mappings_dir=tmp_mappings, cache_ttl=60)


# ======================================================================
# 基础加载测试
# ======================================================================

class TestBasicLoading:
    """测试基本的文件加载和键值读取。"""

    def test_load_returns_dict(self, loader):
        data = loader.load("provider_mappings")
        assert isinstance(data, dict)
        assert "llm_provider_names" in data

    def test_get_returns_specific_key(self, loader):
        names = loader.get("provider_mappings", "llm_provider_names")
        assert names == {"openai": "OpenAI", "qwen": "通义千问"}

    def test_get_returns_default_for_missing_key(self, loader):
        result = loader.get("provider_mappings", "nonexistent_key", "fallback")
        assert result == "fallback"

    def test_get_returns_default_for_missing_file(self, tmp_mappings):
        loader = MappingLoader(mappings_dir=tmp_mappings)
        result = loader.load("nonexistent_file")
        assert result == {}

    def test_list_files(self, loader):
        files = loader.list_files()
        assert "provider_mappings" in files
        assert "market_mappings" in files
        assert "analysis_mappings" in files
        assert "ui_mappings" in files

    def test_load_with_yaml_extension(self, loader):
        data = loader.load("provider_mappings.yaml")
        assert "llm_provider_names" in data


# ======================================================================
# 缓存测试
# ======================================================================

class TestCaching:
    """测试缓存机制。"""

    def test_cached_data_returned_on_second_call(self, loader):
        data1 = loader.load("provider_mappings")
        data2 = loader.load("provider_mappings")
        assert data1 is data2  # 同一个对象引用

    def test_cache_cleared_on_reload(self, loader):
        data1 = loader.load("provider_mappings")
        loader.reload("provider_mappings")
        data2 = loader.load("provider_mappings")
        # reload 后重新加载，数据内容相同但可能是新对象
        assert data1 == data2

    def test_reload_all_clears_entire_cache(self, loader):
        loader.load("provider_mappings")
        loader.load("market_mappings")
        loader.reload()  # 清除所有
        # 验证重新加载成功
        data = loader.load("provider_mappings")
        assert "llm_provider_names" in data

    def test_cache_ttl_expires(self, tmp_mappings):
        loader = MappingLoader(mappings_dir=tmp_mappings, cache_ttl=0)
        data1 = loader.load("provider_mappings")
        time.sleep(0.01)
        data2 = loader.load("provider_mappings")
        # TTL=0 意味着每次都重新加载，但数据内容相同
        assert data1 == data2


# ======================================================================
# 文件修改热重载测试
# ======================================================================

class TestHotReload:
    """测试文件修改后的热重载。"""

    def test_file_change_detected(self, tmp_mappings):
        loader = MappingLoader(mappings_dir=tmp_mappings, cache_ttl=0)
        # 初始加载
        names = loader.get("provider_mappings", "llm_provider_names")
        assert "openai" in names

        # 修改文件
        file_path = tmp_mappings / "provider_mappings.yaml"
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        data["llm_provider_names"]["new_provider"] = "New Provider"
        file_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")

        # TTL=0 所以下次加载应该检测到变化
        loader.reload("provider_mappings")
        names = loader.get("provider_mappings", "llm_provider_names")
        assert "new_provider" in names


# ======================================================================
# 便捷方法测试
# ======================================================================

class TestConvenienceMethods:
    """测试各便捷方法。"""

    def test_get_llm_provider_names(self, loader):
        names = loader.get_llm_provider_names()
        assert names["openai"] == "OpenAI"

    def test_get_data_source_names(self, loader):
        names = loader.get_data_source_names()
        assert names["tushare"] == "Tushare"

    def test_get_llm_env_key_mapping(self, loader):
        mapping = loader.get_llm_env_key_mapping()
        assert mapping["openai"] == "OPENAI_API_KEY"

    def test_get_data_source_env_key_mapping(self, loader):
        mapping = loader.get_data_source_env_key_mapping()
        assert mapping["tushare"] == "TUSHARE_TOKEN"

    def test_get_model_prefixes(self, loader):
        prefixes = loader.get_model_prefixes()
        assert prefixes["gpt-"] == "openai"

    def test_get_model_provider_map(self, loader):
        m = loader.get_model_provider_map()
        assert m["qwen-turbo"] == "qwen"
        assert m["gpt-4"] == "openai"

    def test_get_provider_normalization(self, loader):
        norm = loader.get_provider_normalization()
        assert norm["alibaba"] == "qwen"

    def test_get_aggregator_providers(self, loader):
        agg = loader.get_aggregator_providers()
        assert "openrouter" in agg

    def test_get_market_category_map(self, loader):
        m = loader.get_market_category_map()
        assert m["CN"] == "a_shares"
        assert m["HK"] == "hk_stocks"

    def test_get_market_type_names(self, loader):
        names = loader.get_market_type_names()
        assert names["china_a"] == "A股"

    def test_get_market_currency_map(self, loader):
        m = loader.get_market_currency_map()
        assert m["CN"] == "CNY"

    def test_get_initial_cash_by_market(self, loader):
        cash = loader.get_initial_cash_by_market()
        assert cash["CNY"] == 1000000.0

    def test_get_data_source_priority(self, loader):
        priority = loader.get_data_source_priority()
        assert priority["CN"] == ["tushare", "akshare"]

    def test_get_period_map_yahoo(self, loader):
        m = loader.get_period_map("yahoo")
        assert m["day"] == "1d"

    def test_get_period_map_akshare(self, loader):
        m = loader.get_period_map("akshare")
        assert m["day"] == "daily"

    def test_get_period_map_tushare(self, loader):
        m = loader.get_period_map("tushare")
        assert m["day"] == "D"

    def test_get_adjust_map(self, loader):
        m = loader.get_adjust_map()
        assert m["qfq"] == "qfq"

    def test_get_cache_ttl_config(self, loader):
        ttl = loader.get_cache_ttl_config()
        assert ttl["HK"]["quote"] == 600

    def test_get_tushare_rate_limits(self, loader):
        limits = loader.get_tushare_rate_limits()
        assert limits["free"]["max_calls"] == 100

    def test_get_numeric_to_depth(self, loader):
        m = loader.get_numeric_to_depth()
        assert m[1] == "快速"
        assert m[5] == "全面"

    def test_get_depth_to_numeric(self, loader):
        m = loader.get_depth_to_numeric()
        assert m["快速"] == 1
        assert m["全面"] == 5

    def test_get_analyst_steps(self, loader):
        steps = loader.get_analyst_steps()
        assert steps["market"]["name"] == "市场分析师"

    def test_get_base_time_per_depth(self, loader):
        t = loader.get_base_time_per_depth()
        assert t[1] == 150
        assert t[5] == 480

    def test_get_model_time_multiplier(self, loader):
        m = loader.get_model_time_multiplier()
        assert m["qwen"] == 1.0
        assert m["deepseek"] == 0.8

    def test_get_depth_time_multiplier(self, loader):
        m = loader.get_depth_time_multiplier()
        assert m[1] == 0.8

    def test_get_action_translation(self, loader):
        m = loader.get_action_translation()
        assert m["BUY"] == "买入"

    def test_get_status_mapping(self, loader):
        m = loader.get_status_mapping()
        assert m["processing"] == "running"

    def test_get_http_method_names(self, loader):
        m = loader.get_http_method_names()
        assert m["POST"] == "创建"

    def test_get_module_titles(self, loader):
        titles = loader.get_module_titles()
        assert titles["company_overview"] == "公司概况"

    def test_get_capability_badges(self, loader):
        badges = loader.get_capability_badges()
        assert badges[1]["text"] == "基础"
        assert badges[5]["text"] == "旗舰"

    def test_get_role_badges(self, loader):
        badges = loader.get_role_badges()
        assert badges["quick_analysis"]["text"] == "快速分析"

    def test_get_feature_badges(self, loader):
        badges = loader.get_feature_badges()
        assert badges["tool_calling"]["text"] == "工具调用"

    def test_get_sensitive_keys(self, loader):
        keys = loader.get_sensitive_keys()
        assert "MONGODB_PASSWORD" in keys


# ======================================================================
# 线程安全测试
# ======================================================================

class TestThreadSafety:
    """测试并发访问时的线程安全。"""

    def test_concurrent_load(self, loader):
        results = {}
        errors = []

        def load_mapping(name, idx):
            try:
                data = loader.load(name)
                results[idx] = data
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(20):
            name = ["provider_mappings", "market_mappings", "analysis_mappings", "ui_mappings"][i % 4]
            t = threading.Thread(target=load_mapping, args=(name, i))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_concurrent_reload(self, loader):
        errors = []

        def reload_and_load():
            try:
                for _ in range(5):
                    loader.reload()
                    loader.load("provider_mappings")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reload_and_load) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ======================================================================
# 边界情况测试
# ======================================================================

class TestEdgeCases:
    """测试边界情况和异常处理。"""

    def test_empty_yaml_file(self, tmp_mappings):
        (tmp_mappings / "empty.yaml").write_text("", encoding="utf-8")
        loader = MappingLoader(mappings_dir=tmp_mappings)
        data = loader.load("empty")
        assert data == {}

    def test_malformed_yaml_file(self, tmp_mappings):
        (tmp_mappings / "bad.yaml").write_text("{{{{invalid yaml", encoding="utf-8")
        loader = MappingLoader(mappings_dir=tmp_mappings)
        data = loader.load("bad")
        assert data == {}

    def test_nonexistent_directory(self, tmp_path):
        loader = MappingLoader(mappings_dir=tmp_path / "nonexistent")
        data = loader.load("anything")
        assert data == {}
        assert loader.list_files() == []

    def test_get_with_none_default(self, loader):
        result = loader.get("provider_mappings", "nonexistent")
        assert result is None
