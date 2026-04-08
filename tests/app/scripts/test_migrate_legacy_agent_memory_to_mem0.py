from app.scripts.migrate_legacy_agent_memory_to_mem0 import (
    LegacyMemoryRecord,
    _build_store_metadata,
    _build_store_messages,
    _normalize_collection_rows,
    _normalize_qdrant_scroll_rows,
)


class _FakeQdrantPoint:
    def __init__(self, point_id, payload):
        self.id = point_id
        self.payload = payload


def test_normalize_collection_rows_builds_legacy_records():
    payload = {
        "ids": ["1", "2"],
        "documents": [
            "贵州茅台 600519 基本面改善",
            "腾讯控股 HK.00700 估值承压",
        ],
        "metadatas": [
            {"recommendation": "继续跟踪高端白酒需求与估值切换"},
            {"recommendation": "关注广告恢复与估值压缩后的修复空间"},
        ],
    }

    records = _normalize_collection_rows("bull_memory", payload)

    assert len(records) == 2
    assert records[0].memory_name == "bull_memory"
    assert records[0].legacy_doc_id == "1"
    assert records[0].recommendation == "继续跟踪高端白酒需求与估值切换"
    assert records[1].legacy_doc_id == "2"


def test_build_store_metadata_adds_symbol_object_binding():
    record = LegacyMemoryRecord(
        memory_name="bull_memory",
        legacy_doc_id="7",
        situation="贵州茅台 600519 基本面改善",
        recommendation="继续跟踪高端白酒需求与估值切换",
    )

    metadata = _build_store_metadata(record)

    assert metadata["source"] == "legacy_financial_situation_memory_migration"
    assert metadata["legacy_memory_name"] == "bull_memory"
    assert metadata["legacy_doc_id"] == "7"
    assert metadata["symbol"] == "600519"
    assert metadata["object_type"] == "stock"
    assert metadata["object_key"] == "600519"


def test_build_store_messages_preserves_legacy_payload_shape():
    record = LegacyMemoryRecord(
        memory_name="risk_manager_memory",
        legacy_doc_id="9",
        situation="高波动环境下仓位暴露偏高",
        recommendation="降低高贝塔仓位并提高现金比例",
    )

    messages = _build_store_messages(record)

    assert messages == [
        {
            "role": "user",
            "content": "Legacy situation:\n高波动环境下仓位暴露偏高\n\nRecommendation:\n降低高贝塔仓位并提高现金比例",
        }
    ]


def test_normalize_qdrant_scroll_rows_builds_legacy_records():
    points = [
        _FakeQdrantPoint(
            "abc-1",
            {
                "document": "宁德时代 300750 研究结论偏多，关注盈利修复。",
                "ticker": "300750",
                "stance": "bull",
                "agent_id": "bull_researcher_v2",
                "provider": "阿里云百炼",
            },
        )
    ]

    records = _normalize_qdrant_scroll_rows("memory_bull_researcher_v2", points)

    assert len(records) == 1
    assert records[0].memory_name == "memory_bull_researcher_v2"
    assert records[0].legacy_doc_id == "abc-1"
    assert records[0].situation == "宁德时代 300750 研究结论偏多，关注盈利修复。"
    assert records[0].legacy_metadata["agent_id"] == "bull_researcher_v2"
    assert records[0].legacy_metadata["ticker"] == "300750"


def test_build_store_metadata_preserves_qdrant_legacy_metadata():
    record = LegacyMemoryRecord(
        memory_name="memory_bear_researcher_v2",
        legacy_doc_id="pt-9",
        situation="万科A 000002 基本面承压，销售恢复偏慢。",
        legacy_metadata={
            "ticker": "000002",
            "stance": "bear",
            "agent_id": "bear_researcher_v2",
            "timestamp": "2026-04-08T10:00:00",
            "provider": "阿里云百炼",
        },
    )

    metadata = _build_store_metadata(record)

    assert metadata["legacy_content"] == "万科A 000002 基本面承压，销售恢复偏慢。"
    assert metadata["ticker"] == "000002"
    assert metadata["legacy_stance"] == "bear"
    assert metadata["legacy_agent_id"] == "bear_researcher_v2"
    assert metadata["legacy_timestamp"] == "2026-04-08T10:00:00"
    assert metadata["legacy_embedding_provider"] == "阿里云百炼"
    assert metadata["symbol"] == "000002"
    assert metadata["object_key"] == "000002"


def test_build_store_messages_without_recommendation_uses_plain_content():
    record = LegacyMemoryRecord(
        memory_name="memory_pa_risk_v2",
        legacy_doc_id="pt-10",
        situation="组合对高波动因子暴露偏高，需要控制回撤。",
    )

    messages = _build_store_messages(record)

    assert messages == [
        {
            "role": "user",
            "content": "组合对高波动因子暴露偏高，需要控制回撤。",
        }
    ]
