"""股票基础信息统一 Schema 单元测试

覆盖 tradingagents/dataflows/stock_basic_schema.py（共享层实现本体；
app/services/stock_basic_schema.py 为 re-export 兼容壳）：
- validate_stock_basic_doc：必填/可选/允许为空规则
- normalize_stock_basic_doc：写入对齐（code/symbol、source/data_source 语义统一、别名镜像）
- merge_stock_basic_records：读侧多源合并（优先级、非空互补、空值回退、字段级来源标注）
- 兼容壳 re-export 语义（app 路径与共享层为同一实现）
纯逻辑测试，不依赖 MongoDB。
"""

import pytest

from tradingagents.dataflows.stock_basic_schema import (
    FIELD_SOURCE_KEY,
    SOURCE_PRIORITY,
    get_source_rank,
    merge_stock_basic_records,
    normalize_stock_basic_doc,
    validate_stock_basic_doc,
)


# ---------------------------------------------------------------------------
# 兼容壳 re-export
# ---------------------------------------------------------------------------
class TestCompatShell:
    def test_app_shell_reexports_shared_impl(self):
        from app.services.stock_basic_schema import (
            merge_stock_basic_records as shell_merge,
        )
        from app.services.stock_basic_schema import (
            normalize_stock_basic_doc as shell_normalize,
        )

        assert shell_merge is merge_stock_basic_records
        assert shell_normalize is normalize_stock_basic_doc


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------
class TestValidate:
    def test_valid_doc_no_errors(self):
        doc = {
            "code": "600519",
            "symbol": "600519",
            "name": "贵州茅台",
            "industry": "白酒",
            "source": "tushare",
            "pe": 25.3,
        }
        assert validate_stock_basic_doc(doc) == []

    def test_missing_required_fields(self):
        errors = validate_stock_basic_doc({})
        assert any("code" in e for e in errors)
        assert any("source" in e for e in errors)

    def test_invalid_code(self):
        errors = validate_stock_basic_doc({"code": "6005", "source": "tushare"})
        assert any("code" in e for e in errors)

    def test_optional_fields_allowed_empty(self):
        doc = {
            "code": "000001",
            "source": "akshare",
            "name": "",
            "area": "",
            "list_date": None,
            "pe": None,
            "total_mv": "",
        }
        assert validate_stock_basic_doc(doc) == []

    def test_numeric_field_must_be_number(self):
        doc = {"code": "000001", "source": "akshare", "pe": "不是数字"}
        errors = validate_stock_basic_doc(doc)
        assert any("pe" in e for e in errors)


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------
class TestNormalize:
    def test_normalize_derives_symbol_and_pads_code(self):
        doc = normalize_stock_basic_doc({"code": "1", "source": "tushare"})
        assert doc["code"] == "000001"
        assert doc["symbol"] == "000001"

    def test_normalize_unifies_source_and_data_source(self):
        doc = normalize_stock_basic_doc(
            {"code": "000001", "source": "akshare", "data_source": "tushare"}
        )
        assert doc["source"] == "akshare"
        # 以 source 为准，同一条记录两处一致
        assert doc["data_source"] == "akshare"

    def test_normalize_fills_data_source_when_missing(self):
        doc = normalize_stock_basic_doc({"code": "600519", "source": "tushare"})
        assert doc["data_source"] == "tushare"

    def test_normalize_mirrors_category_and_sec(self):
        doc = normalize_stock_basic_doc(
            {"code": "600519", "source": "tushare", "category": "stock_cn"}
        )
        assert doc["sec"] == "stock_cn"

        doc2 = normalize_stock_basic_doc(
            {"code": "600519", "source": "tushare", "sec": "stock_cn"}
        )
        assert doc2["category"] == "stock_cn"

    def test_normalize_strips_whitespace(self):
        doc = normalize_stock_basic_doc(
            {"code": " 600519 ", "source": " tushare ", "name": " 贵州茅台 "}
        )
        assert doc["code"] == "600519"
        assert doc["source"] == "tushare"
        assert doc["name"] == "贵州茅台"

    def test_normalize_keeps_unknown_fields(self):
        doc = normalize_stock_basic_doc(
            {"code": "600519", "source": "tushare", "is_hs": True}
        )
        assert doc["is_hs"] is True

    def test_normalize_raises_on_missing_source(self):
        with pytest.raises(ValueError):
            normalize_stock_basic_doc({"code": "600519"})


# ---------------------------------------------------------------------------
# merge（读侧多源合并）
# ---------------------------------------------------------------------------
class TestMerge:
    def test_priority_and_complement(self):
        """同 code 双源：高优先级字段优先，缺失字段由低优先级互补。"""
        tushare_doc = {
            "code": "600519",
            "symbol": "600519",
            "name": "贵州茅台",
            "industry": "白酒",
            "area": "",
            "source": "tushare",
        }
        akshare_doc = {
            "code": "600519",
            "symbol": "600519",
            "name": "贵州茅台XD",
            "industry": "食品饮料",
            "area": "贵州",
            "source": "akshare",
        }
        merged = merge_stock_basic_records([akshare_doc, tushare_doc])
        assert merged["name"] == "贵州茅台"  # 优先级：tushare 胜出
        assert merged["industry"] == "白酒"
        assert merged["area"] == "贵州"  # 空值回退：tushare 缺 area，取 akshare
        assert merged[FIELD_SOURCE_KEY]["name"] == "tushare"
        assert merged[FIELD_SOURCE_KEY]["area"] == "akshare"

    def test_empty_value_falls_back_to_next_source(self):
        tushare_doc = {"code": "000001", "name": "", "source": "tushare"}
        baostock_doc = {"code": "000001", "name": "平安银行", "source": "baostock"}
        merged = merge_stock_basic_records([tushare_doc, baostock_doc])
        assert merged["name"] == "平安银行"
        assert merged[FIELD_SOURCE_KEY]["name"] == "baostock"

    def test_numeric_zero_is_kept(self):
        """0 是有效值，不应被低优先级记录覆盖。"""
        tushare_doc = {"code": "000001", "pe": 0.0, "source": "tushare"}
        akshare_doc = {"code": "000001", "pe": 12.5, "source": "akshare"}
        merged = merge_stock_basic_records([tushare_doc, akshare_doc])
        assert merged["pe"] == 0.0
        assert merged[FIELD_SOURCE_KEY]["pe"] == "tushare"

    def test_nan_treated_as_empty(self):
        tushare_doc = {"code": "000001", "pe": float("nan"), "source": "tushare"}
        akshare_doc = {"code": "000001", "pe": 12.5, "source": "akshare"}
        merged = merge_stock_basic_records([tushare_doc, akshare_doc])
        assert merged["pe"] == 12.5
        assert merged[FIELD_SOURCE_KEY]["pe"] == "akshare"

    def test_source_priority_order(self):
        assert get_source_rank("tushare") < get_source_rank("multi_source")
        assert get_source_rank("multi_source") < get_source_rank("akshare")
        assert get_source_rank("akshare") < get_source_rank("baostock")
        assert get_source_rank("unknown_src") > get_source_rank("baostock")
        assert SOURCE_PRIORITY == ("tushare", "multi_source", "akshare", "baostock")

    def test_unknown_and_legacy_sources_rank_last(self):
        legacy_doc = {"code": "000001", "name": "旧数据名称", "area": "广东"}
        unknown_doc = {"code": "000001", "name": "未知源名称", "source": "qmt"}
        akshare_doc = {"code": "000001", "name": "平安银行A", "source": "akshare"}
        merged = merge_stock_basic_records([legacy_doc, unknown_doc, akshare_doc])
        assert merged["name"] == "平安银行A"
        assert merged["area"] == "广东"
        assert merged[FIELD_SOURCE_KEY]["name"] == "akshare"
        assert merged[FIELD_SOURCE_KEY]["area"] == "unknown"

    def test_data_source_unified_with_source(self):
        merged = merge_stock_basic_records(
            [
                {"code": "000001", "source": "tushare"},
                {"code": "000001", "source": "akshare", "data_source": "akshare"},
            ]
        )
        assert merged["source"] == "tushare"
        assert merged["data_source"] == "tushare"
        assert merged[FIELD_SOURCE_KEY]["data_source"] == "tushare"

    def test_category_sec_mirrored(self):
        merged = merge_stock_basic_records(
            [
                {"code": "600519", "source": "tushare", "sec": "stock_cn"},
                {"code": "600519", "source": "akshare", "category": "stock_ak"},
            ]
        )
        # tushare 的 sec（category 别名）优先
        assert merged["category"] == "stock_cn"
        assert merged["sec"] == "stock_cn"

    def test_symbol_derived_from_code(self):
        merged = merge_stock_basic_records([{"code": "600519", "source": "tushare"}])
        assert merged["symbol"] == "600519"

    def test_internal_fields_excluded(self):
        merged = merge_stock_basic_records(
            [{"_id": "abc", "code": "600519", "source": "tushare"}]
        )
        assert "_id" not in merged

    def test_single_record_passthrough_with_annotation(self):
        merged = merge_stock_basic_records(
            [{"code": "600519", "name": "贵州茅台", "source": "tushare"}]
        )
        assert merged["name"] == "贵州茅台"
        assert merged[FIELD_SOURCE_KEY]["name"] == "tushare"

    def test_empty_input_returns_none(self):
        assert merge_stock_basic_records([]) is None
        assert merge_stock_basic_records(None) is None

    def test_merged_result_is_normalized_consistent(self):
        """合并结果可以再次通过 normalize（读写口径一致）。"""
        merged = merge_stock_basic_records(
            [
                {"code": "600519", "name": "贵州茅台", "source": "tushare", "area": ""},
                {"code": "600519", "name": "贵州茅台", "source": "akshare", "area": "贵州"},
            ]
        )
        normalized = normalize_stock_basic_doc(merged)
        assert normalized["area"] == "贵州"
        assert normalized["data_source"] == "tushare"


def test_normalize_stamps_write_path():
    """§七：写入路径标记——同步默认 'sync'，缓存回写传 'cache'，已有标记保留。"""
    assert normalize_stock_basic_doc({"code": "600519", "source": "tushare"})["write_path"] == "sync"
    assert (
        normalize_stock_basic_doc({"code": "600519", "source": "tushare"}, write_path="cache")["write_path"]
        == "cache"
    )
    assert (
        normalize_stock_basic_doc({"code": "600519", "source": "tushare", "write_path": "cache"})["write_path"]
        == "cache"
    )
