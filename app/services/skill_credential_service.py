"""
Skill 凭证管理服务

负责管理 ClawHub Skill 的凭证（API Key、Auth Token 等）。

支持两种凭证配置方式：
1. **frontmatter env 声明** - 在 SKILL.md 的 YAML frontmatter 中声明需要的环境变量
   ```yaml
   metadata:
     openclaw:
       env:
         - name: IFIND_AUTH_TOKEN
           description: "认证 token"
           required: true
   ```
   执行脚本时，将凭证值注入为环境变量。

2. **命令行参数式配置** - 通过脚本自身的配置命令（如 `--set-token`）配置
   例如 ifind-repilot-finance-data-search Skill：
   ```bash
   python3 <skill_dir>/scripts/fetch_data.py --set-token <your_auth_token>
   ```
   凭证存储在脚本指定的位置（如 ~/.config/ifind-repilot/config.json）。

凭证加密存储：
- 使用 Fernet 加密（AES-128-CBC + HMAC-SHA256）
- 密钥从 JWT_SECRET 派生（复用项目已有机制）
- 存储在 MongoDB skill_credentials 集合
"""

import base64
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("webapi")

# 凭证存储集合
CREDENTIALS_COLLECTION = "skill_credentials"


def _get_encryption_key() -> bytes:
    """获取加密密钥（基于 JWT_SECRET 派生）

    复用 mcp.py 中的加密机制，保持一致性。
    """
    secret = os.getenv("JWT_SECRET", "trading-agents-default-secret")
    return hashlib.sha256(secret.encode()).digest()


def _get_fernet():
    """获取 Fernet 实例"""
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(_get_encryption_key())
    return Fernet(key)


def _encrypt_value(plain: str) -> str:
    """加密凭证值

    输出格式：v2:<fernet_token>
    """
    f = _get_fernet()
    token = f.encrypt(plain.encode("utf-8")).decode("ascii")
    return f"v2:{token}"


def _decrypt_value(cipher: str) -> str:
    """解密凭证值

    支持两种格式：
    - v2:<fernet_token>：新格式，Fernet 解密
    - <base64>：旧格式，XOR + base64 解密（向后兼容）
    """
    if cipher.startswith("v2:"):
        f = _get_fernet()
        token = cipher[3:].encode("ascii")
        return f.decrypt(token).decode("utf-8")
    else:
        # 旧格式兼容
        key = _get_encryption_key()
        data = base64.b64decode(cipher)
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return decrypted.decode("utf-8")


def _mask_value(value: str) -> str:
    """遮蔽显示：只显示前4位和后4位"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


class CredentialDeclaration:
    """凭证声明（从 SKILL.md 解析）"""

    def __init__(
        self,
        name: str,
        description: str = "",
        required: bool = False,
        config_type: str = "env",  # env | script_arg
        config_command: str = "",  # 仅 script_arg 类型，如 "--set-token"
        config_position: int = 0,  # 配置命令在 instructions 中的位置
    ):
        self.name = name
        self.description = description
        self.required = required
        self.config_type = config_type  # env: 环境变量注入；script_arg: 脚本命令配置
        self.config_command = config_command
        self.config_position = config_position

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "config_type": self.config_type,
            "config_command": self.config_command,
        }


class SkillCredentialService:
    """Skill 凭证管理服务"""

    # =============================================================
    # 凭证声明解析
    # =============================================================

    @staticmethod
    def parse_credentials_from_skill_md(skill_dir: str) -> List[CredentialDeclaration]:
        """从 SKILL.md 解析需要的凭证声明

        解析顺序：
        1. 从 frontmatter metadata.openclaw.env 解析（标准方式）
        2. 从 instructions 中解析 --set-token 等配置命令（命令行参数式）

        Args:
            skill_dir: Skill 包目录路径

        Returns:
            凭证声明列表
        """
        skill_md_path = Path(skill_dir) / "SKILL.md"
        if not skill_md_path.exists():
            return []

        content = skill_md_path.read_text(encoding="utf-8")
        return SkillCredentialService._parse_credentials_from_content(content)

    @staticmethod
    def _parse_credentials_from_content(content: str) -> List[CredentialDeclaration]:
        """从 SKILL.md 内容解析凭证声明"""
        declarations: List[CredentialDeclaration] = []

        # 1. 解析 frontmatter
        frontmatter, body = SkillCredentialService._split_frontmatter(content)
        if frontmatter:
            try:
                metadata = yaml.safe_load(frontmatter)
                if isinstance(metadata, dict):
                    declarations.extend(
                        SkillCredentialService._parse_env_from_frontmatter(metadata)
                    )
            except yaml.YAMLError as e:
                logger.warning(f"解析 SKILL.md frontmatter 失败: {e}")

        # 2. 从 instructions 中解析 --set-token 等配置命令
        if body:
            declarations.extend(
                SkillCredentialService._parse_config_commands_from_body(body)
            )

        # 去重（按 name）
        seen_names = set()
        unique: List[CredentialDeclaration] = []
        for decl in declarations:
            if decl.name not in seen_names:
                seen_names.add(decl.name)
                unique.append(decl)

        return unique

    @staticmethod
    def _split_frontmatter(content: str):
        """分离 YAML frontmatter 和 body"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n?(.*)"
        match = re.match(pattern, content.strip(), re.DOTALL)
        if match:
            return match.group(1), match.group(2)
        return None, content

    @staticmethod
    def _parse_env_from_frontmatter(metadata: Dict[str, Any]) -> List[CredentialDeclaration]:
        """从 frontmatter metadata.openclaw.env 解析凭证声明"""
        declarations: List[CredentialDeclaration] = []

        # 支持 metadata.openclaw.env
        meta = metadata.get("metadata") or {}
        if isinstance(meta, str):
            # 有些 SKILL.md 的 metadata 是 JSON 字符串
            try:
                import json
                meta = json.loads(meta)
            except (json.JSONDecodeError, ValueError):
                meta = {}

        if not isinstance(meta, dict):
            return declarations

        openclaw_meta = meta.get("openclaw") or {}
        if not isinstance(openclaw_meta, dict):
            return declarations

        env_decls = openclaw_meta.get("env") or []
        if not isinstance(env_decls, list):
            return declarations

        for env_decl in env_decls:
            if isinstance(env_decl, dict):
                declarations.append(CredentialDeclaration(
                    name=env_decl.get("name", ""),
                    description=env_decl.get("description", ""),
                    required=env_decl.get("required", False),
                    config_type="env",
                ))
            elif isinstance(env_decl, str):
                declarations.append(CredentialDeclaration(
                    name=env_decl,
                    description="",
                    required=True,
                    config_type="env",
                ))

        return declarations

    @staticmethod
    def _parse_config_commands_from_body(body: str) -> List[CredentialDeclaration]:
        """从 instructions 中解析 --set-token 等配置命令

        匹配模式：
        - `--set-token <your_auth_token>`
        - `--set-api-key <your_api_key>`
        - `--config-token <token>`
        - `--set-key <key>`

        提取变量名：set-token -> AUTH_TOKEN, set-api-key -> API_KEY
        """
        declarations: List[CredentialDeclaration] = []

        # 匹配 --set-xxx 或 --config-xxx 后跟占位符
        patterns = [
            (r"--set-(\w[\w-]*)\s+<([^>]+)>", "set"),
            (r"--config-(\w[\w-]*)\s+<([^>]+)>", "config"),
            (r"--set-(\w[\w-]*)\s+(\w+)", "set"),
        ]

        seen_commands = set()
        for pattern, prefix in patterns:
            for match in re.finditer(pattern, body):
                cmd_name = match.group(1).lower()
                placeholder = match.group(2)
                full_command = f"--{prefix}-{cmd_name}"

                if full_command in seen_commands:
                    continue
                seen_commands.add(full_command)

                # 从命令名推导环境变量名
                # set-token -> AUTH_TOKEN
                # set-api-key -> API_KEY
                # set-auth-token -> AUTH_TOKEN
                var_name = SkillCredentialService._derive_var_name(cmd_name)

                # 从占位符推导描述
                description = f"通过 `{full_command}` 命令配置"

                declarations.append(CredentialDeclaration(
                    name=var_name,
                    description=description,
                    required=True,
                    config_type="script_arg",
                    config_command=full_command,
                ))

        return declarations

    @staticmethod
    def _derive_var_name(cmd_name: str) -> str:
        """从命令名推导环境变量名

        set-token -> AUTH_TOKEN
        set-api-key -> API_KEY
        set-auth-token -> AUTH_TOKEN
        """
        # 移除常见前缀
        parts = cmd_name.split("-")
        # 过滤掉 set/config/auth 等前缀词
        filtered = [p for p in parts if p not in ("set", "config", "auth", "the", "your")]
        if not filtered:
            filtered = parts
        return "_".join(p.upper() for p in filtered)

    # =============================================================
    # 凭证存储（MongoDB + Fernet 加密）
    # =============================================================

    @staticmethod
    async def save_credentials(
        db: AsyncIOMotorDatabase,
        skill_name: str,
        credentials: Dict[str, str],
    ) -> Dict[str, Any]:
        """保存 Skill 凭证（加密存储）

        Args:
            db: MongoDB 数据库
            skill_name: Skill 名称
            credentials: 凭证键值对（明文）

        Returns:
            {success, skill_name, saved_count}
        """
        if not credentials:
            return {"success": False, "message": "凭证不能为空"}

        # 加密所有凭证值
        encrypted = {
            key: _encrypt_value(str(value))
            for key, value in credentials.items()
            if value is not None and str(value) != ""
        }

        if not encrypted:
            return {"success": False, "message": "没有有效的凭证值"}

        # 写入 MongoDB（upsert）
        await db[CREDENTIALS_COLLECTION].update_one(
            {"skill_name": skill_name},
            {
                "$set": {
                    "skill_name": skill_name,
                    "credentials": encrypted,
                    "updated_at": SkillCredentialService._now_iso(),
                },
                "$setOnInsert": {
                    "created_at": SkillCredentialService._now_iso(),
                },
            },
            upsert=True,
        )

        logger.info(f"✅ Skill '{skill_name}' 凭证已保存（{len(encrypted)} 项）")
        return {
            "success": True,
            "skill_name": skill_name,
            "saved_count": len(encrypted),
        }

    @staticmethod
    async def get_credentials_decrypted(
        db: AsyncIOMotorDatabase,
        skill_name: str,
    ) -> Dict[str, str]:
        """获取 Skill 凭证（解密后的明文）

        注意：此方法返回明文，仅用于执行脚本时注入环境变量，
        不要用于 API 响应。

        Args:
            db: MongoDB 数据库
            skill_name: Skill 名称

        Returns:
            凭证键值对（明文）
        """
        doc = await db[CREDENTIALS_COLLECTION].find_one({"skill_name": skill_name})
        if not doc:
            return {}

        decrypted = {}
        for key, encrypted_value in doc.get("credentials", {}).items():
            try:
                decrypted[key] = _decrypt_value(encrypted_value)
            except Exception as e:
                logger.warning(f"⚠️ 解密凭证 '{key}' 失败: {e}")
                decrypted[key] = ""

        return decrypted

    @staticmethod
    async def get_credentials_status(
        db: AsyncIOMotorDatabase,
        skill_name: str,
        required_declarations: List[CredentialDeclaration] = None,
    ) -> Dict[str, Any]:
        """获取凭证配置状态（不返回明文）

        用于 API 响应，显示已配置/未配置状态和遮蔽值。

        Args:
            db: MongoDB 数据库
            skill_name: Skill 名称
            required_declarations: 需要的凭证声明列表（可选）

        Returns:
            {
                "skill_name": str,
                "required": [{name, description, required, config_type, config_command, configured, masked_value}],
                "extra": [{name, masked_value}],  # 已配置但未声明的凭证
                "all_configured": bool,
                "missing_required": [name]
            }
        """
        doc = await db[CREDENTIALS_COLLECTION].find_one({"skill_name": skill_name})
        stored_credentials = doc.get("credentials", {}) if doc else {}

        # 解密以生成遮蔽值
        decrypted = {}
        for key, encrypted_value in stored_credentials.items():
            try:
                decrypted[key] = _decrypt_value(encrypted_value)
            except Exception:
                decrypted[key] = ""

        required_list = []
        missing_required = []
        configured_names = set(stored_credentials.keys())

        if required_declarations:
            for decl in required_declarations:
                is_configured = decl.name in decrypted and bool(decrypted[decl.name])
                masked_value = _mask_value(decrypted[decl.name]) if is_configured else ""
                required_list.append({
                    "name": decl.name,
                    "description": decl.description,
                    "required": decl.required,
                    "config_type": decl.config_type,
                    "config_command": decl.config_command,
                    "configured": is_configured,
                    "masked_value": masked_value,
                })
                if decl.required and not is_configured:
                    missing_required.append(decl.name)

        # 已配置但未声明的凭证
        declared_names = {d.name for d in required_declarations} if required_declarations else set()
        extra_list = []
        for key, value in decrypted.items():
            if key not in declared_names:
                extra_list.append({
                    "name": key,
                    "masked_value": _mask_value(value),
                })

        return {
            "skill_name": skill_name,
            "required": required_list,
            "extra": extra_list,
            "all_configured": len(missing_required) == 0,
            "missing_required": missing_required,
        }

    @staticmethod
    async def delete_credentials(
        db: AsyncIOMotorDatabase,
        skill_name: str,
        keys: List[str] = None,
    ) -> Dict[str, Any]:
        """删除 Skill 凭证

        Args:
            db: MongoDB 数据库
            skill_name: Skill 名称
            keys: 要删除的凭证键列表（None 表示删除全部）

        Returns:
            {success, deleted_count}
        """
        if keys is None:
            # 删除全部
            result = await db[CREDENTIALS_COLLECTION].delete_many({"skill_name": skill_name})
            deleted = result.deleted_count
        else:
            # 删除指定键
            doc = await db[CREDENTIALS_COLLECTION].find_one({"skill_name": skill_name})
            if not doc:
                return {"success": True, "deleted_count": 0}

            existing = doc.get("credentials", {})
            deleted = 0
            for key in keys:
                if key in existing:
                    del existing[key]
                    deleted += 1

            if not existing:
                await db[CREDENTIALS_COLLECTION].delete_one({"skill_name": skill_name})
            else:
                await db[CREDENTIALS_COLLECTION].update_one(
                    {"skill_name": skill_name},
                    {"$set": {"credentials": existing, "updated_at": SkillCredentialService._now_iso()}},
                )

        logger.info(f"✅ Skill '{skill_name}' 凭证已删除（{deleted} 项）")
        return {"success": True, "deleted_count": deleted}

    # =============================================================
    # 命令行参数式凭证配置
    # =============================================================

    @staticmethod
    async def configure_via_script(
        skill_dir: str,
        script_path: str,
        config_command: str,
        credential_value: str,
        timeout: int = 30,
        python_executable: str = "python",
    ) -> Dict[str, Any]:
        """通过脚本的配置命令配置凭证

        适用于使用 --set-token 等命令配置凭证的 Skill。
        例如：python scripts/fetch_data.py --set-token <token>

        Args:
            skill_dir: Skill 包目录
            script_path: 脚本相对路径（如 "scripts/fetch_data.py"）
            config_command: 配置命令（如 "--set-token"）
            credential_value: 凭证值
            timeout: 超时秒数
            python_executable: Python 解释器

        Returns:
            {success, stdout, stderr, message}
        """
        import subprocess

        skill_dir_path = Path(skill_dir).resolve()
        full_script_path = skill_dir_path / script_path

        if not full_script_path.exists():
            return {
                "success": False,
                "message": f"脚本文件不存在: {full_script_path}",
            }

        # 构建命令：python scripts/fetch_data.py --set-token <token>
        cmd = [python_executable, str(full_script_path), config_command, credential_value]

        try:
            logger.info(f"🔧 执行凭证配置命令: {config_command}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(skill_dir_path),
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "message": "凭证配置成功",
                }
            else:
                return {
                    "success": False,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "message": f"配置失败: {result.stderr or result.stdout or '未知错误'}",
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": f"配置命令执行超时（{timeout}秒）",
            }
        except Exception as e:
            logger.error(f"❌ 凭证配置命令执行异常: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    # =============================================================
    # 辅助方法
    # =============================================================

    @staticmethod
    def _now_iso() -> str:
        """获取当前时间的 ISO 格式字符串"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
