"""
Pro 专属路由清单（v3.6.0 社区版开源分离）

本文件集中承载全部 Pro 路由的 import 与注册列表，供 router_registry.py
动态加载。社区版发布管道（scripts/publish_community.py）将本文件整体删除，
router_registry.py 的 try-import 自动降级为空列表，无需任何行级修改。

新增 Pro 路由时只改本文件；新增社区路由改 router_registry.py 的 COMMUNITY_ROUTERS。
"""

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
from app.routers import historical_data as historical_data_router
from app.routers import social_media as social_media_router
from app.routers import prompt_templates as prompt_templates_router
from app.routers import template_history as template_history_router
from app.routers import user_template_configs as user_template_configs_router
from app.routers import prompt_preview as prompt_preview_router
from app.routers import prompt_injection_policies as prompt_injection_policies_router
from app.routers import prompt_design as prompt_design_router
from app.routers import templates_debug as templates_debug_router  # ⚠️ DEPRECATED: v1 调试路由，v4.0 移除

# (router, 注册名, include_router kwargs)
# 注意：与 COMMUNITY_ROUTERS 的 (router, name, kwargs) 结构一致
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
    # --- 数据保存（手动数据管理入口，require_pro 门控；news_data r7、stock_data/financial_data
    #     r8 为免费功能已移入社区版——读取端点本无门控且社区股票详情页实际调用）---
    (historical_data_router.router, "historical_data", {"tags": ["historical-data"]}),
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
