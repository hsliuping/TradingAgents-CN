"""
社区版首次启动自举服务

背景：社区版不随包分发 install/ 与 scripts/（Pro 版由 docker-entrypoint.sh 调用
scripts/import_config_and_create_user.py 完成建号与配置导入），因此社区版首次启动时
空库无系统配置——模型目录、提示词模板、Agent 配置、工作流等全部缺失，登录后功能不可用。

本模块在应用启动阶段导入最小系统配置，幂等：install/community_bootstrap.json 存在时，
按"集合为空才导入"写入，Pro 版各集合非空时自动跳过，行为零影响。

建号不在此处：由 app/services/user_service.py::bootstrap_first_admin 负责（社区版无注册
接口，空库时依据 ADMIN_DEFAULT_PASSWORD 创建 admin）。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from bson import ObjectId

logger = logging.getLogger(__name__)

# 启动自举配置包（社区版快照内置：install/community_bootstrap.json）
BOOTSTRAP_FILENAME = "community_bootstrap.json"
INSTALL_DIRNAME = "install"

# 敏感字段模式：导入前二次脱敏，防止配置包携带密钥
_SECRET_KEY_PATTERNS = (
    "api_key", "apikey", "api_secret", "secret",
    "password", "access_token", "refresh_token",
)
_SECRET_KEY_SKIP = ("has_api_key", "has_api_secret", "max_tokens")


def _project_root() -> Path:
    """项目根目录（app/services/xxx.py → 上溯三级）"""
    return Path(__file__).resolve().parents[2]


def _sanitize(node: Any) -> Any:
    """递归清空敏感字段值（保留字段名），防止配置包意外携带密钥"""
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for key, value in node.items():
            lowered = key.lower()
            if lowered in _SECRET_KEY_SKIP:
                out[key] = _sanitize(value)
                continue
            if any(p in lowered for p in _SECRET_KEY_PATTERNS):
                out[key] = "" if isinstance(value, (str, type(None))) else _sanitize(value)
                continue
            out[key] = _sanitize(value)
        return out
    if isinstance(node, list):
        return [_sanitize(item) for item in node]
    return node


def _convert_to_bson(data: Any) -> Any:
    """JSON → BSON：还原 ObjectId 与 datetime（与 Pro 版导入脚本口径一致）"""
    if isinstance(data, dict):
        result: Dict[str, Any] = {}
        for key, value in data.items():
            if key == "_id" or key.endswith("_id"):
                if isinstance(value, str) and len(value) == 24:
                    try:
                        result[key] = ObjectId(value)
                        continue
                    except Exception:
                        pass
            if key.endswith("_at") or key in ("created_at", "updated_at", "last_login", "added_at"):
                if isinstance(value, str):
                    try:
                        result[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        continue
                    except Exception:
                        pass
            result[key] = _convert_to_bson(value)
        return result
    if isinstance(data, list):
        return [_convert_to_bson(item) for item in data]
    return data


async def import_bootstrap_config() -> int:
    """导入社区版最小系统配置（仅导入空集合，幂等）

    Returns:
        本次导入的文档总数
    """
    from app.core.database import get_mongo_db

    bootstrap_file = _project_root() / INSTALL_DIRNAME / BOOTSTRAP_FILENAME
    if not bootstrap_file.exists():
        return 0

    try:
        with open(bootstrap_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        logger.error(f"❌ 读取启动配置包失败: {bootstrap_file} ({e})")
        return 0

    data = payload.get("data") or {}
    if not isinstance(data, dict):
        logger.error(f"❌ 启动配置包格式不正确（缺少 data 段）: {bootstrap_file}")
        return 0

    db = get_mongo_db()
    total_inserted = 0
    imported_collections = []

    for collection_name, documents in data.items():
        if not isinstance(documents, list) or not documents:
            continue
        try:
            if await db[collection_name].count_documents({}) > 0:
                continue
            converted = [_convert_to_bson(_sanitize(doc)) for doc in documents]
            await db[collection_name].insert_many(converted, ordered=False)
            total_inserted += len(converted)
            imported_collections.append(f"{collection_name}({len(converted)})")
        except Exception as e:
            logger.error(f"❌ 导入集合 {collection_name} 失败: {e}")

    if total_inserted:
        logger.info(f"✅ 启动配置导入完成: {total_inserted} 个文档 → {', '.join(imported_collections)}")
        logger.info("📋 系统配置已就绪，首次登录后请在「系统设置」中配置 LLM 与数据源密钥")
    return total_inserted