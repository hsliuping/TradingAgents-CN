"""
迁移执行器

负责扫描迁移脚本、检查执行状态、按顺序执行待处理的迁移。
"""

import importlib
import logging
import time
import pkgutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("migrations")


class MigrationRunner:
    """数据库迁移执行器"""

    HISTORY_COLLECTION = "migration_history"

    def __init__(self, db):
        """
        Args:
            db: AsyncIOMotorDatabase 实例
        """
        self.db = db
        self._migrations: List[Dict[str, Any]] = []

    def discover_migrations(self) -> List[Dict[str, Any]]:
        """
        扫描 migrations 包中所有 v*.py 迁移脚本
        
        Returns:
            按版本号排序的迁移信息列表
        """
        import migrations as mig_pkg

        found = []
        for importer, modname, ispkg in pkgutil.iter_modules(mig_pkg.__path__):
            if not modname.startswith("v"):
                continue
            full_name = f"migrations.{modname}"
            try:
                mod = importlib.import_module(full_name)
                version = getattr(mod, "VERSION", None)
                description = getattr(mod, "DESCRIPTION", "")
                upgrade_fn = getattr(mod, "upgrade", None)
                downgrade_fn = getattr(mod, "downgrade", None)

                if not version or not upgrade_fn:
                    logger.warning(
                        f"⚠️ 跳过 {modname}: 缺少 VERSION 或 upgrade 函数"
                    )
                    continue

                found.append({
                    "version": version,
                    "description": description,
                    "module": modname,
                    "upgrade": upgrade_fn,
                    "downgrade": downgrade_fn,
                })
            except Exception as e:
                logger.error(f"❌ 加载迁移脚本 {modname} 失败: {e}")

        # 按版本号排序（将 "2.0.1" 转为可比较的元组）
        found.sort(key=lambda m: self._version_key(m["version"]))
        self._migrations = found
        return found

    async def get_applied_versions(self) -> List[str]:
        """获取已执行成功的迁移版本列表"""
        cursor = self.db[self.HISTORY_COLLECTION].find(
            {"status": "success"},
            {"version": 1, "_id": 0},
        ).sort("applied_at", 1)
        docs = await cursor.to_list(length=None)
        return [d["version"] for d in docs]

    async def get_pending(self) -> List[Dict[str, Any]]:
        """获取待执行的迁移列表"""
        if not self._migrations:
            self.discover_migrations()
        applied = set(await self.get_applied_versions())
        return [m for m in self._migrations if m["version"] not in applied]

    async def run_pending(self) -> List[Dict[str, Any]]:
        """
        执行所有待处理的迁移
        
        Returns:
            已执行的迁移结果列表
        """
        pending = await self.get_pending()
        if not pending:
            logger.info("✅ 数据库已是最新版本，无需迁移")
            return []

        logger.info(f"📦 发现 {len(pending)} 个待执行迁移")
        results = []

        for mig in pending:
            result = await self._execute_one(mig)
            results.append(result)
            if result["status"] == "failed":
                logger.error(
                    f"❌ 迁移 {mig['version']} 失败，停止后续迁移"
                )
                break

        return results

    async def run_one(self, version: str) -> Dict[str, Any]:
        """执行指定版本的迁移"""
        if not self._migrations:
            self.discover_migrations()
        target = next(
            (m for m in self._migrations if m["version"] == version), None
        )
        if not target:
            raise ValueError(f"未找到版本 {version} 的迁移脚本")

        applied = set(await self.get_applied_versions())
        if version in applied:
            logger.info(f"⏭️ 版本 {version} 已执行过，跳过")
            return {"version": version, "status": "skipped"}

        return await self._execute_one(target)

    async def _execute_one(self, mig: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个迁移"""
        version = mig["version"]
        logger.info(f"🔄 执行迁移 {version}: {mig['description']}")

        start = time.monotonic()
        try:
            await mig["upgrade"](self.db)
            duration_ms = int((time.monotonic() - start) * 1000)

            record = {
                "version": version,
                "description": mig["description"],
                "module": mig["module"],
                "applied_at": datetime.now(timezone.utc),
                "duration_ms": duration_ms,
                "status": "success",
                "error": None,
            }
            await self.db[self.HISTORY_COLLECTION].insert_one(record)
            logger.info(
                f"✅ 迁移 {version} 完成 ({duration_ms}ms)"
            )
            return {"version": version, "status": "success",
                    "duration_ms": duration_ms}

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            record = {
                "version": version,
                "description": mig["description"],
                "module": mig["module"],
                "applied_at": datetime.now(timezone.utc),
                "duration_ms": duration_ms,
                "status": "failed",
                "error": str(e),
            }
            await self.db[self.HISTORY_COLLECTION].insert_one(record)
            logger.error(f"❌ 迁移 {version} 失败: {e}")
            return {"version": version, "status": "failed",
                    "error": str(e), "duration_ms": duration_ms}

    async def get_status(self) -> Dict[str, Any]:
        """获取迁移状态摘要"""
        if not self._migrations:
            self.discover_migrations()
        applied = await self.get_applied_versions()
        pending = await self.get_pending()
        return {
            "total_migrations": len(self._migrations),
            "applied": len(applied),
            "pending": len(pending),
            "applied_versions": applied,
            "pending_versions": [m["version"] for m in pending],
        }

    @staticmethod
    def _version_key(version: str):
        """将版本号字符串转为可排序的元组，如 '2.0.1' -> (2, 0, 1)"""
        parts = []
        for p in version.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(p)
        return tuple(parts)

