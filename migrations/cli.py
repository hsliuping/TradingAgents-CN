"""
迁移管理命令行工具

用法:
    python -m migrations.cli status              # 查看迁移状态
    python -m migrations.cli run                  # 执行所有待迁移
    python -m migrations.cli run --version 2.0.1  # 执行指定版本
    python -m migrations.cli history              # 查看迁移历史
"""

import asyncio
import argparse
import sys
import os
import logging

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrations.cli")


async def get_db():
    """获取数据库连接"""
    from app.core.database import init_database, get_mongo_db
    await init_database()
    return get_mongo_db()


async def cmd_status():
    """显示迁移状态"""
    from migrations.runner import MigrationRunner

    db = await get_db()
    runner = MigrationRunner(db)
    status = await runner.get_status()

    print("\n" + "=" * 50)
    print("📊 数据库迁移状态")
    print("=" * 50)
    print(f"  总迁移数:   {status['total_migrations']}")
    print(f"  已执行:     {status['applied']}")
    print(f"  待执行:     {status['pending']}")

    if status["applied_versions"]:
        print(f"\n  ✅ 已执行版本:")
        for v in status["applied_versions"]:
            print(f"     - {v}")

    if status["pending_versions"]:
        print(f"\n  ⏳ 待执行版本:")
        for v in status["pending_versions"]:
            print(f"     - {v}")

    print()


async def cmd_run(version: str = None):
    """执行迁移"""
    from migrations.runner import MigrationRunner

    db = await get_db()
    runner = MigrationRunner(db)

    if version:
        print(f"\n🔄 执行指定迁移: {version}")
        result = await runner.run_one(version)
        results = [result]
    else:
        print("\n🔄 执行所有待处理迁移...")
        results = await runner.run_pending()

    if not results:
        print("✅ 没有需要执行的迁移\n")
        return

    print("\n" + "=" * 50)
    print("📋 迁移执行结果")
    print("=" * 50)
    for r in results:
        icon = "✅" if r["status"] == "success" else "❌" if r["status"] == "failed" else "⏭️"
        line = f"  {icon} {r['version']}"
        if "duration_ms" in r:
            line += f" ({r['duration_ms']}ms)"
        if r.get("error"):
            line += f" - {r['error']}"
        print(line)
    print()


async def cmd_history():
    """查看迁移历史"""
    db = await get_db()
    cursor = db.migration_history.find().sort("applied_at", -1)
    docs = await cursor.to_list(length=50)

    print("\n" + "=" * 60)
    print("📜 迁移历史记录")
    print("=" * 60)

    if not docs:
        print("  (无记录)")
    else:
        for doc in docs:
            icon = "✅" if doc.get("status") == "success" else "❌"
            ts = doc.get("applied_at", "").strftime("%Y-%m-%d %H:%M:%S") if doc.get("applied_at") else "N/A"
            dur = doc.get("duration_ms", "?")
            print(f"  {icon} {doc['version']:10s} | {ts} | {dur}ms | {doc.get('description', '')}")
            if doc.get("error"):
                print(f"     ❌ Error: {doc['error']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="TradingAgents-CN 数据库迁移工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    subparsers.add_parser("status", help="查看迁移状态")

    run_parser = subparsers.add_parser("run", help="执行迁移")
    run_parser.add_argument("--version", "-v", help="指定执行某个版本")

    subparsers.add_parser("history", help="查看迁移历史")

    args = parser.parse_args()

    if args.command == "status":
        asyncio.run(cmd_status())
    elif args.command == "run":
        asyncio.run(cmd_run(args.version))
    elif args.command == "history":
        asyncio.run(cmd_history())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

