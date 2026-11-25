"""
TradingAgents-CN v2.1.0 FastAPI Backend
主应用程序入口

Copyright (c) 2024-2026 hsliuping. All rights reserved.
版权所有 (c) 2024-2026 hsliuping。保留所有权利。

This software is proprietary and confidential. Unauthorized copying, distribution,
or use of this software, via any medium, is strictly prohibited.
本软件为专有和机密软件。严禁通过任何媒介未经授权复制、分发或使用本软件。

For commercial licensing, please contact: hsliup@163.com
商业许可咨询，请联系：hsliup@163.com
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager
import asyncio
from pathlib import Path

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.logging_config import setup_logging
from app.router_registry import register_routers
from app.services.basics_sync_service import get_basics_sync_service
from app.services.multi_source_basics_sync_service import MultiSourceBasicsSyncService
from app.services.scheduler_service import set_scheduler_instance
from app.worker.tushare_sync_service import (
    run_tushare_realtime_quotes_hourly,
    run_tushare_basic_info_sync,
    # run_tushare_quotes_sync,  # 🔥 已禁用，统一由 run_tushare_realtime_quotes_hourly 管理
    run_tushare_historical_sync,
    run_tushare_financial_sync,
    run_tushare_status_check
)
from app.worker.akshare_sync_service import (
    run_akshare_basic_info_sync,
    run_akshare_quotes_sync,
    run_akshare_historical_sync,
    run_akshare_financial_sync,
    run_akshare_status_check
)
from app.worker.baostock_sync_service import (
    run_baostock_basic_info_sync,
    run_baostock_daily_quotes_sync,
    run_baostock_historical_sync,
    run_baostock_status_check
)
from app.worker.etf_sync_service import run_etf_sync
from app.worker.favorites_sync_task import run_favorites_data_sync
# 港股和美股改为按需获取+缓存模式，不再需要定时同步任务
# from app.worker.hk_sync_service import ...
# from app.worker.us_sync_service import ...
from app.middleware.operation_log_middleware import OperationLogMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.services.quotes_ingestion_service import QuotesIngestionService


def get_version() -> str:
    """从 VERSION 文件读取版本号"""
    try:
        version_file = Path(__file__).parent.parent / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    return "2.1.0"  # 默认版本号


def get_build_info() -> dict:
    """从 BUILD_INFO 文件读取构建信息"""
    try:
        build_info_file = Path(__file__).parent.parent / "BUILD_INFO"
        if build_info_file.exists():
            import json
            return json.loads(build_info_file.read_text(encoding='utf-8'))
    except Exception as e:
        logging.debug(f"Failed to read BUILD_INFO: {e}")
    return {}




async def _print_config_summary(logger):
    """显示配置摘要"""
    try:
        logger.info("=" * 70)
        logger.info("📋 TradingAgents-CN Configuration Summary")
        logger.info("=" * 70)

        # .env 文件路径信息
        import os
        from pathlib import Path

        current_dir = Path.cwd()
        logger.info(f"📁 Current working directory: {current_dir}")

        # 支持通过 DOTENV_FILE 环境变量指定不同的 .env 文件（如京东云模式用 .env.jdyun）
        env_filename = os.getenv("DOTENV_FILE", ".env")
        logger.info(f"📄 Environment file: {env_filename}")

        # 检查可能的 .env 文件位置
        env_files_to_check = [
            current_dir / env_filename,
            current_dir / "app" / env_filename,
            Path(__file__).parent.parent / env_filename,  # 项目根目录
        ]

        logger.info("🔍 Checking .env file locations:")
        env_file_found = False
        for env_file in env_files_to_check:
            if env_file.exists():
                logger.info(f"  ✅ Found: {env_file} (size: {env_file.stat().st_size} bytes)")
                env_file_found = True
                # 显示文件的前几行（隐藏敏感信息）
                try:
                    with open(env_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:5]  # 只读前5行
                        logger.info(f"     Preview (first 5 lines):")
                        for i, line in enumerate(lines, 1):
                            # 隐藏包含密码、密钥等敏感信息的行
                            if any(keyword in line.upper() for keyword in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN']):
                                logger.info(f"       {i}: {line.split('=')[0]}=***")
                            else:
                                logger.info(f"       {i}: {line.strip()}")
                except Exception as e:
                    logger.warning(f"     Could not preview file: {e}")
            else:
                logger.info(f"  ❌ Not found: {env_file}")
        
        if not env_file_found:
            logger.warning("⚠️  No .env file found in checked locations")
        
        # Pydantic Settings 配置加载状态
        logger.info("⚙️  Pydantic Settings Configuration:")
        logger.info(f"  • Settings class: {settings.__class__.__name__}")
        logger.info(f"  • Config source: {getattr(settings.model_config, 'env_file', 'Not specified')}")
        logger.info(f"  • Encoding: {getattr(settings.model_config, 'env_file_encoding', 'Not specified')}")
        
        # 显示一些关键配置值的来源（环境变量 vs 默认值）
        key_settings = ['HOST', 'PORT', 'DEBUG', 'MONGODB_HOST', 'REDIS_HOST']
        logger.info("  • Key settings sources:")
        for setting_name in key_settings:
            env_var_name = setting_name
            env_value = os.getenv(env_var_name)
            config_value = getattr(settings, setting_name, None)
            if env_value is not None:
                logger.info(f"    - {setting_name}: from environment variable ({config_value})")
            else:
                logger.info(f"    - {setting_name}: using default value ({config_value})")
        
        # 环境信息
        env = "Production" if settings.is_production else "Development"
        logger.info(f"Environment: {env}")

        # 数据库连接
        logger.info(f"MongoDB: {settings.MONGODB_HOST}:{settings.MONGODB_PORT}/{settings.MONGODB_DATABASE}")
        logger.info(f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")

        # 代理配置
        import os
        if settings.PROXY_ENABLED and (settings.HTTP_PROXY or settings.HTTPS_PROXY):
            logger.info("Proxy Configuration:")
            logger.info(f"  🔧 PROXY_ENABLED: True")
            if settings.HTTP_PROXY:
                logger.info(f"  HTTP_PROXY: {settings.HTTP_PROXY}")
            if settings.HTTPS_PROXY:
                logger.info(f"  HTTPS_PROXY: {settings.HTTPS_PROXY}")
            if settings.NO_PROXY:
                # 只显示前3个域名
                no_proxy_list = settings.NO_PROXY.split(',')
                if len(no_proxy_list) <= 3:
                    logger.info(f"  NO_PROXY: {settings.NO_PROXY}")
                else:
                    logger.info(f"  NO_PROXY: {','.join(no_proxy_list[:3])}... ({len(no_proxy_list)} domains)")
            logger.info(f"  ✅ Proxy environment variables set successfully")
        else:
            if settings.PROXY_ENABLED:
                logger.info("Proxy: Enabled but not configured (no proxy address)")
            else:
                logger.info("Proxy: Disabled (direct connection)")

        # 检查大模型配置
        try:
            from app.services.config_service import config_service
            config = await config_service.get_system_config()
            if config and config.llm_configs:
                enabled_llms = [llm for llm in config.llm_configs if llm.enabled]
                logger.info(f"Enabled LLMs: {len(enabled_llms)}")
                if enabled_llms:
                    for llm in enabled_llms[:3]:  # 只显示前3个
                        logger.info(f"  • {llm.provider}: {llm.model_name}")
                    if len(enabled_llms) > 3:
                        logger.info(f"  • ... and {len(enabled_llms) - 3} more")
                else:
                    logger.warning("⚠️  No LLM enabled. Please configure at least one LLM in Web UI.")
            else:
                logger.warning("⚠️  No LLM configured. Please configure at least one LLM in Web UI.")
        except Exception as e:
            logger.warning(f"⚠️  Failed to check LLM configs: {e}")

        # 检查数据源配置
        try:
            if config and config.data_source_configs:
                enabled_sources = [ds for ds in config.data_source_configs if ds.enabled]
                logger.info(f"Enabled Data Sources: {len(enabled_sources)}")
                if enabled_sources:
                    for ds in enabled_sources[:3]:  # 只显示前3个
                        logger.info(f"  • {ds.type.value}: {ds.name}")
                    if len(enabled_sources) > 3:
                        logger.info(f"  • ... and {len(enabled_sources) - 3} more")
            else:
                logger.info("Data Sources: Using default (AKShare)")
        except Exception as e:
            logger.warning(f"⚠️  Failed to check data source configs: {e}")

        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"Failed to print config summary: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    setup_logging()
    logger = logging.getLogger("app.main")

    # 验证启动配置
    try:
        from app.core.startup_validator import validate_startup_config
        validate_startup_config()
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        raise

    await init_db()

    # 执行数据库迁移
    try:
        from app.core.database import get_mongo_db as _get_db
        from migrations.runner import MigrationRunner

        _mig_db = _get_db()
        _runner = MigrationRunner(_mig_db)
        _results = await _runner.run_pending()
        if _results:
            _ok = sum(1 for r in _results if r["status"] == "success")
            _fail = sum(1 for r in _results if r["status"] == "failed")
            logger.info(f"📦 数据库迁移完成: {_ok} 成功, {_fail} 失败")
        else:
            logger.info("📦 数据库已是最新版本")
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        # 迁移失败不阻止启动，但记录错误
        # 如果需要强制要求迁移成功才启动，取消下一行注释：
        # raise

    # 首次启动引导：空库时依据 ADMIN_DEFAULT_PASSWORD 创建初始管理员（社区版无注册接口）
    try:
        from app.services.user_service import bootstrap_first_admin
        await bootstrap_first_admin()
    except Exception as e:
        logger.error(f"❌ 初始管理员引导异常: {e}")

    # 首次启动自举：导入社区版最小系统配置（幂等，集合非空则跳过）
    # 须在 ensure_system_prompt_templates 之前执行，否则 prompt_templates 被后者占位后本包跳过
    try:
        from app.services.community_bootstrap_service import import_bootstrap_config
        await import_bootstrap_config()
    except Exception as e:
        logger.error(f"❌ 启动配置导入失败（不影响服务启动）: {e}", exc_info=True)

    # 初始化自定义工具
    try:
        from app.core.database import get_mongo_db
        from core.tools.custom_tool import CustomToolDefinition, register_custom_tool
        
        db = get_mongo_db()
        cursor = db.custom_tools.find()
        async for doc in cursor:
            try:
                # 移除 _id 字段以符合 Pydantic 模型
                if "_id" in doc:
                    del doc["_id"]
                definition = CustomToolDefinition(**doc)
                await register_custom_tool(definition)
                logger.info(f"✅ Loaded custom tool: {definition.id}")
            except Exception as e:
                logger.error(f"❌ Failed to load custom tool {doc.get('id')}: {e}")
                
        logger.info("Custom tools initialization completed")
    except Exception as e:
        logger.error(f"❌ Custom tools initialization failed: {e}")

    # 初始化 Skill：将 active/enabled 的 Skill 注册到 ToolRegistry，供 Agent 运行时调用
    try:
        from app.core.database import get_mongo_db
        from core.tools import get_tool_registry
        from core.tools.external_skill_loader import load_external_skills_to_registry
        from app.routers.skills import _register_skill_to_registry

        db = get_mongo_db()
        standard_count = 0
        async for doc in db.skills.find({"enabled": True}):
            await _register_skill_to_registry(doc)
            standard_count += 1
        external_count = await load_external_skills_to_registry(db, get_tool_registry())
        logger.info(f"✅ Skill 初始化完成，已加载 {standard_count} 个标准 Skill、{external_count} 个 AI 生成 Skill")

        # 初始化工具执行日志记录器
        from core.tools.execution_logger import get_tool_execution_logger
        get_tool_execution_logger().set_db(db)
        logger.info("✅ 工具执行日志记录器已初始化")
    except Exception as e:
        logger.error(f"❌ Skill 初始化失败: {e}", exc_info=True)

    # 恢复已启用的 MCP 服务器工具到 ToolRegistry
    # 后端重启后，MCP 工具不会自动注册，需要从 mcp_server_configs 集合恢复
    try:
        from app.pro.services.mcp_service import MCPService
        mcp_service = MCPService(db)
        await mcp_service.restore_enabled_servers()
        logger.info("✅ MCP 服务器工具恢复完成")
    except Exception as e:
        logger.error(f"❌ MCP 服务器工具恢复失败: {e}", exc_info=True)

    #  配置桥接：将统一配置写入环境变量，供 TradingAgents 核心库使用
    try:
        from app.core.config_bridge import bridge_config_to_env
        bridge_config_to_env()
    except Exception as e:
        logger.warning(f"⚠️  配置桥接失败: {e}")
        logger.warning("⚠️  TradingAgents 将使用 .env 文件中的配置")

    # 🔧 京东云合作版：首次启动时从环境变量初始化数据库配置
    try:
        from app.services.jdyun_init import init_jdyun_config
        init_jdyun_config()
    except Exception as e:
        logger.warning(f"⚠️  京东云配置初始化失败: {e}")

    # 启动期同步能力索引：工具元数据变更后，重启即可增量写入向量库。
    # 改为后台异步任务，避免 Embedding 模型加载阻塞项目启动
    async def _sync_capability_index_background():
        """后台异步同步能力索引，不阻塞启动"""
        try:
            # 延迟 5 秒，让 uvicorn 先完全启动并监听端口
            await asyncio.sleep(5)

            from app.core.database import get_mongo_db
            from app.services.capability_index_service import CapabilityIndexService

            result = await CapabilityIndexService(get_mongo_db()).ensure_index()
            logger.info(
                "✅ 能力索引同步完成: %s %d/%d backend=%s",
                result.sync_mode,
                result.indexed_documents,
                result.total_documents,
                result.vector_backend,
            )

            # 索引跳过时，向所有管理员发送系统通知
            if result.sync_mode.startswith("skipped_"):
                try:
                    from app.services.user_service import UserService
                    from app.services.notifications_service import get_notifications_service
                    from app.models.notification import NotificationCreate

                    user_svc = UserService()
                    users = await user_svc.list_users(limit=100)
                    notif_svc = get_notifications_service()

                    skip_reason = "Embedding API 不可用" if "embedding" in result.sync_mode else "未配置 Embedding"
                    for u in users:
                        await notif_svc.create_and_publish(NotificationCreate(
                            user_id=u.id,
                            type="system",
                            title="能力索引未构建",
                            content=f"系统启动时能力索引构建被跳过（{skip_reason}）。请先在系统设置中配置有效的 Embedding API Key，然后在「系统设置 -> 工具能力索引」中手动重建索引。",
                            source="capability_index",
                            severity="warning",
                        ))
                    logger.info("📢 已向 %d 位用户发送能力索引跳过通知", len(users))
                except Exception as ne:
                    logger.warning(f"⚠️ 发送能力索引通知失败: {ne}")
        except Exception as e:
            logger.error(f"❌ 能力索引同步失败: {e}", exc_info=True)

    # 创建后台任务，不阻塞启动
    asyncio.create_task(_sync_capability_index_background())
    logger.info("📋 能力索引同步已在后台启动")

    # 启动期同步用户手册向量索引：手册内容变更后重启即自动重建，
    # 让使用问答机器人能基于向量语义检索回答"怎么做分析"等自然语言问题
    async def _sync_user_manual_index_background():
        """后台异步构建用户手册向量索引，不阻塞启动"""
        try:
            from core.knowledge.user_manual_manager import UserManualManager
            from app.core.database import get_mongo_db

            manager = UserManualManager(db=get_mongo_db())
            if not manager.available:
                logger.warning(
                    "⚠️ [用户手册索引] 向量库/Embedding 不可用，跳过构建。"
                    "使用问答机器人将回退到关键字匹配模式。"
                )
                return

            # 延迟 3 秒，让 uvicorn 先完全启动并监听端口
            await asyncio.sleep(3)

            # 在独立线程中执行同步索引，避免阻塞事件循环
            # ensure_indexed 是同步方法（含大量 embedding 请求），
            # 直接在协程中调用会阻塞 uvicorn 监听端口
            result = await asyncio.to_thread(manager.ensure_indexed, force=False)
            if result["rebuilt"]:
                logger.info(
                    "✅ 用户手册索引构建完成: %d 个切片，来源 %d 份手册，签名=%s",
                    result["sections_count"],
                    result["manuals_count"],
                    result["signature"][:8],
                )
            elif result["skipped"]:
                logger.info(
                    "📋 用户手册索引跳过重建（签名一致），现有 %d 个切片",
                    result["sections_count"],
                )
            else:
                logger.warning(
                    "⚠️ 用户手册索引构建失败: %s",
                    result.get("error", "未知原因"),
                )
        except Exception as e:
            logger.error(f"❌ 用户手册索引同步失败: {e}", exc_info=True)

    asyncio.create_task(_sync_user_manual_index_background())
    logger.info("📖 用户手册索引同步已在后台启动")

    # 启动期同步系统默认提示词模板：将代码中的 fallback 提示词写入数据库统一管理
    try:
        from app.services.system_prompt_seed_service import ensure_system_prompt_templates
        await ensure_system_prompt_templates()
        logger.info("✅ 系统默认提示词模板同步完成")
    except Exception as e:
        logger.error(f"❌ 系统默认提示词模板同步失败: {e}", exc_info=True)

    # Apply dynamic settings (log_level, enable_monitoring) from ConfigProvider
    try:
        from app.services.config_provider import provider as config_provider  # local import to avoid early DB init issues
        eff = await config_provider.get_effective_system_settings()
        desired_level = str(eff.get("log_level", "INFO")).upper()
        setup_logging(log_level=desired_level)
        for name in ("webapi", "worker", "uvicorn", "fastapi"):
            logging.getLogger(name).setLevel(desired_level)
        try:
            from app.middleware.operation_log_middleware import set_operation_log_enabled
            set_operation_log_enabled(bool(eff.get("enable_monitoring", True)))
        except Exception:
            pass
    except Exception as e:
        logging.getLogger("webapi").warning(f"Failed to apply dynamic settings: {e}")

    # 初始化工作流注册表
    try:
        from app.services.workflow_registry import initialize_builtin_workflows
        initialize_builtin_workflows()
        logger.info("✅ 工作流注册表初始化完成")
    except Exception as e:
        logger.error(f"❌ 工作流注册表初始化失败: {e}")

    # 显示配置摘要
    logger.info("⏳ 开始显示配置摘要")
    await _print_config_summary(logger)
    logger.info("✅ 配置摘要显示完成")

    # 🔥 启动线程池 Worker（在 Backend 进程内处理队列任务）
    try:
        logger.info("⏳ 开始启动线程池 Worker")
        from app.services.thread_worker import start_thread_worker
        max_workers = getattr(settings, 'WORKER_MAX_CONCURRENT', 3)
        await asyncio.wait_for(start_thread_worker(max_workers=max_workers), timeout=20.0)
        logger.info(f"✅ 线程池 Worker 已启动 (max_workers={max_workers})")
        logger.info("✅ 线程池 Worker 启动阶段完成")
    except Exception as e:
        logger.error(f"❌ 线程池 Worker 启动失败: {e}", exc_info=True)
        # 不阻止 Backend 启动，只是队列任务不会被处理

    logger.info("TradingAgents FastAPI backend started")

    # 初始化交易日历缓存（确定今日/最近一个真实交易日，供 JIT 数据新鲜度判断使用）
    try:
        from app.services.trading_calendar_service import get_trading_calendar_service
        await get_trading_calendar_service().warm_up()
    except Exception as e:
        logger.warning(f"⚠️ 交易日历缓存初始化失败（不影响启动）: {e}")

    # 启动期：若需要在休市时补充上一交易日收盘快照
    if settings.QUOTES_BACKFILL_ON_STARTUP:
        try:
            qi = QuotesIngestionService()
            await qi.ensure_indexes()
            await qi.backfill_last_close_snapshot_if_needed()
        except Exception as e:
            logger.warning(f"Startup backfill failed (ignored): {e}")

    # 启动每日定时任务：可配置
    scheduler: AsyncIOScheduler | None = None
    try:
        from croniter import croniter
    except Exception:
        croniter = None  # 可选依赖
    try:
        # 🔥 配置 APScheduler：同一任务不允许并发执行
        # max_instances=1 确保同一任务同时只能有一个实例在执行
        # 如果任务正在执行，新的触发会被跳过
        from apscheduler.executors.asyncio import AsyncIOExecutor
        
        # 创建异步执行器
        executors = {
            'default': AsyncIOExecutor()
        }
        
        # 配置 job_defaults：同一任务不允许并发执行
        job_defaults = {
            'coalesce': True,  # 合并错过的任务（如果任务正在执行，跳过新的触发）
            'max_instances': 1,  # 同一任务最多1个实例（不允许并发）
            'misfire_grace_time': 30  # 错过执行时间后30秒内仍可执行
        }
        
        scheduler = AsyncIOScheduler(
            timezone=settings.TIMEZONE,
            executors=executors,
            job_defaults=job_defaults
        )

        # 使用多数据源同步服务（支持自动切换）
        multi_source_service = MultiSourceBasicsSyncService()

        # 🔥 从数据库读取数据源优先级配置（而非硬编码）
        # 排除 local/mongodb 等缓存层，只使用真实 API 数据源
        async def get_preferred_sources_from_db():
            """从数据库读取启用的 API 数据源优先级"""
            try:
                from app.core.data_source_priority import get_enabled_data_sources_async
                all_sources = await get_enabled_data_sources_async("a_shares")
                # 排除缓存层，只保留真实 API 数据源
                api_sources = [s for s in all_sources if s not in ("local", "mongodb", "local_file")]
                # 启动期股票基础信息同步不使用 QMT 作为首选源，避免 QMT 全市场列表拖慢启动。
                filtered_sources = [s for s in api_sources if s != "qmt"]
                if api_sources:
                    logger.info(f"📊 股票基础信息同步原始数据源优先级（来自数据库）: {' > '.join(api_sources)}")
                    if filtered_sources != api_sources:
                        logger.info(f"🧹 股票基础信息同步已排除 QMT 首选优先级，实际顺序: {' > '.join(filtered_sources)}")
                    return filtered_sources or None
                else:
                    logger.warning("⚠️ 数据库中没有启用的 API 数据源，使用默认配置")
                    return None
            except Exception as e:
                logger.error(f"❌ 读取数据源优先级失败: {e}，使用默认配置")
                return None

        # 立即在启动后尝试一次（不阻塞）
        async def run_sync_with_sources():
            preferred_sources = await get_preferred_sources_from_db()
            await multi_source_service.run_full_sync(force=False, preferred_sources=preferred_sources)

        asyncio.create_task(run_sync_with_sources())

        # 配置调度：优先使用 CRON，其次使用 HH:MM
        # 🔥 定时任务也需要从数据库读取最新的数据源优先级
        async def scheduled_sync_with_db_priority():
            """定时任务：每次执行时从数据库读取最新的数据源优先级"""
            preferred_sources = await get_preferred_sources_from_db()
            await multi_source_service.run_full_sync(force=False, preferred_sources=preferred_sources)

        if settings.SYNC_STOCK_BASICS_ENABLED:
            if settings.SYNC_STOCK_BASICS_CRON:
                # 如果提供了cron表达式
                scheduler.add_job(
                    scheduled_sync_with_db_priority,
                    CronTrigger.from_crontab(settings.SYNC_STOCK_BASICS_CRON, timezone=settings.TIMEZONE),
                    id="basics_sync_service",
                    name="股票基础信息同步（多数据源）"
                )
                logger.info(f"📅 Stock basics sync scheduled by CRON: {settings.SYNC_STOCK_BASICS_CRON} ({settings.TIMEZONE})")
            else:
                hh, mm = (settings.SYNC_STOCK_BASICS_TIME or "06:30").split(":")
                scheduler.add_job(
                    scheduled_sync_with_db_priority,
                    CronTrigger(hour=int(hh), minute=int(mm), timezone=settings.TIMEZONE),
                    id="basics_sync_service",
                    name="股票基础信息同步（多数据源）"
                )
                logger.info(f"📅 Stock basics sync scheduled daily at {settings.SYNC_STOCK_BASICS_TIME} ({settings.TIMEZONE})")

        # 实时行情入库任务（每N秒），内部自判交易时段
        if settings.QUOTES_INGEST_ENABLED:
            quotes_ingestion = QuotesIngestionService()
            await quotes_ingestion.ensure_indexes()
            scheduler.add_job(
                quotes_ingestion.run_once,  # coroutine function; AsyncIOScheduler will await it
                IntervalTrigger(seconds=settings.QUOTES_INGEST_INTERVAL_SECONDS, timezone=settings.TIMEZONE),
                id="quotes_ingestion_service",
                name="实时行情入库服务"
            )
            logger.info(f"⏱ 实时行情入库任务已启动: 每 {settings.QUOTES_INGEST_INTERVAL_SECONDS}s")

        # Tushare统一数据同步任务配置
        logger.info("🔄 配置Tushare统一数据同步任务...")

        # 基础信息同步任务
        scheduler.add_job(
            run_tushare_basic_info_sync,
            CronTrigger.from_crontab(settings.TUSHARE_BASIC_INFO_SYNC_CRON, timezone=settings.TIMEZONE),
            id="tushare_basic_info_sync",
            name="股票基础信息同步（Tushare）",
            kwargs={"force_update": False}
        )
        if not (settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_BASIC_INFO_SYNC_ENABLED):
            scheduler.pause_job("tushare_basic_info_sync")
            logger.info(f"⏸️ Tushare基础信息同步已添加但暂停: {settings.TUSHARE_BASIC_INFO_SYNC_CRON}")
        else:
            logger.info(f"📅 Tushare基础信息同步已配置: {settings.TUSHARE_BASIC_INFO_SYNC_CRON}")

        # 🔥 已禁用旧的实时行情同步任务，统一由 run_tushare_realtime_quotes_hourly 管理
        # 避免与每小时31分的定时任务冲突（免费用户每小时只能调用一次）
        # scheduler.add_job(
        #     run_tushare_quotes_sync,
        #     CronTrigger.from_crontab(settings.TUSHARE_QUOTES_SYNC_CRON, timezone=settings.TIMEZONE),
        #     id="tushare_quotes_sync",
        #     name="实时行情同步（Tushare）"
        # )
        logger.info(f"⏸️ Tushare实时行情同步任务已禁用，统一由每小时31分的定时任务管理")

        # Tushare实时行情每小时同步任务（免费用户每小时只能调用一次）
        scheduler.add_job(
            run_tushare_realtime_quotes_hourly,
            CronTrigger.from_crontab(settings.TUSHARE_REALTIME_QUOTES_HOURLY_CRON, timezone=settings.TIMEZONE),
            id="tushare_realtime_quotes_hourly",
            name="实时行情每小时同步（Tushare，免费用户每小时31分）"
        )
        if not (settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_REALTIME_QUOTES_HOURLY_ENABLED):
            scheduler.pause_job("tushare_realtime_quotes_hourly")
            logger.info(f"⏸️ Tushare实时行情每小时同步已添加但暂停: {settings.TUSHARE_REALTIME_QUOTES_HOURLY_CRON}")
        else:
            logger.info(f"📈 Tushare实时行情每小时同步已配置: {settings.TUSHARE_REALTIME_QUOTES_HOURLY_CRON} (每小时31分执行，15:00后自动保存到历史数据)")

        # 历史数据同步任务
        scheduler.add_job(
            run_tushare_historical_sync,
            CronTrigger.from_crontab(settings.TUSHARE_HISTORICAL_SYNC_CRON, timezone=settings.TIMEZONE),
            id="tushare_historical_sync",
            name="历史数据同步（Tushare）",
            kwargs={"incremental": True}
        )
        if not (settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_HISTORICAL_SYNC_ENABLED):
            scheduler.pause_job("tushare_historical_sync")
            logger.info(f"⏸️ Tushare历史数据同步已添加但暂停: {settings.TUSHARE_HISTORICAL_SYNC_CRON}")
        else:
            logger.info(f"📊 Tushare历史数据同步已配置: {settings.TUSHARE_HISTORICAL_SYNC_CRON}")

        # 财务数据同步任务
        scheduler.add_job(
            run_tushare_financial_sync,
            CronTrigger.from_crontab(settings.TUSHARE_FINANCIAL_SYNC_CRON, timezone=settings.TIMEZONE),
            id="tushare_financial_sync",
            name="财务数据同步（Tushare）"
        )
        if not (settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_FINANCIAL_SYNC_ENABLED):
            scheduler.pause_job("tushare_financial_sync")
            logger.info(f"⏸️ Tushare财务数据同步已添加但暂停: {settings.TUSHARE_FINANCIAL_SYNC_CRON}")
        else:
            logger.info(f"💰 Tushare财务数据同步已配置: {settings.TUSHARE_FINANCIAL_SYNC_CRON}")

        # 状态检查任务
        scheduler.add_job(
            run_tushare_status_check,
            CronTrigger.from_crontab(settings.TUSHARE_STATUS_CHECK_CRON, timezone=settings.TIMEZONE),
            id="tushare_status_check",
            name="数据源状态检查（Tushare）"
        )
        if not (settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_STATUS_CHECK_ENABLED):
            scheduler.pause_job("tushare_status_check")
            logger.info(f"⏸️ Tushare状态检查已添加但暂停: {settings.TUSHARE_STATUS_CHECK_CRON}")
        else:
            logger.info(f"🔍 Tushare状态检查已配置: {settings.TUSHARE_STATUS_CHECK_CRON}")

        # AKShare统一数据同步任务配置
        logger.info("🔄 配置AKShare统一数据同步任务...")

        # 基础信息同步任务
        scheduler.add_job(
            run_akshare_basic_info_sync,
            CronTrigger.from_crontab(settings.AKSHARE_BASIC_INFO_SYNC_CRON, timezone=settings.TIMEZONE),
            id="akshare_basic_info_sync",
            name="股票基础信息同步（AKShare）",
            kwargs={"force_update": False}
        )
        if not (settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_BASIC_INFO_SYNC_ENABLED):
            scheduler.pause_job("akshare_basic_info_sync")
            logger.info(f"⏸️ AKShare基础信息同步已添加但暂停: {settings.AKSHARE_BASIC_INFO_SYNC_CRON}")
        else:
            logger.info(f"📅 AKShare基础信息同步已配置: {settings.AKSHARE_BASIC_INFO_SYNC_CRON}")

        # 实时行情同步任务
        scheduler.add_job(
            run_akshare_quotes_sync,
            CronTrigger.from_crontab(settings.AKSHARE_QUOTES_SYNC_CRON, timezone=settings.TIMEZONE),
            id="akshare_quotes_sync",
            name="实时行情同步（AKShare）"
        )
        if not (settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_QUOTES_SYNC_ENABLED):
            scheduler.pause_job("akshare_quotes_sync")
            logger.info(f"⏸️ AKShare行情同步已添加但暂停: {settings.AKSHARE_QUOTES_SYNC_CRON}")
        else:
            logger.info(f"📈 AKShare行情同步已配置: {settings.AKSHARE_QUOTES_SYNC_CRON}")

        # 历史数据同步任务
        scheduler.add_job(
            run_akshare_historical_sync,
            CronTrigger.from_crontab(settings.AKSHARE_HISTORICAL_SYNC_CRON, timezone=settings.TIMEZONE),
            id="akshare_historical_sync",
            name="历史数据同步（AKShare）",
            kwargs={"incremental": True}
        )
        if not (settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_HISTORICAL_SYNC_ENABLED):
            scheduler.pause_job("akshare_historical_sync")
            logger.info(f"⏸️ AKShare历史数据同步已添加但暂停: {settings.AKSHARE_HISTORICAL_SYNC_CRON}")
        else:
            logger.info(f"📊 AKShare历史数据同步已配置: {settings.AKSHARE_HISTORICAL_SYNC_CRON}")

        # 财务数据同步任务
        scheduler.add_job(
            run_akshare_financial_sync,
            CronTrigger.from_crontab(settings.AKSHARE_FINANCIAL_SYNC_CRON, timezone=settings.TIMEZONE),
            id="akshare_financial_sync",
            name="财务数据同步（AKShare）"
        )
        if not (settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_FINANCIAL_SYNC_ENABLED):
            scheduler.pause_job("akshare_financial_sync")
            logger.info(f"⏸️ AKShare财务数据同步已添加但暂停: {settings.AKSHARE_FINANCIAL_SYNC_CRON}")
        else:
            logger.info(f"💰 AKShare财务数据同步已配置: {settings.AKSHARE_FINANCIAL_SYNC_CRON}")

        # 状态检查任务
        scheduler.add_job(
            run_akshare_status_check,
            CronTrigger.from_crontab(settings.AKSHARE_STATUS_CHECK_CRON, timezone=settings.TIMEZONE),
            id="akshare_status_check",
            name="数据源状态检查（AKShare）"
        )
        if not (settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_STATUS_CHECK_ENABLED):
            scheduler.pause_job("akshare_status_check")
            logger.info(f"⏸️ AKShare状态检查已添加但暂停: {settings.AKSHARE_STATUS_CHECK_CRON}")
        else:
            logger.info(f"🔍 AKShare状态检查已配置: {settings.AKSHARE_STATUS_CHECK_CRON}")

        # BaoStock统一数据同步任务配置
        logger.info("🔄 配置BaoStock统一数据同步任务...")

        # 基础信息同步任务
        scheduler.add_job(
            run_baostock_basic_info_sync,
            CronTrigger.from_crontab(settings.BAOSTOCK_BASIC_INFO_SYNC_CRON, timezone=settings.TIMEZONE),
            id="baostock_basic_info_sync",
            name="股票基础信息同步（BaoStock）"
        )
        if not (settings.BAOSTOCK_UNIFIED_ENABLED and settings.BAOSTOCK_BASIC_INFO_SYNC_ENABLED):
            scheduler.pause_job("baostock_basic_info_sync")
            logger.info(f"⏸️ BaoStock基础信息同步已添加但暂停: {settings.BAOSTOCK_BASIC_INFO_SYNC_CRON}")
        else:
            logger.info(f"📋 BaoStock基础信息同步已配置: {settings.BAOSTOCK_BASIC_INFO_SYNC_CRON}")

        # 日K线同步任务（注意：BaoStock不支持实时行情）
        scheduler.add_job(
            run_baostock_daily_quotes_sync,
            CronTrigger.from_crontab(settings.BAOSTOCK_DAILY_QUOTES_SYNC_CRON, timezone=settings.TIMEZONE),
            id="baostock_daily_quotes_sync",
            name="日K线数据同步（BaoStock）"
        )
        if not (settings.BAOSTOCK_UNIFIED_ENABLED and settings.BAOSTOCK_DAILY_QUOTES_SYNC_ENABLED):
            scheduler.pause_job("baostock_daily_quotes_sync")
            logger.info(f"⏸️ BaoStock日K线同步已添加但暂停: {settings.BAOSTOCK_DAILY_QUOTES_SYNC_CRON}")
        else:
            logger.info(f"📈 BaoStock日K线同步已配置: {settings.BAOSTOCK_DAILY_QUOTES_SYNC_CRON} (注意：BaoStock不支持实时行情)")

        # 历史数据同步任务
        scheduler.add_job(
            run_baostock_historical_sync,
            CronTrigger.from_crontab(settings.BAOSTOCK_HISTORICAL_SYNC_CRON, timezone=settings.TIMEZONE),
            id="baostock_historical_sync",
            name="历史数据同步（BaoStock）"
        )
        if not (settings.BAOSTOCK_UNIFIED_ENABLED and settings.BAOSTOCK_HISTORICAL_SYNC_ENABLED):
            scheduler.pause_job("baostock_historical_sync")
            logger.info(f"⏸️ BaoStock历史数据同步已添加但暂停: {settings.BAOSTOCK_HISTORICAL_SYNC_CRON}")
        else:
            logger.info(f"📊 BaoStock历史数据同步已配置: {settings.BAOSTOCK_HISTORICAL_SYNC_CRON}")

        # 状态检查任务
        scheduler.add_job(
            run_baostock_status_check,
            CronTrigger.from_crontab(settings.BAOSTOCK_STATUS_CHECK_CRON, timezone=settings.TIMEZONE),
            id="baostock_status_check",
            name="数据源状态检查（BaoStock）"
        )
        if not (settings.BAOSTOCK_UNIFIED_ENABLED and settings.BAOSTOCK_STATUS_CHECK_ENABLED):
            scheduler.pause_job("baostock_status_check")
            logger.info(f"⏸️ BaoStock状态检查已添加但暂停: {settings.BAOSTOCK_STATUS_CHECK_CRON}")
        else:
            logger.info(f"🔍 BaoStock状态检查已配置: {settings.BAOSTOCK_STATUS_CHECK_CRON}")

        # ETF 数据同步任务配置
        logger.info("🔄 配置ETF数据同步任务...")

        scheduler.add_job(
            run_etf_sync,
            CronTrigger.from_crontab(settings.ETF_SYNC_CRON, timezone=settings.TIMEZONE),
            id="etf_sync",
            name="ETF 数据同步",
            kwargs={"force_update": False, "days": settings.ETF_SYNC_DAYS, "job_id": "etf_sync"}
        )
        if not settings.ETF_SYNC_ENABLED:
            scheduler.pause_job("etf_sync")
            logger.info(f"⏸️ ETF 数据同步已添加但暂停: {settings.ETF_SYNC_CRON}")
        else:
            logger.info(
                f"📅 ETF 数据同步已配置: {settings.ETF_SYNC_CRON}，"
                f"首次全量补齐、后续按最新入库日期增量同步；"
                f"强制回溯窗口为 {settings.ETF_SYNC_DAYS} 天"
            )

        # 股票关注列表A股数据同步任务配置
        logger.info("🔄 配置股票关注列表A股数据同步任务...")
        
        scheduler.add_job(
            run_favorites_data_sync,
            CronTrigger.from_crontab(settings.FAVORITES_DATA_SYNC_CRON, timezone=settings.TIMEZONE),
            id="favorites_data_sync",
            name="股票关注列表A股数据同步（历史数据+财务数据）"
        )
        if not settings.FAVORITES_DATA_SYNC_ENABLED:
            scheduler.pause_job("favorites_data_sync")
            logger.info(f"⏸️ 股票关注列表A股数据同步已添加但暂停: {settings.FAVORITES_DATA_SYNC_CRON}")
        else:
            logger.info(f"⭐ 股票关注列表A股数据同步已配置: {settings.FAVORITES_DATA_SYNC_CRON} (历史数据+财务数据)")

        # 新闻数据同步任务配置（使用AKShare同步所有股票新闻）
        logger.info("🔄 配置新闻数据同步任务...")

        from app.worker.akshare_sync_service import get_akshare_sync_service

        async def run_news_sync():
            """运行新闻同步任务 - 使用AKShare同步股票关注列表新闻"""
            try:
                logger.info("📰 开始新闻数据同步（AKShare - 仅股票关注列表）...")
                service = await get_akshare_sync_service()
                # 🔥 设置正确的 job_id，确保进度更新和状态标记使用正确的任务ID
                service._current_job_id = "news_sync"
                result = await service.sync_news_data(
                    symbols=None,  # None + favorites_only=True 表示只同步股票关注列表
                    max_news_per_stock=settings.NEWS_SYNC_MAX_PER_SOURCE,
                    favorites_only=True  # 只同步股票关注列表
                )
                logger.info(
                    f"✅ 新闻同步完成: "
                    f"处理{result['total_processed']}只股票关注列表, "
                    f"成功{result['success_count']}只, "
                    f"失败{result['error_count']}只, "
                    f"新闻总数{result['news_count']}条, "
                    f"耗时{(datetime.utcnow() - result['start_time']).total_seconds():.2f}秒"
                )
            except Exception as e:
                logger.error(f"❌ 新闻同步失败: {e}", exc_info=True)

        # ==================== 港股/美股数据配置 ====================
        # 港股和美股采用按需获取+缓存模式，不再配置定时同步任务
        logger.info("🇭🇰 港股数据采用按需获取+缓存模式")
        logger.info("🇺🇸 美股数据采用按需获取+缓存模式")

        scheduler.add_job(
            run_news_sync,
            CronTrigger.from_crontab(settings.NEWS_SYNC_CRON, timezone=settings.TIMEZONE),
            id="news_sync",
            name="新闻数据同步（AKShare - 仅股票关注列表）"
        )
        if not settings.NEWS_SYNC_ENABLED:
            scheduler.pause_job("news_sync")
            logger.info(f"⏸️ 新闻数据同步已添加但暂停: {settings.NEWS_SYNC_CRON}")
        else:
            logger.info(f"📰 新闻数据同步已配置（仅股票关注列表）: {settings.NEWS_SYNC_CRON}")

        # ==================== 股票关注列表定时分析配置 ====================
        from app.worker.watchlist_analysis_task import run_watchlist_analysis
        scheduler.add_job(
            run_watchlist_analysis,
            CronTrigger.from_crontab(settings.WATCHLIST_ANALYSIS_CRON, timezone=settings.TIMEZONE),
            id="watchlist_analysis",
            name="股票关注列表定时分析"
        )
        if not settings.WATCHLIST_ANALYSIS_ENABLED:
            scheduler.pause_job("watchlist_analysis")
            logger.info(f"⏸️ 股票关注列表定时分析已添加但暂停: {settings.WATCHLIST_ANALYSIS_CRON}")
        else:
            logger.info(f"📊 股票关注列表定时分析已配置: {settings.WATCHLIST_ANALYSIS_CRON}")

        # ==================== 交易日历缓存刷新任务 ====================
        # 每日 18:30 刷新一次：Tushare daily_basic 数据一般在收盘后（15:00）
        # 约 1~3 小时才稳定入库，18:30 之后获取当日数据才可靠。
        # 启动时已由 warm_up() 完成初始化，本任务负责当日收盘后的更新。
        async def _refresh_trading_calendar():
            try:
                from app.services.trading_calendar_service import get_trading_calendar_service
                await get_trading_calendar_service().warm_up()
                logger.info("🗓️ [TradingCalendar] 交易日历缓存已刷新（18:30 定时）")
            except Exception as _e:
                logger.warning(f"⚠️ [TradingCalendar] 定时刷新失败（不影响运行）: {_e}")

        scheduler.add_job(
            _refresh_trading_calendar,
            CronTrigger(hour=18, minute=30, timezone=settings.TIMEZONE),
            id="trading_calendar_refresh",
            name="交易日历缓存刷新（每日18:30）"
        )
        logger.info("🗓️ 交易日历缓存刷新任务已配置（每日 18:30 执行）")

        # v3.5.0 项4 / v3.6.0 项6：HITL 待确认操作过期清理（每 30 分钟执行一次）
        async def _expire_stale_hitl_operations():
            try:
                from app.core.database import get_mongo_db
                from core.hitl.checkpoint_store import HITLCheckpointService
                db = get_mongo_db()
                if db is not None:
                    svc = HITLCheckpointService(db)
                    cleaned = await svc.expire_stale()
                    if cleaned:
                        logger.info(f"[HITL·定时] 已清理 {cleaned} 条过期待确认操作")
            except Exception as _e:
                logger.warning(f"[HITL·定时] 过期清理失败: {_e}")

        scheduler.add_job(
            _expire_stale_hitl_operations,
            IntervalTrigger(minutes=30, timezone=settings.TIMEZONE),
            id="hitl_expire_stale",
            name="HITL 待确认操作过期清理（每30分钟）"
        )
        logger.info("🔄 HITL 待确认操作过期清理已配置（每 30 分钟）")

        # v3.6.0：Skill 审核过期清理（每 30 分钟执行一次）
        async def _expire_stale_skill_reviews():
            try:
                from app.core.database import get_mongo_db
                from app.pro.services.skill_review_service import SkillReviewService
                db = get_mongo_db()
                if db is not None:
                    svc = SkillReviewService(db=db)
                    cleaned = await svc.expire_stale_reviews()
                    if cleaned:
                        logger.info(f"[SkillReview·定时] 已过期 {cleaned} 条待审核 Skill 记录")
            except Exception as _e:
                logger.warning(f"[SkillReview·定时] 过期清理失败: {_e}")

        scheduler.add_job(
            _expire_stale_skill_reviews,
            IntervalTrigger(minutes=30, timezone=settings.TIMEZONE),
            id="skill_review_expire_stale",
            name="Skill 审核过期清理（每30分钟）"
        )
        logger.info("🔄 Skill 审核过期清理已配置（每 30 分钟）")

        scheduler.start()

        # 设置调度器实例到服务中，以便API可以管理任务
        set_scheduler_instance(scheduler)
        logger.info("✅ 调度器服务已初始化")
        
        # 🔥 检测服务重启导致的挂起任务
        try:
            from app.services.scheduler_service import get_scheduler_service
            scheduler_service = get_scheduler_service()  # 同步函数，不需要await
            await scheduler_service.check_suspended_tasks_on_startup()
        except Exception as e:
            logger.warning(f"⚠️ 检测挂起任务失败（不影响启动）: {e}")
    except Exception as e:
        logger.error(f"❌ 调度器启动失败: {e}", exc_info=True)
        raise  # 抛出异常，阻止应用启动

    try:
        yield
    finally:
        # 关闭时清理

        # 🔥 关闭统一线程池同步服务
        try:
            from app.worker.unified_thread_pool_sync_service import get_unified_thread_pool_sync_service
            unified_sync_service = await get_unified_thread_pool_sync_service()
            unified_sync_service.shutdown(timeout=30.0)
            logger.info("🛑 统一线程池同步服务已停止")
        except Exception as e:
            logger.warning(f"统一线程池同步服务关闭错误: {e}")

        # 🔥 停止财务数据同步服务的线程池
        try:
            from app.worker.financial_data_sync_service import get_financial_sync_service
            financial_sync_service = await get_financial_sync_service()
            if financial_sync_service is not None:
                financial_sync_service.shutdown(timeout=30.0)
                logger.info("🛑 财务数据同步服务线程池已停止")
        except Exception as e:
            logger.warning(f"财务数据同步服务停止错误: {e}")

        # 🔥 停止线程池 Worker
        try:
            from app.services.thread_worker import stop_thread_worker
            await stop_thread_worker()
            logger.info("🛑 线程池 Worker 已停止")
        except Exception as e:
            logger.warning(f"线程池 Worker 停止错误: {e}")

        if scheduler:
            try:
                # 等待正在执行的任务收尾，避免 job 仍在访问 Motor 时数据库/事件循环已被关闭。
                scheduler.shutdown(wait=True)
                logger.info("🛑 Scheduler stopped")
            except Exception as e:
                logger.warning(f"Scheduler shutdown error: {e}")

        try:
            stop_gain_alert_service.stop()
        except Exception as e:
            logger.warning(f"StopGainAlertService cleanup error: {e}")

        # 关闭 UserService MongoDB 连接
        try:
            from app.services.user_service import user_service
            user_service.close()
        except Exception as e:
            logger.warning(f"UserService cleanup error: {e}")

        await close_db()
        logger.info("TradingAgents FastAPI backend stopped")


# 创建FastAPI应用
app = FastAPI(
    title="TradingAgents-CN API",
    description="股票分析与批量队列系统 API",
    version=get_version(),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
    redirect_slashes=False,
)

# 安全中间件
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Session 中间件（用于 Web 前端的 Cookie 认证）
# 注意：必须在 CORS 中间件之后添加
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET,  # 使用相同的密钥
    session_cookie="tradingagents_session",  # Cookie 名称
    max_age=3600,  # 1 小时过期
    same_site="lax",  # CSRF 保护
    https_only=False if settings.DEBUG else True,  # 生产环境使用 HTTPS
)

# 操作日志中间件
app.add_middleware(OperationLogMiddleware)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # 跳过健康检查和静态文件请求的日志
    if request.url.path in ["/health", "/favicon.ico"] or request.url.path.startswith("/static"):
        response = await call_next(request)
        return response

    # 使用webapi logger记录请求
    logger = logging.getLogger("webapi")
    
    # 对于 license/status 接口，记录更详细的信息
    if request.url.path == "/api/license/status":
        auth_header = request.headers.get("authorization", "无")
        # 🔥 安全地访问 session（可能不存在或 SessionMiddleware 未安装）
        session_id = "无"
        try:
            if "session" in request.scope:
                session_id = request.session.get("user_id", "无")
        except (AssertionError, AttributeError, KeyError):
            session_id = "无"
        logger.info(f"🔄 {request.method} {request.url.path} - 开始处理 (Authorization: {auth_header[:20] if len(auth_header) > 20 else auth_header}..., Session: {session_id})")
    else:
        logger.info(f"🔄 {request.method} {request.url.path} - 开始处理")

    response = await call_next(request)
    process_time = time.time() - start_time

    # 记录请求完成
    status_emoji = "✅" if response.status_code < 400 else "❌"
    if request.url.path == "/api/license/status":
        logger.info(f"{status_emoji} {request.method} {request.url.path} - 状态: {response.status_code} - 耗时: {process_time:.3f}s (如果是404，可能是路由未匹配或认证失败)")
    else:
        logger.info(f"{status_emoji} {request.method} {request.url.path} - 状态: {response.status_code} - 耗时: {process_time:.3f}s")

    return response


# 全局异常处理
# 请求ID/Trace-ID 中间件（需作为最外层，放在函数式中间件之后）
from app.middleware.request_id import RequestIDMiddleware
app.add_middleware(RequestIDMiddleware)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Internal server error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )


# 测试端点 - 验证中间件是否工作
@app.get("/api/test-log")
async def test_log():
    """测试日志中间件是否工作"""
    print("🧪 测试端点被调用 - 这条消息应该出现在控制台")
    return {"message": "测试成功", "timestamp": time.time()}


# =============================================================================
# 路由注册
# v3.6.0 社区版开源分离（M1 收敛改造）：全部路由注册收敛至 app/router_registry.py，
# COMMUNITY_ROUTERS 与 PRO_ROUTERS 分列，社区版发布时整体剔除 PRO_ROUTERS 段。
# 见 docs/05-design/v3.0/v3.6.0-community-edition-separation-plan.md §7.1
# =============================================================================
register_routers(app)

logger = logging.getLogger("app.main")


@app.get("/api/system/info", tags=["system"])
async def get_system_info():
    """获取系统版本信息"""
    version = get_version()
    build_info = get_build_info()

    # 如果BUILD_INFO存在，使用其中的信息
    if build_info:
        return {
            "version": build_info.get("version", version),
            "full_version": build_info.get("full_version", version),
            "build_timestamp": build_info.get("build_timestamp"),
            "build_date": build_info.get("build_date"),
            "build_unix": build_info.get("build_unix"),
            "git_commit": build_info.get("git_commit"),
            "build_type": build_info.get("build_type"),
        }

    # 否则只返回主版本号
    return {
        "version": version,
        "full_version": version,
        "build_timestamp": None,
        "build_date": None,
        "build_unix": None,
        "git_commit": None,
        "build_type": None,
    }


@app.get("/")
async def root():
    """根路径，返回API信息"""
    print("🏠 根路径被访问")
    return {
        "name": "TradingAgents-CN API",
        "version": get_version(),
        "status": "running",
        "docs_url": "/docs" if settings.DEBUG else None
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
        reload_dirs=["app"] if settings.DEBUG else None,
        reload_excludes=[
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".git",
            ".pytest_cache",
            "*.log",
            "*.tmp"
        ] if settings.DEBUG else None,
        reload_includes=["*.py"] if settings.DEBUG else None
    )
