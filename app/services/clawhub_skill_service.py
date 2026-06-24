"""
ClawHub Skill 下载与管理服务

负责从 ClawHub (clawhub.ai) 下载完整 Skill 包（含 scripts/）到本地目录，
并解析 SKILL.md 注册到 MongoDB。

ClawHub API 文档: https://docs.openclaw.ai/clawhub/api
- GET /api/v1/skills/{slug}          获取 Skill 元数据
- GET /api/v1/search?q=...           搜索 Skill
- GET /api/v1/download?slug=&version=&tag=  下载 Skill ZIP 包
- GET /api/v1/skills?limit=&cursor=&sort=   列出 Skill

slug 格式：Skill 的唯一标识，如 "ifind-repilot-finance-data-search"
"""

import io
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("webapi")

# ClawHub API 基础 URL
CLAWHUB_BASE_URL = "https://clawhub.ai"

# 本地 Skill 包存储根目录（项目根目录下的 skills/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"


class ClawHubSkillService:
    """ClawHub Skill 下载与管理服务"""

    # 下载超时（秒），Skill 包可能较大
    DOWNLOAD_TIMEOUT = 60.0
    # API 请求超时
    API_TIMEOUT = 15.0
    # HTTP 客户端默认 headers
    DEFAULT_HEADERS = {
        "User-Agent": "TradingAgentsCN/3.0 (Skill Installer)",
        "Accept": "application/json",
    }

    # =============================================================
    # 公开方法
    # =============================================================

    @classmethod
    async def search_skills(cls, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索 ClawHub 上的 Skill

        Args:
            query: 搜索关键词
            limit: 返回数量上限（1-200）

        Returns:
            Skill 列表，每项包含 slug/displayName/summary/version/ownerHandle 等
        """
        if not query.strip():
            return []
        limit = max(1, min(200, limit))
        url = f"{CLAWHUB_BASE_URL}/api/v1/search"
        params = {"q": query, "limit": limit, "nonSuspiciousOnly": "true"}

        try:
            async with httpx.AsyncClient(timeout=cls.API_TIMEOUT, headers=cls.DEFAULT_HEADERS) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"ClawHub 搜索失败: HTTP {resp.status_code}, {resp.text[:200]}")
                    return []
                data = resp.json()
                results = data.get("results", []) if isinstance(data, dict) else []
                # 标准化字段
                normalized = []
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    owner = item.get("owner") or {}
                    normalized.append({
                        "slug": item.get("slug", ""),
            "display_name": item.get("displayName") or item.get("slug", ""),
            "summary": item.get("summary") or "",
            "version": item.get("version") or "",
            "updated_at": item.get("updatedAt"),
                        "owner_handle": owner.get("handle", "") if isinstance(owner, dict) else "",
                        "owner_display_name": owner.get("displayName", "") if isinstance(owner, dict) else "",
                        "canonical_url": f"{CLAWHUB_BASE_URL}/{owner.get('handle', '')}/{item.get('slug', '')}"
                                         if isinstance(owner, dict) and owner.get("handle") else "",
                        "score": item.get("score", 0),
                    })
                return normalized
        except httpx.TimeoutException:
            logger.warning("ClawHub 搜索超时")
            return []
        except Exception as e:
            logger.warning(f"ClawHub 搜索异常: {e}")
            return []

    @classmethod
    async def get_skill_info(cls, slug: str) -> Optional[Dict[str, Any]]:
        """获取 ClawHub Skill 元数据

        Args:
            slug: Skill 标识，如 "ifind-repilot-finance-data-search"

        Returns:
            Skill 元数据字典，失败返回 None
        """
        url = f"{CLAWHUB_BASE_URL}/api/v1/skills/{slug}"
        try:
            async with httpx.AsyncClient(timeout=cls.API_TIMEOUT, headers=cls.DEFAULT_HEADERS) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    logger.info(f"ClawHub Skill 不存在: {slug}")
                    return None
                if resp.status_code != 200:
                    logger.warning(f"ClawHub 获取 Skill 元数据失败: HTTP {resp.status_code}")
                    return None
                return resp.json()
        except Exception as e:
            logger.warning(f"ClawHub 获取 Skill 元数据异常: {e}")
            return None

    @classmethod
    async def install_skill(
        cls,
        slug: str,
        version: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从 ClawHub 安装 Skill 到本地目录

        流程：
        1. 调用 /api/v1/download 下载 ZIP 包
        2. 解压到 skills/<slug>/ 目录
        3. 校验 SKILL.md 存在
        4. 校验是否为脚本型 Skill（含 scripts/ 目录）
        5. 写入 .clawhub/origin.json 记录来源信息

        Args:
            slug: Skill 标识
            version: 指定版本（可选，默认最新）
            tag: 版本标签（可选，如 "latest"）

        Returns:
            {
                "success": bool,
                "skill_name": str,
                "skill_dir": str,
                "version": str,
                "has_scripts": bool,
                "message": str
            }
        """
        slug = slug.strip().lstrip("@")
        # 支持 owner/slug 格式，取最后一段作为 slug
        if "/" in slug:
            slug = slug.split("/")[-1]

        if not slug:
            return {"success": False, "message": "slug 不能为空"}

        # 1. 下载 ZIP 包
        zip_bytes, resolved_version = await cls._download_zip(slug, version=version, tag=tag)
        if zip_bytes is None:
            return {
                "success": False,
                "message": f"下载 Skill '{slug}' 失败，请检查 slug 是否正确或网络连接",
            }

        # 2. 解压到 skills/<slug>/ 目录
        skill_dir = SKILLS_DIR / slug
        # 如果已存在，先清空（重新安装）
        if skill_dir.exists():
            import shutil
            shutil.rmtree(skill_dir, ignore_errors=True)
        skill_dir.mkdir(parents=True, exist_ok=True)

        try:
            extracted_files = cls._extract_zip(zip_bytes, skill_dir)
        except Exception as e:
            logger.error(f"解压 Skill ZIP 失败: {e}", exc_info=True)
            return {"success": False, "message": f"解压失败: {e}"}

        # 3. 校验 SKILL.md 存在
        # ZIP 可能包含一层根目录，需要定位实际的 Skill 根目录
        skill_root = cls._locate_skill_root(skill_dir)
        if skill_root is None:
            return {
                "success": False,
                "message": f"Skill 包中未找到 SKILL.md 文件",
                "skill_dir": str(skill_dir),
            }

        # 如果 Skill 根目录不是 skill_dir 本身，重命名
        if skill_root != skill_dir:
            # 将 skill_root 内容移到 skill_dir
            import shutil
            temp_name = skill_dir.parent / f"{slug}.tmp_{Path(__file__).stem}"
            if temp_name.exists():
                shutil.rmtree(temp_name, ignore_errors=True)
            shutil.move(str(skill_root), str(temp_name))
            shutil.rmtree(str(skill_dir), ignore_errors=True)
            shutil.move(str(temp_name), str(skill_dir))

        # 4. 校验是否为脚本型 Skill（含 scripts/ 目录或根目录 .py 文件）
        scripts_dir = skill_dir / "scripts"
        has_scripts = False
        if scripts_dir.is_dir() and any(scripts_dir.iterdir()):
            has_scripts = True
        else:
            # 兼容 SkillHub 包结构：根目录直接放 .py 文件（如 stock-monitor/monitor.py）
            root_py_files = [f for f in skill_dir.iterdir()
                             if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"]
            if root_py_files:
                has_scripts = True
                logger.info(f"📦 Skill '{slug}' 检测到根目录 Python 脚本: {[f.name for f in root_py_files]}")

        if not has_scripts:
            # 知识型 Skill，根据用户决策拒绝导入
            logger.info(f"📚 Skill '{slug}' 是知识型（无 scripts/ 目录），拒绝导入")
            # 清理已下载的目录
            import shutil
            shutil.rmtree(skill_dir, ignore_errors=True)
            return {
                "success": False,
                "message": (
                    f"Skill '{slug}' 是知识型 Skill（无 scripts/ 目录），本项目不支持导入。"
                    "本项目只支持包含可执行脚本的 Python 脚本型 Skill。"
                ),
                "skill_type": "knowledge",
            }

        # 5. 写入 .clawhub/origin.json 记录来源信息
        origin_dir = skill_dir / ".clawhub"
        origin_dir.mkdir(exist_ok=True)
        import json
        origin_info = {
            "source": "clawhub",
            "slug": slug,
            "version": resolved_version or "",
            "installed_at": cls._now_iso(),
            "canonical_url": f"{CLAWHUB_BASE_URL}/skills/{slug}",
        }
        (origin_dir / "origin.json").write_text(
            json.dumps(origin_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info(f"✅ ClawHub Skill '{slug}' 安装成功，目录: {skill_dir}")

        # 计算脚本数量（兼容两种包结构）
        if scripts_dir.is_dir():
            script_count = len([f for f in scripts_dir.iterdir() if f.suffix == ".py"])
        else:
            script_count = len([f for f in skill_dir.iterdir()
                                if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"])

        return {
            "success": True,
            "skill_name": slug,
            "skill_dir": str(skill_dir),
            "version": resolved_version or "",
            "has_scripts": True,
            "scripts_count": script_count,
            "extracted_files_count": len(extracted_files),
            "message": f"Skill '{slug}' 安装成功",
        }

    @classmethod
    def list_local_skills(cls) -> List[Dict[str, Any]]:
        """列出本地已安装的 ClawHub Skill 包

        Returns:
            本地 Skill 列表，每项包含 name/dir/has_scripts/origin 等
        """
        if not SKILLS_DIR.exists():
            return []

        skills = []
        for item in SKILLS_DIR.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith(".") or item.name == ".gitkeep":
                continue
            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue

            scripts_dir = item / "scripts"
            has_scripts = scripts_dir.is_dir() and any(scripts_dir.iterdir()) if scripts_dir.exists() else False

            # 读取 origin.json
            origin = {}
            origin_path = item / ".clawhub" / "origin.json"
            if origin_path.exists():
                try:
                    import json
                    origin = json.loads(origin_path.read_text(encoding="utf-8"))
                except Exception:
                    origin = {}

            skills.append({
                "name": item.name,
                "skill_dir": str(item),
                "has_scripts": has_scripts,
                "has_skill_md": True,
                "source": origin.get("source", "local"),
                "version": origin.get("version", ""),
                "installed_at": origin.get("installed_at", ""),
                "canonical_url": origin.get("canonical_url", ""),
            })
        return skills

    @classmethod
    def uninstall_local_skill(cls, slug: str) -> Dict[str, Any]:
        """卸载本地 Skill 包（删除目录）

        Args:
            slug: Skill 标识

        Returns:
            {success, message}
        """
        slug = slug.strip().lstrip("@")
        if "/" in slug:
            slug = slug.split("/")[-1]

        skill_dir = SKILLS_DIR / slug
        if not skill_dir.exists():
            return {"success": False, "message": f"本地 Skill '{slug}' 不存在"}

        try:
            import shutil
            shutil.rmtree(skill_dir)
            logger.info(f"✅ 已卸载本地 Skill: {slug}")
            return {"success": True, "message": f"Skill '{slug}' 已卸载"}
        except Exception as e:
            return {"success": False, "message": f"卸载失败: {e}"}

    # =============================================================
    # 内部方法
    # =============================================================

    @classmethod
    async def _download_zip(
        cls,
        slug: str,
        version: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> tuple[Optional[bytes], Optional[str]]:
        """从 ClawHub 下载 Skill ZIP 包

        API: GET /api/v1/download?slug=&version=&tag=
        匿名访问，速率限制 1200/min per IP

        Returns:
            (zip_bytes, resolved_version)，失败返回 (None, None)
        """
        url = f"{CLAWHUB_BASE_URL}/api/v1/download"
        params = {"slug": slug}
        if version:
            params["version"] = version
        if tag:
            params["tag"] = tag

        try:
            async with httpx.AsyncClient(
                timeout=cls.DOWNLOAD_TIMEOUT,
                headers={**cls.DEFAULT_HEADERS, "Accept": "application/zip"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 404:
                    logger.warning(f"ClawHub Skill '{slug}' 不存在或不可下载")
                    return None, None
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "?")
                    logger.warning(f"ClawHub 下载被限流，请等待 {retry_after} 秒后重试")
                    return None, None
                if resp.status_code != 200:
                    logger.warning(f"ClawHub 下载失败: HTTP {resp.status_code}, {resp.text[:200]}")
                    return None, None

                # 从响应中解析版本（如果有）
                resolved_version = (
                    resp.headers.get("X-Skill-Version")
                    or resp.headers.get("x-skill-version")
                    or version
                    or ""
                )

                content_type = resp.headers.get("content-type", "")
                if "zip" not in content_type and not resp.content[:4] == b"PK\x03\x04":
                    logger.warning(f"ClawHub 返回的不是 ZIP 文件: content-type={content_type}")
                    return None, None

                return resp.content, resolved_version
        except httpx.TimeoutException:
            logger.warning(f"ClawHub 下载超时: {slug}")
            return None, None
        except Exception as e:
            logger.warning(f"ClawHub 下载异常: {e}")
            return None, None

    @staticmethod
    def _extract_zip(zip_bytes: bytes, target_dir: Path) -> List[str]:
        """解压 ZIP 到目标目录

        Args:
            zip_bytes: ZIP 文件字节数据
            target_dir: 目标目录

        Returns:
            解压出的文件列表
        """
        extracted = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # 安全检查：拒绝包含 .. 或绝对路径的条目
            for member in zf.namelist():
                if member.startswith("/") or ".." in Path(member).parts:
                    raise ValueError(f"ZIP 包含不安全的路径: {member}")

            zf.extractall(target_dir)
            extracted = zf.namelist()
        return extracted

    @staticmethod
    def _locate_skill_root(base_dir: Path) -> Optional[Path]:
        """定位包含 SKILL.md 的实际目录

        ZIP 包可能：
        1. 直接包含 SKILL.md（根目录就是 Skill 根）
        2. 包含一层子目录，子目录里有 SKILL.md

        Returns:
            Skill 根目录路径，找不到返回 None
        """
        # 情况 1：base_dir/SKILL.md
        if (base_dir / "SKILL.md").exists():
            return base_dir

        # 情况 2：base_dir/<subdir>/SKILL.md
        for item in base_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                return item

        return None

    @staticmethod
    def _now_iso() -> str:
        """获取当前时间的 ISO 格式字符串"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
