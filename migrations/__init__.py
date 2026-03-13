"""
TradingAgents-CN 数据库迁移框架

版本化的 MongoDB 数据库迁移机制：
- 每个版本对应一个迁移脚本
- 启动时自动检测并执行未完成的迁移
- 记录迁移历史到 migration_history 集合
- 支持幂等执行（安全重复运行）

使用方法：
    # 在应用启动时自动执行
    from migrations.runner import MigrationRunner
    runner = MigrationRunner(db)
    await runner.run_pending()
    
    # 命令行工具
    python -m migrations.cli status    # 查看迁移状态
    python -m migrations.cli run       # 执行待迁移
    python -m migrations.cli run --version 2.0.1  # 执行指定版本
"""

