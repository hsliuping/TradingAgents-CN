from fastapi import APIRouter
from fastapi.responses import JSONResponse
import time
from pathlib import Path

router = APIRouter()


def get_version() -> str:
    """从 VERSION 文件读取版本号"""
    try:
        version_file = Path(__file__).parent.parent.parent / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    return "0.1.16"  # 默认版本号


@router.get("/health")
async def health():
    """健康检查接口 - 前端使用"""
    return {
        "success": True,
        "data": {
            "status": "ok",
            "version": get_version(),
            "timestamp": int(time.time()),
            "service": "TradingAgents-CN API"
        },
        "message": "服务运行正常"
    }

@router.get("/healthz")
async def healthz():
    """Kubernetes健康检查"""
    return {"status": "ok"}

@router.get("/readyz")
async def readyz():
    """Kubernetes就绪检查"""
    return {"ready": True}


@router.get("/health/live")
async def layered_liveness():
    """Pure process liveness; deliberately performs no dependency I/O."""
    return {
        "status": "ALIVE",
        "service": "TradingAgents-CN API",
        "version": get_version(),
        "timestamp": int(time.time()),
    }


@router.get("/health/ready")
async def layered_readiness():
    """Dependency and AlphaGuard safety readiness with honest degradation."""
    from app.core.database import get_mongo_db, get_redis_client
    from app.services.alphaguard.operations_service import AlphaGuardOperationsService
    from app.services.scheduler_service import _scheduler_instance

    report = await AlphaGuardOperationsService(
        get_mongo_db(),
        redis_client=get_redis_client(),
        scheduler=_scheduler_instance,
    ).readiness(persist_alerts=False)
    core_unhealthy = any(
        item.required
        and item.status in {"UNHEALTHY", "UNKNOWN", "NOT_CONFIGURED"}
        for item in report.service_health
    )
    # Missing market/reference data is an honest DEGRADED state, not a reason
    # to make the management UI unreachable. Unsafe configuration or a failed
    # required dependency remains fail-closed at the readiness probe.
    status_code = 503 if report.overall_status == "UNSAFE" or core_unhealthy else 200
    return JSONResponse(
        status_code=status_code,
        content={
            "status": (
                "READY"
                if report.overall_status == "READY_FOR_PAPER"
                else (
                    "UNSAFE"
                    if report.overall_status == "UNSAFE"
                    else "DEGRADED"
                )
            ),
            "overall_status": report.overall_status,
            "report_id": report.report_id,
            "blocking_items": report.blocking_items,
            "live_ready": False,
            "generated_at": report.generated_at.isoformat(),
        },
    )
