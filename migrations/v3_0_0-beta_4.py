"""
v3.0.0-beta.4 migration

Add schema changes, new indexes, or default values here.
All operations must be idempotent (safe to run multiple times).
"""

VERSION = "3.0.0-beta.4"
DESCRIPTION = "v3.0.0-beta.4 migration"


async def upgrade(db):
    # Example: await db.migration_history.create_index([("status", 1)])
    pass


async def downgrade(db):
    pass


