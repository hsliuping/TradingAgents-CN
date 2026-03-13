"""
自动更新服务

功能：
1. 检查官网是否有新版本
2. 下载更新包（带进度跟踪）
3. 校验更新包（SHA256）
4. 触发更新器脚本（独立进程）
"""
import os
import json
import hashlib
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 默认更新服务器地址（当配置为空时使用）
DEFAULT_UPDATE_BASE_URL = "https://www.tradingagentscn.com/api"


class UpdateInfo:
    """更新信息"""

    def __init__(self, data: dict):
        self.has_update: bool = data.get("has_update", False)
        self.latest_version: str = data.get("version", "")
        self.package_type: str = self._normalize_package_type(data.get("package_type"))
        self.download_url: str = data.get("download_url", "")
        self.file_size: int = data.get("file_size", 0)
        self.sha256: str = data.get("sha256", "")
        self.release_notes: str = data.get("release_notes", "")
        self.release_date: str = data.get("release_date", "")
        self.is_mandatory: bool = data.get("is_mandatory", False)
        self.min_version: str = data.get("min_version", "")
        self.check_failed: bool = data.get("check_failed", False)
        self.error_message: str = data.get("error_message", "")

    def to_dict(self) -> dict:
        return {
            "has_update": self.has_update,
            "latest_version": self.latest_version,
            "package_type": self.package_type,
            "download_url": self.download_url,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "release_notes": self.release_notes,
            "release_date": self.release_date,
            "is_mandatory": self.is_mandatory,
            "min_version": self.min_version,
            "check_failed": self.check_failed,
            "error_message": self.error_message,
        }

    @staticmethod
    def _normalize_package_type(package_type: Optional[str]) -> str:
        raw = (package_type or "installer").strip().lower()
        return raw if raw in {"installer", "update"} else "installer"


class UpdateService:
    """自动更新服务"""

    # 更新包下载目录
    UPDATES_DIR = PROJECT_ROOT / "runtime" / "updates"

    # 备份目录
    BACKUP_DIR = PROJECT_ROOT / "backup"

    def __init__(self):
        # 从配置读取更新检查地址，支持 .env 中 UPDATE_CHECK_BASE_URL 覆盖（用于测试验证）
        url = (settings.UPDATE_CHECK_BASE_URL or "").strip()
        self.base_url = url if url else DEFAULT_UPDATE_BASE_URL
        self.channel = self._normalize_update_channel(settings.UPDATE_CHECK_CHANNEL)
        self._download_progress: Dict[str, Any] = {}
        # 确保目录存在
        self.UPDATES_DIR.mkdir(parents=True, exist_ok=True)

    # ── 版本信息 ──────────────────────────────────────────

    def get_current_version(self) -> str:
        """读取当前版本号"""
        version_file = PROJECT_ROOT / "VERSION"
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except Exception:
            return "0.0.0"

    def get_build_info(self) -> dict:
        """读取构建信息"""
        build_file = PROJECT_ROOT / "BUILD_INFO"
        try:
            raw = build_file.read_text(encoding="utf-8-sig").strip()
            return json.loads(raw)
        except Exception:
            return {}

    def get_update_channel(self) -> str:
        """获取当前更新通道"""
        return self.channel

    # ── 检查更新 ──────────────────────────────────────────

    async def check_for_updates(self) -> UpdateInfo:
        """向官网查询是否有新版本"""
        current_version = self.get_current_version()
        build_info = self.get_build_info()

        logger.info(
            f"🔍 检查更新... 当前版本: {current_version}, 通道: {self.channel}"
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/app/check-update",
                    params={
                        "version": current_version,
                        "build_type": build_info.get("build_type", "unknown"),
                        "channel": self.channel,
                    },
                    headers={"User-Agent": f"TradingAgentsCN/{current_version}"},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        info = UpdateInfo(data.get("data", {}))
                        if info.has_update:
                            logger.info(
                                f"📦 发现新版本: {info.latest_version}"
                            )
                        else:
                            logger.info("✅ 已是最新版本")
                        return info

                logger.warning(f"⚠️ 检查更新失败: HTTP {resp.status_code}")
                return UpdateInfo({
                    "has_update": False,
                    "check_failed": True,
                    "error_message": f"更新服务器返回错误 (HTTP {resp.status_code})",
                })

        except httpx.ConnectError:
            logger.warning("⚠️ 无法连接更新服务器")
            return UpdateInfo({
                "has_update": False,
                "check_failed": True,
                "error_message": "无法连接更新服务器，请检查网络或稍后重试",
            })
        except httpx.TimeoutException:
            logger.warning("⚠️ 连接更新服务器超时")
            return UpdateInfo({
                "has_update": False,
                "check_failed": True,
                "error_message": "连接更新服务器超时，请稍后重试",
            })
        except Exception as e:
            logger.error(f"❌ 检查更新异常: {e}")
            return UpdateInfo({
                "has_update": False,
                "check_failed": True,
                "error_message": f"检查更新失败: {str(e)}",
            })

    # ── 下载更新包 ────────────────────────────────────────

    async def download_update(self, update_info: UpdateInfo) -> Optional[Path]:
        """下载更新包，返回本地文件路径"""
        if not update_info.download_url:
            logger.error("❌ 下载地址为空")
            return None

        version = update_info.latest_version
        filename = self._build_download_filename(update_info)
        target_path = self.UPDATES_DIR / filename

        # 如果已下载且校验通过，直接返回
        if target_path.exists() and update_info.sha256:
            if self._verify_sha256(target_path, update_info.sha256):
                logger.info(f"✅ 更新包已存在且校验通过: {filename}")
                return target_path

        logger.info(f"⬇️ 开始下载更新包: {update_info.download_url}")
        self._download_progress = {
            "status": "downloading",
            "version": version,
            "total": update_info.file_size,
            "downloaded": 0,
            "percent": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
                async with client.stream("GET", update_info.download_url) as resp:
                    if resp.status_code != 200:
                        logger.error(f"❌ 下载失败: HTTP {resp.status_code}")
                        self._download_progress["status"] = "failed"
                        return None

                    total = int(resp.headers.get("content-length", 0)) or update_info.file_size
                    self._download_progress["total"] = total
                    downloaded = 0

                    with open(target_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            self._download_progress["downloaded"] = downloaded
                            if total > 0:
                                self._download_progress["percent"] = round(
                                    downloaded * 100 / total, 1
                                )

            # 校验
            if update_info.sha256:
                if not self._verify_sha256(target_path, update_info.sha256):
                    logger.error("❌ 更新包校验失败，SHA256 不匹配")
                    target_path.unlink(missing_ok=True)
                    self._download_progress["status"] = "verify_failed"
                    return None

            self._download_progress["status"] = "completed"
            self._download_progress["percent"] = 100
            logger.info(f"✅ 更新包下载完成: {filename} ({downloaded} bytes)")
            return target_path

        except Exception as e:
            logger.error(f"❌ 下载更新包异常: {e}")
            self._download_progress["status"] = "failed"
            target_path.unlink(missing_ok=True)
            return None

    def get_download_progress(self) -> dict:
        """获取下载进度"""
        return dict(self._download_progress) if self._download_progress else {
            "status": "idle",
            "percent": 0,
        }

    def get_download_message(self, update_info: UpdateInfo) -> str:
        """根据包类型生成下载提示。"""
        if update_info.package_type == "installer":
            return f"发现 v{update_info.latest_version} 安装包，请下载安装后手动升级"
        return f"开始下载 v{update_info.latest_version} 更新包"

    # ── 应用更新 ──────────────────────────────────────────

    async def apply_update(self, update_file: Path, version: str) -> dict:
        """
        启动独立更新器进程，然后通知调用方需要退出应用。

        更新流程由 scripts/updater/apply_update.ps1 负责：
        1. 等待后端进程退出
        2. 备份当前版本
        3. 解压更新包
        4. 重启所有服务
        """
        if not update_file.exists():
            return {"success": False, "message": "更新包文件不存在"}

        updater_script = PROJECT_ROOT / "scripts" / "updater" / "apply_update.ps1"
        if not updater_script.exists():
            return {"success": False, "message": "更新器脚本不存在"}

        current_version = self.get_current_version()
        logger.info(f"🚀 启动更新: {current_version} → {version}")

        try:
            # 启动独立的 PowerShell 更新器进程
            cmd = [
                "powershell.exe",
                "-ExecutionPolicy", "Bypass",
                "-File", str(updater_script),
                "-UpdateFile", str(update_file),
                "-TargetVersion", version,
                "-CurrentVersion", current_version,
                "-ProjectRoot", str(PROJECT_ROOT),
            ]

            # CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS 让更新器独立于后端进程
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008

            subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            logger.info("✅ 更新器进程已启动，后端即将退出...")
            return {
                "success": True,
                "message": f"更新器已启动，正在从 {current_version} 更新到 {version}",
            }

        except Exception as e:
            logger.error(f"❌ 启动更新器失败: {e}")
            return {"success": False, "message": f"启动更新器失败: {e}"}

    # ── 清理 ──────────────────────────────────────────────

    def cleanup_old_packages(self, keep_latest: int = 2):
        """清理旧的更新包，保留最新的 N 个"""
        if not self.UPDATES_DIR.exists():
            return

        files = sorted(
            self.UPDATES_DIR.glob("update-*.zip"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        for f in files[keep_latest:]:
            try:
                f.unlink()
                logger.info(f"🗑️ 清理旧更新包: {f.name}")
            except Exception as e:
                logger.warning(f"⚠️ 清理失败: {f.name} - {e}")

    # ── 内部方法 ──────────────────────────────────────────

    @staticmethod
    def _build_download_filename(update_info: UpdateInfo) -> str:
        """根据下载地址和包类型推断本地文件名。"""
        parsed = httpx.URL(update_info.download_url)
        basename = Path(parsed.path).name.strip()
        if basename:
            return basename
        extension = ".exe" if update_info.package_type == "installer" else ".zip"
        prefix = "installer" if update_info.package_type == "installer" else "update"
        return f"{prefix}-{update_info.latest_version}{extension}"

    @staticmethod
    def _normalize_update_channel(channel: Optional[str]) -> str:
        """归一化更新通道，避免配置别名造成服务端分流不一致。"""
        raw = (channel or "").strip().lower()
        alias_map = {
            "": "stable",
            "stable": "stable",
            "formal": "stable",
            "prod": "stable",
            "production": "stable",
            "release": "stable",
            "official": "stable",
            "正式": "stable",
            "线上": "stable",
            "test": "test",
            "testing": "test",
            "beta": "test",
            "staging": "test",
            "preview": "test",
            "测试": "test",
            "预发": "test",
        }
        normalized = alias_map.get(raw)
        if normalized:
            return normalized

        logger.warning("⚠️ 未识别的更新通道配置 '%s'，已回退为 stable", channel)
        return "stable"

    @staticmethod
    def _verify_sha256(file_path: Path, expected_hash: str) -> bool:
        """校验文件 SHA256"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                sha256.update(data)
        actual = sha256.hexdigest()
        match = actual.lower() == expected_hash.lower()
        if not match:
            logger.warning(
                f"SHA256 不匹配: expected={expected_hash[:16]}... actual={actual[:16]}..."
            )
        return match


# 单例
_update_service: Optional[UpdateService] = None


def get_update_service() -> UpdateService:
    """获取更新服务单例"""
    global _update_service
    if _update_service is None:
        _update_service = UpdateService()
    return _update_service
