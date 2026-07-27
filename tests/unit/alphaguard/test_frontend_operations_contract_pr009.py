from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend/src"


def test_unified_alphaguard_route_and_all_mvp_pages_exist():
    router = (FRONTEND / "router/index.ts").read_text(encoding="utf-8")
    sidebar = (
        FRONTEND / "components/Layout/SidebarMenu.vue"
    ).read_text(encoding="utf-8")
    expected = {
        "overview": "Overview.vue",
        "candidates": "Candidates.vue",
        "decisions": "Decisions.vue",
        "paper": "Paper.vue",
        "evaluations": "Evaluations.vue",
        "experiments": "Experiments.vue",
        "operations": "Operations.vue",
    }
    assert "path: '/alphaguard'" in router
    assert 'index="/alphaguard/overview"' in sidebar
    for route, filename in expected.items():
        assert f"path: '{route}'" in router
        assert (FRONTEND / "views/AlphaGuard" / filename).is_file()


def test_frontend_keeps_manual_and_automatic_paper_trading_distinct():
    router = (FRONTEND / "router/index.ts").read_text(encoding="utf-8")
    sidebar = (
        FRONTEND / "components/Layout/SidebarMenu.vue"
    ).read_text(encoding="utf-8")
    shell = (
        FRONTEND / "views/AlphaGuard/AlphaGuardLayout.vue"
    ).read_text(encoding="utf-8")
    assert "path: '/paper'" in router
    assert "path: '/alphaguard'" in router
    assert 'index="/paper"' in sidebar
    assert 'index="/alphaguard/overview"' in sidebar
    assert "实盘永久关闭" in shell
    assert "Risk PASS 不等于订单" in shell


def test_frontend_exposes_no_live_or_direct_automatic_order_creation():
    files = list((FRONTEND / "views/AlphaGuard").glob("*.vue")) + [
        FRONTEND / "api/alphaguard.ts",
        FRONTEND / "api/alphaguardOperations.ts",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for forbidden in (
        "live-trading/enable",
        "/broker/",
        "/paper/order-intents",
        "PaperFill创建",
        "force=true",
    ):
        assert forbidden not in source
    assert "live_execution_allowed: false" in source


def test_shared_api_client_never_logs_bearer_token_contents():
    source = (FRONTEND / "api/request.ts").read_text(encoding="utf-8")
    auth_source = (FRONTEND / "stores/auth.ts").read_text(encoding="utf-8")
    assert "tokenPrefix" not in source
    assert "authHeader:" not in source
    assert "sanitizeForLog(config.data)" in source
    assert "sanitizeForLog(config.headers)" in source
    assert "sanitizeForLog(response.data)" in source
    assert "error: error" not in source
    assert "response: error.response" not in source
    assert "prefix: this.refreshToken.substring" not in auth_source
    assert "刷新响应:', response" not in auth_source
    assert "this.roles = ['admin']" not in auth_source
    assert "user.is_admin ? ['admin'] : ['user']" in auth_source


def test_backend_auth_and_model_logs_do_not_emit_secret_prefixes():
    paths = (
        ROOT / "app/routers/auth_db.py",
        ROOT / "app/routers/config.py",
        ROOT / "app/services/auth_service.py",
        ROOT / "app/services/config_service.py",
        ROOT / "app/services/user_service.py",
        ROOT / "tradingagents/config/config_manager.py",
        ROOT / "tradingagents/llm_adapters/google_openai_adapter.py",
        ROOT / "tradingagents/llm_adapters/openai_compatible_base.py",
        ROOT / "tradingagents/llm_adapters/dashscope_openai_adapter.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "Token前20位",
        "JWT密钥: {settings.JWT_SECRET[:",
        "前10位: {env_api_key[:",
        "输入密码哈希:",
        "存储密码哈希:",
        "密码: {password}",
        "Auth=Bearer...",
        '"received": api_key',
        '"expected": truncated_db_key',
    ):
        assert forbidden not in source


def test_decision_page_keeps_structured_objects_visibly_separate():
    source = (
        FRONTEND / "views/AlphaGuard/Decisions.vue"
    ).read_text(encoding="utf-8")
    for label in (
        "NormalTradePlan",
        "TopReviewDecision",
        "ConsensusDecision",
        "RiskDecision",
        "模型失败不会显示为 HOLD",
    ):
        assert label in source


def test_compose_declares_api_both_workers_mongo_redis_and_safe_defaults():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert {
        "backend",
        "frontend",
        "mongodb",
        "redis",
        "queue-worker",
        "analysis-worker",
    } <= set(services)
    for name in ("backend", "queue-worker", "analysis-worker"):
        environment = services[name]["environment"]
        assert "SIM_AUTONOMOUS" in environment["ALPHAGUARD_SYSTEM_MODE"]
        assert "false" in environment["ALPHAGUARD_LIVE_TRADING_ENABLED"]
    assert "/health/ready" in " ".join(services["backend"]["healthcheck"]["test"])


def test_backup_restore_and_initialization_scripts_are_dry_run_by_default():
    for filename in (
        "alphaguard_backup.py",
        "alphaguard_restore.py",
        "alphaguard_initialize.py",
        "init_alphaguard_operations_indexes.py",
    ):
        source = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
        assert "--execute" in source
    backup = (ROOT / "scripts/alphaguard_backup.py").read_text(encoding="utf-8")
    restore = (ROOT / "scripts/alphaguard_restore.py").read_text(encoding="utf-8")
    assert "ALPHAGUARD_INDEX_SPECS" in backup
    assert "paper_accounts" not in backup
    assert "--overwrite-current" in restore
    assert "OVERWRITE" in restore


def test_readiness_report_exposes_all_mvp_dimensions():
    source = (
        ROOT / "scripts/alphaguard_readiness_report.py"
    ).read_text(encoding="utf-8")
    for name in (
        "CODE_COMPLETE",
        "RUNTIME_READY",
        "DATA_READY",
        "PAPER_READY",
        "EVALUATION_READY",
        "EXPERIMENT_READY",
        "CHALLENGER_READY",
        "LIVE_READY",
    ):
        assert f'"{name}"' in source
