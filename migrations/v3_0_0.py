"""
v3.0.0 migration

新增集合索引：
- agent_configs: 工坊 agent 配置
- agent_versions: agent 版本记录
- agent_specs: agent 规格
- agent_workshop_sessions: 工坊会话
- template_history: 模板迁移历史
- skill_bindings: Skill-Agent 绑定
- tool_execution_logs: 工具执行日志

所有操作必须幂等（可安全多次运行）。
"""

import logging

logger = logging.getLogger("migrations.v3_0_0")

VERSION = "3.0.0"
DESCRIPTION = "v3.0.0 新增集合索引"


async def _create_index_safely(collection, keys, *, name=None, unique=False):
    """安全创建索引，忽略已存在错误"""
    options = {}
    if name:
        options["name"] = name
    if unique:
        options["unique"] = True

    try:
        await collection.create_index(keys, **options)
        logger.info(f"v3.0.0 migration: 创建索引 {name or keys} 于 {collection.name}")
    except Exception as exc:
        logger.warning(
            f"v3.0.0 migration: 创建索引 {name or keys} 于 {collection.name} 跳过: {exc}"
        )


async def upgrade(db):
    """v3.0.0 migration. All operations are idempotent."""

    # 1. agent_configs 集合索引
    agent_configs = db["agent_configs"]
    await _create_index_safely(
        agent_configs,
        [("agent_id", 1)],
        name="agent_id_1",
        unique=True,
    )
    await _create_index_safely(
        agent_configs,
        [("enabled", 1), ("version_status", 1), ("runtime_status", 1)],
        name="enabled_version_runtime_status",
    )
    await _create_index_safely(
        agent_configs,
        [("workflow_stage", 1)],
        name="workflow_stage_1",
    )
    await _create_index_safely(
        agent_configs,
        [("category", 1)],
        name="category_1",
    )

    # 2. agent_versions 集合索引
    agent_versions = db["agent_versions"]
    await _create_index_safely(
        agent_versions,
        [("version_id", 1)],
        name="version_id_1",
        unique=True,
    )
    await _create_index_safely(
        agent_versions,
        [("spec_id", 1), ("version", -1)],
        name="spec_id_version_desc",
    )
    await _create_index_safely(
        agent_versions,
        [("status", 1)],
        name="status_1",
    )

    # 3. agent_specs 集合索引
    agent_specs = db["agent_specs"]
    await _create_index_safely(
        agent_specs,
        [("spec_id", 1)],
        name="spec_id_1",
        unique=True,
    )
    await _create_index_safely(
        agent_specs,
        [("owner_user_id", 1)],
        name="owner_user_id_1",
    )
    await _create_index_safely(
        agent_specs,
        [("status", 1)],
        name="status_1",
    )

    # 4. agent_workshop_sessions 集合索引
    sessions = db["agent_workshop_sessions"]
    await _create_index_safely(
        sessions,
        [("session_id", 1)],
        name="session_id_1",
        unique=True,
    )
    await _create_index_safely(
        sessions,
        [("spec_id", 1)],
        name="spec_id_1",
    )
    await _create_index_safely(
        sessions,
        [("user_id", 1), ("created_at", -1)],
        name="user_id_created_at_desc",
    )
    await _create_index_safely(
        sessions,
        [("stage", 1)],
        name="stage_1",
    )

    # 5. template_history 集合索引
    template_history = db["template_history"]
    await _create_index_safely(
        template_history,
        [("migration_id", 1)],
        name="migration_id_1",
    )
    await _create_index_safely(
        template_history,
        [("agent_name", 1), ("timestamp", -1)],
        name="agent_name_timestamp_desc",
    )

    # 6. skill_bindings 集合索引
    skill_bindings = db["skill_bindings"]
    await _create_index_safely(
        skill_bindings,
        [("skill_id", 1), ("agent_id", 1)],
        name="skill_id_agent_id",
        unique=True,
    )
    await _create_index_safely(
        skill_bindings,
        [("agent_id", 1)],
        name="agent_id_1",
    )

    # 7. tool_execution_logs 集合索引
    tool_logs = db["tool_execution_logs"]
    await _create_index_safely(
        tool_logs,
        [("execution_id", 1)],
        name="execution_id_1",
    )
    await _create_index_safely(
        tool_logs,
        [("agent_id", 1), ("timestamp", -1)],
        name="agent_id_timestamp_desc",
    )
    await _create_index_safely(
        tool_logs,
        [("tool_name", 1)],
        name="tool_name_1",
    )
    await _create_index_safely(
        tool_logs,
        [("success", 1)],
        name="success_1",
    )

    logger.info("v3.0.0 migration: 所有索引创建完成")


async def downgrade(db):
    """回滚操作（可选）"""
    # MongoDB 索引删除需要显式指定索引名称
    # 为安全起见，downgrade 不自动删除索引
    pass