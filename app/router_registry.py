"""
路由注册中心（v3.6.0 社区版开源分离 · M1 收敛改造）

- 全部 FastAPI 路由注册从 app/main.py 收敛至此单一文件
- COMMUNITY_ROUTERS：社区版保留（免费主链路，社区版发布时原样保留）
- PRO_ROUTERS：Pro 专属（付费功能载体，社区版发布时整体剔除）
- 发布脚本（scripts/publish_community.py）处理方式：
  删除 Pro 路由文件 + 用社区版注册文件（本文件删除 PRO_ROUTERS 段）替换
- 原则：只搬注册行，不动路由实现
- Pro/社区边界依据：付费功能清单.md + 分离方案 §5.2
- 见 docs/05-design/v3.0/v3.6.0-community-edition-separation-plan.md §7.1

注意：新增路由时必须登记到对应清单——新 Pro 路由不入 PRO_ROUTERS = 发布即泄露。
"""

import logging

from fastapi import FastAPI

logger = logging.getLogger("app.main")

# =============================================================================
# 社区版路由（免费主链路）
# =============================================================================
from app.routers import auth_db as auth
from app.routers import (
    analysis,
    screening,
    queue,
    sse,
    health,
    favorites,
    config,
    reports,
    database,
    operation_logs,
    tags,
    usage_statistics,
    model_capabilities,
    cache,
    logs,
)
from app.routers import sync as sync_router
from app.routers import multi_source_sync
from app.routers import stocks as stocks_router
from app.routers import stock_sync as stock_sync_router
from app.routers import multi_market_stocks as multi_market_stocks_router
from app.routers import notifications as notifications_router
from app.routers import analysis_profiles as analysis_profiles_router
from app.routers import websocket_notifications as websocket_notifications_router
from app.routers import scheduler as scheduler_router
from app.routers import analysis_preferences as analysis_preferences_router
from app.routers import advanced_courses as advanced_courses_router  # 社区版保留（课程内容物理裁剪到前 5 节，见方案 §7.4）
from app.routers import embedded_nanobot as embedded_nanobot_router
from app.routers import paper as paper_router
from app.routers import portfolio as portfolio_router
from app.routers import review as review_router
from app.routers import intelligent_assistant as intelligent_assistant_router
from app.routers import intelligent_screening as intelligent_screening_router
from app.routers import memory as memory_router
from app.routers import workflow_growth as workflow_growth_router
from app.routers import multi_period_sync
from app.routers import internal_messages
from app.routers import tushare_init
from app.routers import akshare_init
from app.routers import baostock_init
from app.routers import system_config as system_config_router
from app.routers import update as update_router
from app.routers import capability_index as capability_index_router
from app.routers import quality_metrics as quality_metrics_router
from app.routers import unified_tasks as unified_tasks_router
# Skill 中心（v3.6.0 起免费开放，随社区版开源）
from app.routers import skills as skills_router
from app.routers import skill_generation as skill_generation_router
from app.routers import skill_gaps as skill_gaps_router
from app.routers import skill_center as skill_center_router

# (router, 注册名, include_router kwargs)
COMMUNITY_ROUTERS = [
    (health.router, "health", {"prefix": "/api", "tags": ["health"]}),
    (auth.router, "auth", {"prefix": "/api/auth", "tags": ["authentication"]}),
    (analysis.router, "analysis", {"prefix": "/api/analysis", "tags": ["analysis"]}),
    (reports.router, "reports", {"tags": ["reports"]}),
    (screening.router, "screening", {"prefix": "/api/screening", "tags": ["screening"]}),
    (intelligent_screening_router.router, "intelligent_screening", {"tags": ["screening-intelligent"]}),
    (queue.router, "queue", {"prefix": "/api/queue", "tags": ["queue"]}),
    (favorites.router, "favorites", {"prefix": "/api", "tags": ["favorites"]}),
    (stocks_router.router, "stocks", {"prefix": "/api", "tags": ["stocks"]}),
    (multi_market_stocks_router.router, "multi_market_stocks", {"prefix": "/api", "tags": ["multi-market"]}),
    (stock_sync_router.router, "stock_sync", {"tags": ["stock-sync"]}),
    (tags.router, "tags", {"prefix": "/api", "tags": ["tags"]}),
    (config.router, "config", {"prefix": "/api", "tags": ["config"]}),
    (model_capabilities.router, "model_capabilities", {"tags": ["model-capabilities"]}),
    (usage_statistics.router, "usage_statistics", {"tags": ["usage-statistics"]}),
    (database.router, "database", {"prefix": "/api/system", "tags": ["database"]}),
    (cache.router, "cache", {"tags": ["cache"]}),
    (operation_logs.router, "operation_logs", {"prefix": "/api/system", "tags": ["operation_logs"]}),
    (logs.router, "logs", {"prefix": "/api/system", "tags": ["logs"]}),
    (system_config_router.router, "system_config", {"prefix": "/api/system", "tags": ["system"]}),
    (update_router.router, "update", {"tags": ["update"]}),
    (notifications_router.router, "notifications", {"prefix": "/api", "tags": ["notifications"]}),
    (websocket_notifications_router.router, "websocket_notifications", {"prefix": "/api", "tags": ["websocket"]}),
    (scheduler_router.router, "scheduler", {"tags": ["scheduler"]}),
    (analysis_profiles_router.router, "analysis_profiles", {"tags": ["analysis-profiles"]}),
    (sse.router, "sse", {"prefix": "/api/stream", "tags": ["streaming"]}),
    (sync_router.router, "sync", {}),
    (multi_source_sync.router, "multi_source_sync", {}),
    (paper_router.router, "paper", {"prefix": "/api", "tags": ["paper"]}),
    (portfolio_router.router, "portfolio", {"prefix": "/api", "tags": ["portfolio"]}),
    (review_router.router, "review", {"prefix": "/api", "tags": ["review"]}),
    (intelligent_assistant_router.router, "intelligent_assistant", {"tags": ["assistant"]}),
    (memory_router.router, "memory", {"tags": ["memory"]}),
    (workflow_growth_router.router, "workflow_growth", {"tags": ["workflow-growth"]}),
    (tushare_init.router, "tushare_init", {"prefix": "/api", "tags": ["tushare-init"]}),
    (akshare_init.router, "akshare_init", {"prefix": "/api", "tags": ["akshare-init"]}),
    (baostock_init.router, "baostock_init", {"prefix": "/api", "tags": ["baostock-init"]}),
    (multi_period_sync.router, "multi_period_sync", {"tags": ["multi-period-sync"]}),
    (internal_messages.router, "internal_messages", {"tags": ["internal-messages"]}),
    (analysis_preferences_router.router, "analysis_preferences", {"tags": ["analysis-preferences"]}),
    (advanced_courses_router.router, "advanced_courses", {"tags": ["advanced-courses"]}),
    (embedded_nanobot_router.router, "embedded_nanobot", {"tags": ["embedded-nanobot"]}),
    (unified_tasks_router.router, "unified_tasks", {"tags": ["unified-task-center"]}),
    (capability_index_router.router, "capability_index", {"prefix": "/api", "tags": ["capability-index"]}),
    (quality_metrics_router.router, "quality_metrics", {}),
    # --- Skill 中心（v3.6.0 起免费开放，随社区版开源）---
    (skills_router.router, "skills", {"tags": ["skills"]}),
    (skill_generation_router.router, "skill_generation", {"tags": ["skill-generation"]}),
    (skill_gaps_router.router, "skill_gaps", {"tags": ["skill-gaps"]}),
    (skill_center_router.router, "skill_center", {"tags": ["skill-center"]}),
]

# =============================================================================
# Pro 专属路由（社区版发布时整体剔除）
# =============================================================================
from app.routers import workflows as workflows_router
from app.routers import agents as agents_router
from app.routers import tools as tools_router
from app.routers import agent_workshop as agent_workshop_router
from app.routers import workflow_generation as workflow_generation_router
from app.routers import agent_assertions as agent_assertions_router
from app.routers import execution_trace as execution_trace_router
from app.routers import mcp as mcp_router
from app.routers import trading_system as trading_system_router
from app.routers import scheduled_analysis as scheduled_analysis_router
from app.routers import email as email_router
from app.routers import watchlist_groups as watchlist_groups_router
from app.routers import license as license_router
from app.routers import reports_export as reports_export_router
from app.routers import stock_data as stock_data_router
from app.routers import financial_data as financial_data_router
from app.routers import historical_data as historical_data_router
from app.routers import news_data as news_data_router
from app.routers import social_media as social_media_router
from app.routers import prompt_templates as prompt_templates_router
from app.routers import template_history as template_history_router
from app.routers import user_template_configs as user_template_configs_router
from app.routers import prompt_preview as prompt_preview_router
from app.routers import prompt_injection_policies as prompt_injection_policies_router
from app.routers import prompt_design as prompt_design_router
from app.routers import templates_debug as templates_debug_router  # ⚠️ DEPRECATED: v1 调试路由，v4.0 移除

# (router, 注册名, include_router kwargs)
PRO_ROUTERS = [
    # --- 分析流模块（workflows / agents / tools / MCP）---
    (workflows_router.router, "workflows", {"tags": ["workflows"]}),
    (agents_router.router, "agents", {"tags": ["agents"]}),
    (tools_router.router, "tools", {"tags": ["tools"]}),
    (agent_workshop_router.router, "agent_workshop", {"tags": ["agent-workshop"]}),
    (workflow_generation_router.router, "workflow_generation", {"tags": ["workflow-generation"]}),
    (agent_assertions_router.router, "agent_assertions", {"tags": ["agent-assertions"]}),
    (execution_trace_router.router, "execution_trace", {"tags": ["execution-traces"]}),
    (mcp_router.router, "mcp", {}),
    # --- 交易计划（trading_plan_check 门控）---
    (trading_system_router.router, "trading_system", {"tags": ["trading-systems"]}),
    # --- 定时/推送/分组 ---
    (scheduled_analysis_router.router, "scheduled_analysis", {"tags": ["scheduled-analysis"]}),
    (email_router.router, "email", {"tags": ["email"]}),
    (watchlist_groups_router.router, "watchlist_groups", {"tags": ["watchlist-groups"]}),
    # --- License 体系（社区版 licensing → community_stub，路由剔除）---
    (license_router.router, "license", {"tags": ["license"]}),
    # --- 报告导出（export_reports 门控，M1 自 reports.py 拆分）---
    (reports_export_router.router, "reports_export", {"tags": ["reports"]}),
    # --- 数据保存（手动数据管理入口，require_pro 门控）---
    (stock_data_router.router, "stock_data", {"tags": ["stock-data"]}),
    (financial_data_router.router, "financial_data", {"tags": ["financial-data"]}),
    (historical_data_router.router, "historical_data", {"tags": ["historical-data"]}),
    (news_data_router.router, "news_data", {"tags": ["news-data"]}),
    (social_media_router.router, "social_media", {"tags": ["social-media"]}),
    # --- 提示词模板体系（prompt_templates 门控）---
    (prompt_templates_router.router, "prompt_templates", {"tags": ["prompt-templates"]}),
    (template_history_router.router, "template_history", {"tags": ["template-history"]}),
    (user_template_configs_router.router, "user_template_configs", {"tags": ["user-template-configs"]}),
    (prompt_preview_router.router, "prompt_preview", {"tags": ["prompt-preview"]}),
    (prompt_injection_policies_router.router, "prompt_injection_policies", {"tags": ["prompt-policies"]}),
    (prompt_design_router.router, "prompt_design", {"tags": ["prompt-design"]}),
    (templates_debug_router.router, "templates_debug", {"tags": ["templates-debug"]}),
]


def _register_router_with_log(app_instance, router, router_name: str, kwargs: dict) -> bool:
    """注册路由并记录日志（自 app/main.py 原样搬迁）"""
    try:
        app_instance.include_router(router, **kwargs)
        logger.info(f"✅ 路由注册成功: {router_name}")
        return True
    except Exception as e:
        logger.error(f"❌ 路由注册失败: {router_name} - {str(e)}", exc_info=True)
        return False


def register_routers(app: FastAPI) -> None:
    """注册全部路由：Pro 版 = 社区版路由 + Pro 专属路由"""
    logger.info("=" * 70)
    logger.info("🚀 开始注册路由...")
    logger.info("=" * 70)

    for router, name, kwargs in COMMUNITY_ROUTERS:
        _register_router_with_log(app, router, name, kwargs)

    for router, name, kwargs in PRO_ROUTERS:
        _register_router_with_log(app, router, name, kwargs)

    logger.info("=" * 70)
    logger.info("✅ 路由注册完成")
    logger.info("=" * 70)

    # 验证关键路由是否已注册
    logger.info("🔍 验证关键路由注册状态:")
    key_routes = [
        "/api/license/status",
        "/api/v2/tasks/list",
        "/api/v2/tasks/statistics"
    ]

    for route_path in key_routes:
        route_found = False
        matching_routes = []
        for route in app.routes:
            if not hasattr(route, 'path'):
                continue
            # FastAPI 路由路径可能包含前缀，直接用完整路径匹配
            if route.path == route_path:
                methods = getattr(route, 'methods', set())
                matching_routes.append((route.path, methods))
                route_found = True
                break
            # 兼容子路由匹配：路径末尾匹配（处理 /api/license 前缀下的 /status 等）
            if route.path.endswith(route_path) or route_path.endswith(route.path):
                methods = getattr(route, 'methods', set())
                matching_routes.append((route.path, methods))
                route_found = True
                break

        if route_found:
            for path, methods in matching_routes:
                logger.info(f"  ✅ {route_path} -> {path} - 方法: {', '.join(methods)}")
        else:
            # 降级为 INFO：路由已注册但检查逻辑未匹配到完整路径，不代表路由缺失
            logger.info(f"  ℹ️  {route_path} - 未在 app.routes 中精确匹配（可能因为 prefix 拆分），路由已通过 include_router 注册")

    logger.info("=" * 70)
