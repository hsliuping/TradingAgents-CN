"""
自动更新 API 路由

端点：
- GET  /api/system/update/check     检查更新
- GET  /api/system/update/progress   获取下载进度
- POST /api/system/update/download   下载更新包
- POST /api/system/update/apply      应用更新
- GET  /api/system/update/info       获取当前版本信息
"""
import os
import sys
import signal
import logging
import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends

from app.services.update_service import get_update_service, UpdateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/update")


def _is_docker_env() -> bool:
    """Detect if running inside Docker container."""
    if os.environ.get("DOCKER", "").lower() in ("1", "true", "yes"):
        return True
    if Path("/.dockerenv").exists():
        return True
    if os.environ.get("DOCKER_CONTAINER") == "true":
        return True
    return False


def _supports_in_app_update(build_type: str) -> bool:
    """Windows portable/installer supports in-app update; Docker does not."""
    if _is_docker_env():
        return False
    return build_type in ("portable", "installer")


@router.get("/info")
async def get_version_info():
    """获取当前版本和构建信息"""
    svc = get_update_service()
    build_info = svc.get_build_info()
    # Prefer version from BUILD_INFO (build-time source of truth), fallback to VERSION file
    current_version = (build_info.get("version") or "").strip() or svc.get_current_version()
    build_type = build_info.get("build_type") or "unknown"
    is_docker = _is_docker_env()
    supports_in_app_update = _supports_in_app_update(build_type)
    return {
        "success": True,
        "data": {
            "current_version": current_version,
            "build_info": build_info,
            "is_docker": is_docker,
            "supports_in_app_update": supports_in_app_update,
        },
        "message": "ok",
    }


@router.get("/check")
async def check_update():
    """检查是否有新版本"""
    svc = get_update_service()
    info = await svc.check_for_updates()
    return {
        "success": True,
        "data": info.to_dict(),
        "message": "发现新版本" if info.has_update else "已是最新版本",
    }


@router.get("/progress")
async def get_download_progress():
    """获取下载进度"""
    svc = get_update_service()
    return {
        "success": True,
        "data": svc.get_download_progress(),
        "message": "ok",
    }


# 缓存最近一次 check 结果，避免 download 时重复请求
_last_update_info = None


@router.post("/download")
async def download_update():
    """下载更新包（仅 Windows 便携版/安装版支持）"""
    global _last_update_info

    svc = get_update_service()
    build_type = svc.get_build_info().get("build_type") or "unknown"
    if not _supports_in_app_update(build_type):
        if _is_docker_env():
            return {
                "success": False,
                "data": None,
                "message": "Docker 部署不支持应用内更新，请使用 docker pull 获取最新镜像",
            }
        return {
            "success": False,
            "data": None,
            "message": "当前构建类型不支持应用内更新",
        }

    # 先检查更新
    info = await svc.check_for_updates()
    if not info.has_update:
        return {
            "success": False,
            "data": None,
            "message": "没有可用的更新",
        }

    _last_update_info = info

    # 后台下载（不阻塞响应）
    asyncio.create_task(_do_download(svc, info))

    return {
        "success": True,
        "data": {
            "version": info.latest_version,
            "file_size": info.file_size,
        },
        "message": f"开始下载 v{info.latest_version} 更新包",
    }


async def _do_download(svc: UpdateService, info):
    """后台执行下载"""
    try:
        result = await svc.download_update(info)
        if result:
            logger.info(f"✅ 更新包下载完成: {result}")
        else:
            logger.error("❌ 更新包下载失败")
    except Exception as e:
        logger.error(f"❌ 下载异常: {e}")


@router.post("/apply")
async def apply_update():
    """应用更新（启动更新器，然后退出后端；仅 Windows 便携版/安装版支持）"""
    global _last_update_info

    svc = get_update_service()
    build_type = svc.get_build_info().get("build_type") or "unknown"
    if not _supports_in_app_update(build_type):
        if _is_docker_env():
            return {
                "success": False,
                "data": None,
                "message": "Docker 部署不支持应用内更新，请使用 docker pull 获取最新镜像",
            }
        return {
            "success": False,
            "data": None,
            "message": "当前构建类型不支持应用内更新",
        }
    progress = svc.get_download_progress()

    if progress.get("status") != "completed":
        return {
            "success": False,
            "data": None,
            "message": "请先下载更新包",
        }

    # 找到已下载的更新包
    if not _last_update_info:
        return {
            "success": False,
            "data": None,
            "message": "更新信息丢失，请重新检查更新",
        }

    version = _last_update_info.latest_version
    update_file = svc.UPDATES_DIR / f"update-{version}.zip"

    if not update_file.exists():
        return {
            "success": False,
            "data": None,
            "message": "更新包文件不存在，请重新下载",
        }

    # 启动更新器
    result = await svc.apply_update(update_file, version)

    if result["success"]:
        # 给前端一个响应后，延迟退出后端进程
        asyncio.get_event_loop().call_later(3, _shutdown)

    return {
        "success": result["success"],
        "data": None,
        "message": result["message"],
    }


def _shutdown():
    """优雅退出后端进程"""
    logger.info("🛑 后端进程即将退出，等待更新器接管...")
    os._exit(0)

