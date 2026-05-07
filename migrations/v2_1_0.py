"""
v2.1.0 migration

Minor release migration for provider/model routing upgrades and refreshed install
seed data. Configuration seeds, templates, and bindings should be delivered via
releases/v2.1.0/upgrade_config.json.
"""

import logging


logger = logging.getLogger("migrations.v2_1_0")

VERSION = "2.1.0"
DESCRIPTION = "补充 2.1.0 所需索引并保留幂等迁移入口"


async def _create_index_safely(collection, keys, *, name=None, unique=False):
    options = {}
    if name:
        options["name"] = name
    if unique:
        options["unique"] = True

    try:
        await collection.create_index(keys, **options)
    except Exception as exc:
        logger.warning(
            "v2.1.0 migration: create index %s on %s skipped: %s",
            name or keys,
            collection.name,
            exc,
        )


async def upgrade(db):
    """v2.1.0 migration. All operations are idempotent."""

    await db.migration_history.create_index(
        [("status", 1), ("applied_at", -1)]
    )

    industry_mapping = db["stock_industry_mappings"]
    await _create_index_safely(
        industry_mapping,
        [("code", 1)],
        name="code_1",
        unique=True,
    )
    await _create_index_safely(
        industry_mapping,
        [("provider", 1), ("updated_at", -1)],
        name="provider_1_updated_at_-1",
    )

    logger.info(
        "v2.1.0 migration: ensured migration_history and stock_industry_mappings indexes"
    )


async def downgrade(db):
    """回滚操作（可选）"""
    pass