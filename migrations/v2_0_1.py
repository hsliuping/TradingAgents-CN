"""
v2.0.1 示例迁移

此文件是迁移脚本的模板示例，展示常见的迁移操作。
实际发布时替换为真实的迁移内容。

支持的操作类型：
1. 给已有集合添加新字段（设置默认值）
2. 创建新索引
3. 插入新的配置数据
4. 修改已有文档的字段值
5. 创建新集合
"""

VERSION = "2.0.1"
DESCRIPTION = "示例迁移 - 添加 migration_history 索引和系统版本记录"


async def upgrade(db):
    """
    示例迁移操作

    实际使用时，按需修改此函数的内容。
    所有操作必须是幂等的（安全重复执行）。
    """

    # --- 示例 1: 确保集合存在并创建索引 ---
    # create_index 如果索引已存在会自动跳过
    await db.migration_history.create_index(
        [("status", 1), ("applied_at", -1)]
    )

    # --- 示例 2: 给已有文档添加新字段（仅当字段不存在时） ---
    # await db.agent_configs.update_many(
    #     {"timeout": {"$exists": False}},
    #     {"$set": {"timeout": 30}}
    # )

    # --- 示例 3: 插入新配置数据（仅当不存在时） ---
    # existing = await db.system_configs.find_one({"key": "new_feature_flag"})
    # if not existing:
    #     await db.system_configs.insert_one({
    #         "key": "new_feature_flag",
    #         "value": False,
    #         "description": "新功能开关",
    #         "created_at": datetime.now(timezone.utc),
    #     })

    # --- 示例 4: 修改已有文档的字段名 ---
    # await db.some_collection.update_many(
    #     {"old_field_name": {"$exists": True}},
    #     {"$rename": {"old_field_name": "new_field_name"}}
    # )

    # --- 示例 5: 删除不再需要的字段 ---
    # await db.some_collection.update_many(
    #     {"deprecated_field": {"$exists": True}},
    #     {"$unset": {"deprecated_field": ""}}
    # )


async def downgrade(db):
    """回滚操作（可选）"""
    # 回滚示例 2:
    # await db.agent_configs.update_many({}, {"$unset": {"timeout": ""}})
    pass

