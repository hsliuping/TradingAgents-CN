"""
v3.2.0 migration - 向量存储从 Qdrant 迁移到 MongoDB

迁移内容：
1. 为向量相关 MongoDB 集合创建元数据索引，加速客户端 cosine 搜索时的过滤
2. 记录迁移完成标记，便于排查

背景：
- v3.2.0 将向量存储后端从 Qdrant 切换为 MongoDB（客户端 cosine 相似度）
- 向量数据和业务数据统一存储在 MongoDB 中，减少运维组件
- 向量集合的文档结构为扁平式：{embedding, document, ...metadata}
- mem0 集合的文档结构为嵌套式：{embedding, payload: {...}}

所有操作必须幂等（可安全多次运行）。
"""

import logging

logger = logging.getLogger("migrations.v3_2_0")

VERSION = "3.2.0"
DESCRIPTION = "向量存储迁移到 MongoDB：创建向量集合元数据索引"

# VectorStoreManager 使用的向量集合（扁平文档结构）
# 集合名模式：memory_<agent_id>、user_manual_v3、knowledge_finance
_VECTOR_FLAT_COLLECTIONS = [
    "user_manual_v3",
    "knowledge_finance",
]

# mem0 使用的向量集合（嵌套 payload 文档结构）
# 集合名模式：mem0_memories_<provider>_<model>_<dims>_<fingerprint>
_MEM0_COLLECTION_PREFIX = "mem0_memories"

# 扁平文档结构常用过滤字段（与 MongoDBVectorCollection 配合）
_FLAT_INDEX_FIELDS = [
    ("title", 1),
    ("manual_type", 1),
    ("provider", 1),
    ("agent_id", 1),
    ("category", 1),
]

# mem0 嵌套 payload 结构常用过滤字段（与 MongoDBClientCosine 配合）
_MEM0_PAYLOAD_INDEX_FIELDS = [
    ("payload.user_id", 1),
    ("payload.agent_id", 1),
    ("payload.scope", 1),
    ("payload.run_id", 1),
]


async def _create_indexes_for_collection(db, collection_name: str, index_fields: list):
    """为指定集合创建索引（幂等，已存在则跳过）"""
    try:
        existing_indexes = await db[collection_name].list_indexes()
        existing_names = {idx["name"] async for idx in existing_indexes}
    except Exception:
        existing_names = set()

    created = 0
    for field, direction in index_fields:
        index_name = f"{field.replace('.', '_')}_idx"
        if index_name in existing_names:
            continue
        try:
            await db[collection_name].create_index(
                [(field, direction)], name=index_name, background=True
            )
            created += 1
        except Exception as e:
            logger.debug(
                "v3.2.0 migration: 创建索引 %s.%s 跳过: %s",
                collection_name, field, e,
            )
    return created


async def _migrate_vector_collection_indexes(db):
    """为 VectorStoreManager 管理的向量集合创建索引"""
    total_created = 0

    # 1. 已知的固定名称集合
    for col_name in _VECTOR_FLAT_COLLECTIONS:
        # 检查集合是否存在
        exists = col_name in await db.list_collection_names()
        if not exists:
            logger.debug(
                "v3.2.0 migration: 集合 %s 不存在，跳过索引创建", col_name
            )
            continue
        created = await _create_indexes_for_collection(db, col_name, _FLAT_INDEX_FIELDS)
        if created:
            logger.info(
                "v3.2.0 migration: 集合 %s 创建了 %d 个索引", col_name, created
            )
        total_created += created

    # 2. 动态集合：memory_<agent_id>
    all_collections = await db.list_collection_names()
    for col_name in all_collections:
        if col_name.startswith("memory_"):
            created = await _create_indexes_for_collection(db, col_name, _FLAT_INDEX_FIELDS)
            if created:
                logger.info(
                    "v3.2.0 migration: 集合 %s 创建了 %d 个索引", col_name, created
                )
            total_created += created

    return total_created


async def _migrate_mem0_collection_indexes(db):
    """为 mem0 管理的向量集合创建索引"""
    total_created = 0
    all_collections = await db.list_collection_names()

    for col_name in all_collections:
        if not col_name.startswith(_MEM0_COLLECTION_PREFIX):
            continue
        created = await _create_indexes_for_collection(db, col_name, _MEM0_PAYLOAD_INDEX_FIELDS)
        if created:
            logger.info(
                "v3.2.0 migration: mem0 集合 %s 创建了 %d 个索引", col_name, created
            )
        total_created += created

    return total_created


async def upgrade(db):
    """执行 v3.2.0 迁移：为向量集合创建索引"""
    logger.info("v3.2.0 migration: 开始创建向量集合索引（Qdrant → MongoDB 迁移）")

    vector_created = await _migrate_vector_collection_indexes(db)
    mem0_created = await _migrate_mem0_collection_indexes(db)

    logger.info(
        "v3.2.0 migration: 完成 — VectorStoreManager 集合 %d 个索引, "
        "mem0 集合 %d 个索引",
        vector_created, mem0_created,
    )
    logger.info(
        "v3.2.0 migration: 说明 — 向量数据将在启动时由 UserManualManager 等"
        "管理器自动索引到 MongoDB，无需手动导入"
    )


async def downgrade(db):
    """回滚 v3.2.0 迁移：删除本次创建的索引（可选）"""
    logger.info("v3.2.0 migration: 回滚 — 保留索引（无害，跳过删除）")
    # 索引不影响功能，不删除
