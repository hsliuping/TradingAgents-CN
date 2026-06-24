"""
SkillHub Skill 搜索与安装服务

通过 skillhub CLI (npm 包) 搜索和安装 Skill。
Skill 实际存储在 GitHub 仓库中，CLI 负责从 GitHub 下载和解压。
有些 Skill 是 SkillHub 特有的，不在 ClawHub 上，所以需要用 CLI。

首次使用时自动检测并安装 skillhub CLI (npm install -g skillhub)。

CLI 命令：
- skillhub search "<query>" --json --limit <n>
- skillhub install <skill-id> --project --force

安装后 Skill 位于 .claude/skills/<name>/，需要移动到 skills/<name>/
然后复用 _import_local_skill_to_db 导入到 MongoDB。
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("webapi")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
CLAUDE_SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

# CLI 自动安装锁（防止并发请求重复安装）
_cli_install_lock = asyncio.Lock()
_cli_checked = False  # 进程级缓存：已确认 CLI 可用


class SkillHubService:
    """SkillHub Skill 搜索与安装服务（通过 CLI 子进程）"""

    CLI_TIMEOUT = 60  # 搜索/安装超时秒数
    INSTALL_TIMEOUT = 120  # 安装 Skill 包超时秒数

    # =============================================================
    # CLI 自动安装
    # =============================================================

    @classmethod
    async def _ensure_cli(cls) -> bool:
        """确保 skillhub CLI 可用，不可用则自动安装

        Returns:
            True 如果 CLI 可用，False 如果安装失败
        """
        global _cli_checked
        if _cli_checked:
            return True

        async with _cli_install_lock:
            # double-check
            if _cli_checked:
                return True

            # 1. 检查是否已安装
            if await cls._is_cli_available():
                _cli_checked = True
                return True

            # 2. 自动安装
            logger.info("📦 skillhub CLI 未安装，正在自动安装 (npm install -g skillhub)...")
            ok = await cls._install_cli()
            if ok:
                _cli_checked = True
                logger.info("✅ skillhub CLI 安装成功")
            else:
                logger.error("❌ skillhub CLI 自动安装失败")
            return ok

    @staticmethod
    async def _is_cli_available() -> bool:
        """检查 skillhub CLI 是否可用"""
        try:
            proc = await asyncio.create_subprocess_shell(
                "skillhub --version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            return False
        except Exception:
            return False

    @staticmethod
    async def _install_cli() -> bool:
        """通过 npm 全局安装 skillhub CLI"""
        try:
            proc = await asyncio.create_subprocess_shell(
                "npm install -g skillhub",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode == 0:
                return True
            err = stderr.decode("utf-8", errors="replace") if stderr else ""
            logger.error(f"npm install -g skillhub 失败: {err[:300]}")
            return False
        except Exception as e:
            logger.error(f"npm install -g skillhub 异常: {e}")
            return False

    # =============================================================
    # 公开方法
    # =============================================================

    @classmethod
    async def search_skills(cls, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索 SkillHub 上的 Skill

        调用: skillhub search "<query>" --json --limit <n>
        """
        if not query.strip():
            return []

        # 确保 CLI 可用
        if not await cls._ensure_cli():
            logger.error("skillhub CLI 不可用，无法搜索")
            return []

        try:
            # 用 shell 方式调用（Windows 上 skillhub 是 .cmd 文件）
            cmd = f'skillhub search "{query}" --json --limit {limit}'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(PROJECT_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=cls.CLI_TIMEOUT)

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace") if stderr else ""
                logger.warning(f"skillhub search 失败 (exit={proc.returncode}): {err[:200]}")
                return []

            data = json.loads(stdout.decode("utf-8"))
            raw_skills = data.get("skills", []) if isinstance(data, dict) else []

            # 标准化字段
            normalized = []
            for item in raw_skills:
                if not isinstance(item, dict):
                    continue
                skill_id = item.get("id", "")
                parts = skill_id.split("/")
                slug = parts[-1] if parts else skill_id
                owner = parts[0] if len(parts) >= 1 else ""

                normalized.append({
                    "slug": slug,
                    "skill_id": skill_id,
                    "display_name": item.get("name") or slug,
                    "summary": item.get("description") or "",
                    "version": "",
                    "owner_handle": owner,
                    "github_owner": item.get("githubOwner", ""),
                    "github_repo": item.get("githubRepo", ""),
                    "github_stars": item.get("githubStars", 0),
                    "download_count": item.get("downloadCount", 0),
                    "security_score": item.get("securityScore", 0),
                    "security_status": item.get("securityStatus") or "",
                    "ai_score": item.get("aiScore"),
                    "rating": item.get("rating", 0),
                    "is_verified": item.get("isVerified", False),
                    "canonical_url": f"https://skillhub.cn/skills/{slug}",
                })

            # 按下载量倒序排列（CLI 不支持 --sort 参数，在 Python 端排序）
            normalized.sort(key=lambda x: x.get("download_count", 0), reverse=True)
            logger.info(f"📊 SkillHub 搜索结果已按下载量倒序排列 (top: {normalized[0]['download_count'] if normalized else 0})")

            return normalized

        except asyncio.TimeoutError:
            logger.warning("skillhub search 超时")
            return []
        except Exception as e:
            logger.warning(f"skillhub search 异常: {e}")
            return []

    @classmethod
    async def install_skill(cls, skill_id: str) -> Dict[str, Any]:
        """从 SkillHub 安装 Skill 到本地目录

        流程：
        1. 调用 skillhub install <id> --project --force
        2. 安装到 .claude/skills/<name>/
        3. 移动到 skills/<name>/
        4. 校验 SKILL.md 和 scripts/ 存在
        """
        skill_id = skill_id.strip()
        if not skill_id:
            return {"success": False, "message": "skill_id 不能为空"}

        # 确保 CLI 可用
        if not await cls._ensure_cli():
            return {"success": False, "message": "skillhub CLI 自动安装失败，请手动运行: npm install -g skillhub"}

        # skill_id 格式: "owner/repo/skill-name"，取最后一段作为 slug
        parts = skill_id.split("/")
        slug = parts[-1] if parts else skill_id

        # 1. 调用 CLI 安装
        try:
            cmd = f'skillhub install "{skill_id}" --project --force'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(PROJECT_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=cls.INSTALL_TIMEOUT)

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace") if stderr else ""
                return {"success": False, "message": f"skillhub install 失败: {err[:300]}"}

            logger.info(f"✅ skillhub install 成功: {skill_id}")
        except asyncio.TimeoutError:
            return {"success": False, "message": f"安装超时（{cls.INSTALL_TIMEOUT}s）"}
        except Exception as e:
            return {"success": False, "message": f"安装异常: {e}"}

        # 2. 定位安装目录（.claude/skills/<slug>/）
        installed_dir = CLAUDE_SKILLS_DIR / slug
        if not installed_dir.exists():
            installed_dir = cls._find_installed_skill(slug)
            if installed_dir is None:
                return {
                    "success": False,
                    "message": f"CLI 安装完成但未在 {CLAUDE_SKILLS_DIR} 找到 Skill 目录",
                }

        # 3. 移动到 skills/<slug>/
        target_dir = SKILLS_DIR / slug
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(installed_dir), str(target_dir))
        except Exception as e:
            return {"success": False, "message": f"移动 Skill 目录失败: {e}"}

        # 4. 校验 SKILL.md
        if not (target_dir / "SKILL.md").exists():
            shutil.rmtree(target_dir, ignore_errors=True)
            return {"success": False, "message": "Skill 包中未找到 SKILL.md"}

        # 5. 校验 scripts/ 或根目录 .py 文件
        # SkillHub 包结构可能有两种：
        #   A) scripts/*.py（ClawHub 标准）
        #   B) 根目录 *.py（如 stock-monitor/data_source.py, monitor.py 等）
        scripts_dir = target_dir / "scripts"
        has_scripts = False
        script_count = 0

        if scripts_dir.is_dir() and any(scripts_dir.iterdir()):
            has_scripts = True
            script_count = len([f for f in scripts_dir.iterdir() if f.suffix == ".py"])
        else:
            # 检查根目录是否有 .py 文件
            root_py_files = [f for f in target_dir.iterdir()
                             if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"]
            if root_py_files:
                has_scripts = True
                script_count = len(root_py_files)
                logger.info(f"📦 Skill '{slug}' 检测到根目录 Python 脚本: {[f.name for f in root_py_files]}")

        if not has_scripts:
            logger.info(f"📚 Skill '{slug}' 是知识型（无 Python 脚本），仍保留但标记为知识型")

        # 6. 写入来源信息
        origin_dir = target_dir / ".skillhub"
        origin_dir.mkdir(exist_ok=True)
        origin_info = {
            "source": "skillhub",
            "skill_id": skill_id,
            "slug": slug,
            "installed_at": cls._now_iso(),
        }
        (origin_dir / "origin.json").write_text(
            json.dumps(origin_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        script_count = len([f for f in scripts_dir.iterdir() if f.suffix == ".py"]) if has_scripts else 0

        return {
            "success": True,
            "skill_name": slug,
            "skill_dir": str(target_dir),
            "version": "",
            "has_scripts": has_scripts,
            "scripts_count": script_count,
            "message": f"Skill '{slug}' 安装成功",
        }

    # =============================================================
    # 内部方法
    # =============================================================

    @staticmethod
    def _find_installed_skill(slug: str) -> Optional[Path]:
        """在 .claude/skills/ 下查找已安装的 Skill 目录"""
        if not CLAUDE_SKILLS_DIR.exists():
            return None
        for item in CLAUDE_SKILLS_DIR.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                if item.name == slug or slug in item.name or item.name in slug:
                    return item
        # 如果没找到精确匹配，返回第一个有 SKILL.md 的目录
        for item in CLAUDE_SKILLS_DIR.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                return item
        return None

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
