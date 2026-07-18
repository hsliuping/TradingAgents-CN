from fastapi import APIRouter, Depends
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any

router = APIRouter()
logger = logging.getLogger("webapi")


def is_jdyun_mode() -> bool:
    """判断是否为京东云合作版模式"""
    return os.getenv("JDYUN_MODE", "false").lower() == "true"


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


# 缓存层/非真实 API 数据源类型，不视为可用数据源
_CACHE_SOURCE_TYPES = {"local", "mongodb", "local_file"}


@router.get("/system/readiness", response_model=Dict[str, Any])
async def system_readiness():
    """
    系统就绪度检查：返回数据源配置、基础数据同步、LLM 配置的就绪状态，
    供首页引导卡片使用，引导用户完成首次使用前的必要配置。
    """
    readiness = {
        "datasource_configured": False,
        "basics_synced": False,
        "llm_configured": False,
        "basics_count": 0,
        "enabled_real_sources": [],
        "enabled_llm_count": 0,
        "overall_ready": False,
        "next_step": "configure_datasource",
        "next_step_message": "请先配置数据源",
        "next_step_redirect": "/settings/config",
        "next_step_tab": "datasource",
    }

    try:
        # ── 京东云版特化：环境变量已注入配置，直接视为已就绪 ──
        if is_jdyun_mode():
            readiness["datasource_configured"] = True
            readiness["llm_configured"] = True
            readiness["enabled_real_sources"] = ["tushare", "akshare"]
            readiness["enabled_llm_count"] = 1
            # 仍需检查基础数据同步
            from app.core.database import get_mongo_db
            db = get_mongo_db()
            basics_count = await db["stock_basic_info"].count_documents({})
            readiness["basics_count"] = basics_count
            readiness["basics_synced"] = basics_count > 0

            # 京东云版只关心同步状态
            if not readiness["basics_synced"]:
                readiness["next_step"] = "sync_data"
                readiness["next_step_message"] = "请同步股票基础数据"
                readiness["next_step_redirect"] = "/settings/sync"
                readiness["next_step_tab"] = ""
            else:
                readiness["overall_ready"] = True
                readiness["next_step"] = "ready"
                readiness["next_step_message"] = "系统已就绪，可以开始分析"
                readiness["next_step_redirect"] = "/analysis/single"
                readiness["next_step_tab"] = ""

            # 京东云版附加标记，前端可识别
            readiness["jdyun_mode"] = True
            return readiness

        # ── 1. 检查数据源配置 ──
        from app.services.config_service import config_service
        config = await config_service.get_system_config()

        enabled_real_sources = []
        if config and config.data_source_configs:
            for ds in config.data_source_configs:
                if ds.enabled and ds.type not in _CACHE_SOURCE_TYPES:
                    enabled_real_sources.append(ds.type)

        readiness["enabled_real_sources"] = enabled_real_sources
        readiness["datasource_configured"] = len(enabled_real_sources) > 0

        # ── 2. 检查 LLM 配置 ──
        enabled_llms = []
        if config and config.llm_configs:
            enabled_llms = [llm for llm in config.llm_configs if llm.enabled]
        readiness["enabled_llm_count"] = len(enabled_llms)
        readiness["llm_configured"] = len(enabled_llms) > 0

        # ── 3. 检查基础数据同步 ──
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        basics_count = await db["stock_basic_info"].count_documents({})
        readiness["basics_count"] = basics_count
        readiness["basics_synced"] = basics_count > 0

        # ── 4. 计算总体就绪度和下一步建议 ──
        if not readiness["datasource_configured"]:
            readiness["next_step"] = "configure_datasource"
            readiness["next_step_message"] = "第1步：请先配置数据源"
            readiness["next_step_redirect"] = "/settings/config"
            readiness["next_step_tab"] = "datasource"
        elif not readiness["llm_configured"]:
            readiness["next_step"] = "configure_llm"
            readiness["next_step_message"] = "第2步：请配置大语言模型（LLM）"
            readiness["next_step_redirect"] = "/settings/config"
            readiness["next_step_tab"] = "llm"
        elif not readiness["basics_synced"]:
            readiness["next_step"] = "sync_data"
            readiness["next_step_message"] = "第3步：请同步股票基础数据"
            readiness["next_step_redirect"] = "/settings/sync"
            readiness["next_step_tab"] = ""
        else:
            readiness["overall_ready"] = True
            readiness["next_step"] = "ready"
            readiness["next_step_message"] = "系统已就绪，可以开始分析"
            readiness["next_step_redirect"] = "/analysis/single"
            readiness["next_step_tab"] = ""

        return readiness
    except Exception as e:
        logger.error(f"❌ 系统就绪度检查失败: {e}", exc_info=True)
        # 出错时返回未就绪状态，避免误导用户
        readiness["next_step"] = "error"
        readiness["next_step_message"] = f"就绪度检查失败: {e}"
        return readiness
