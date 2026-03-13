"""
v2.0.0 基线迁移

这是第一个迁移脚本，记录当前数据库的基线状态。
对于已有的生产数据库，此迁移不做任何实际更改。
对于全新安装的数据库，此迁移确保核心索引存在。

此迁移是幂等的，可以安全重复执行。
"""

import logging

VERSION = "2.0.0"
DESCRIPTION = "基线迁移 - 记录 v2.0.0 数据库状态，确保核心索引"

logger = logging.getLogger("migrations")


async def _safe_create_index(collection, keys, **kwargs):
    """安全创建索引 - 如果已存在（即使选项不同）也不报错"""
    try:
        await collection.create_index(keys, **kwargs)
    except Exception as e:
        err_code = getattr(e, 'code', None) if hasattr(e, 'code') else None
        # code 85 = IndexOptionsConflict (索引已存在但选项不同)
        # code 86 = IndexKeySpecsConflict
        if err_code in (85, 86):
            name = kwargs.get('name', str(keys))
            logger.info(f"  ⏭️ 索引已存在(选项不同)，跳过: {collection.name}.{name}")
        else:
            raise


async def upgrade(db):
    """建立基线 - 确保核心集合索引存在"""

    # === 用户相关索引 ===
    await _safe_create_index(db.users, "username", unique=True, sparse=True)

    # === 分析任务索引 ===
    await _safe_create_index(db.unified_analysis_tasks, [("created_at", -1)])
    await _safe_create_index(db.unified_analysis_tasks, "status")
    await _safe_create_index(db.unified_analysis_tasks, "user_id")

    # === 工作流配置索引 ===
    await _safe_create_index(db.workflow_definitions, "workflow_id", unique=True, sparse=True)
    await _safe_create_index(db.agent_configs, "agent_id", unique=True, sparse=True)
    await _safe_create_index(db.tool_configs, "tool_id", unique=True, sparse=True)

    # === 系统配置索引 ===
    await _safe_create_index(db.system_configs, "key", unique=True, sparse=True)
    await _safe_create_index(db.llm_providers, "provider_id", unique=True, sparse=True)

    # === 提示词模板索引 ===
    await _safe_create_index(db.prompt_templates, "template_id", unique=True, sparse=True)

    # === 迁移历史索引 ===
    await _safe_create_index(db.migration_history, "version", unique=True)
    await _safe_create_index(db.migration_history, [("applied_at", -1)])


async def downgrade(db):
    """基线迁移不支持回滚"""
    raise NotImplementedError("基线迁移不支持回滚")

