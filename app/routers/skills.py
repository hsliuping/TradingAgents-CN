"""
Skill 管理 API

基于 Agent Skills 标准 + 扩展字段的 Skill CRUD 接口。
支持：导入 SKILL.md、从 URL 导入、列表查询、更新、删除、启用/禁用、注册到 ToolRegistry
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.services.capability_index_service import CapabilityIndexService
from core.skills.models import SkillMetadata, SkillParameter, SkillReturns, ImplementationType
from core.skills.parser import SkillParser
from core.skills.converter import SkillConverter
from core.skills.executor import SkillExecutor
from core.tools.registry import get_tool_registry

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/skills", tags=["skills"])

COLLECTION = "skills"


# =============================================================================
# 请求/响应模型
# =============================================================================

class SkillResponse(BaseModel):
    """Skill 响应模型"""
    id: str = ""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    tags: List[str] = []
    icon: str = "🔧"
    color: str = "#95a5a6"
    when_to_use: str = ""
    parameters: List[Dict[str, Any]] = []
    returns: Optional[Dict[str, Any]] = None
    implementation: Optional[Dict[str, Any]] = None
    instructions: str = ""
    enabled: bool = True
    fc_enabled: bool = True
    is_builtin: bool = False
    skill_type: str = "knowledge"
    is_executable: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SkillCreateRequest(BaseModel):
    """创建 Skill 请求"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    tags: List[str] = []
    icon: str = "🔧"
    color: str = "#95a5a6"
    when_to_use: str = ""
    parameters: List[Dict[str, Any]] = []
    returns: Optional[Dict[str, Any]] = None
    implementation: Optional[Dict[str, Any]] = None
    instructions: str = ""
    enabled: bool = True
    fc_enabled: bool = True


class SkillImportRequest(BaseModel):
    """导入 SKILL.md 请求"""
    content: str = Field(..., description="SKILL.md 文件内容")


class SkillImportUrlRequest(BaseModel):
    """从 URL 导入请求"""
    url: str = Field(..., description="SKILL.md 的直链 URL，如 GitHub raw 地址")


class SkillToggleRequest(BaseModel):
    """启用/禁用请求"""
    enabled: bool


# =============================================================================
# 辅助函数
# =============================================================================

def _doc_to_response(doc: Dict[str, Any]) -> SkillResponse:
    """将 MongoDB 文档转换为 SkillResponse"""
    doc.pop("_id", None)
    impl = doc.get("implementation")
    has_impl = impl is not None
    params = doc.get("parameters", [])
    skill_type = "knowledge"
    if has_impl:
        skill_type = impl.get("type", "unknown") if isinstance(impl, dict) else "unknown"
    return SkillResponse(
        id=doc.get("name", ""),
        name=doc.get("name", ""),
        description=doc.get("description", ""),
        version=doc.get("version", "1.0.0"),
        author=doc.get("author", ""),
        category=doc.get("category", "general"),
        tags=doc.get("tags", []),
        icon=doc.get("icon", "🔧"),
        color=doc.get("color", "#95a5a6"),
        when_to_use=doc.get("when_to_use", ""),
        parameters=params,
        returns=doc.get("returns"),
        implementation=impl,
        instructions=doc.get("instructions", ""),
        enabled=doc.get("enabled", True),
        fc_enabled=doc.get("fc_enabled", True),
        is_builtin=doc.get("is_builtin", False),
        skill_type=skill_type,
        is_executable=has_impl,
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
    )


def _skill_to_doc(skill: SkillMetadata) -> Dict[str, Any]:
    """将 SkillMetadata 转换为 MongoDB 文档"""
    doc = skill.model_dump(exclude_none=True)
    # 确保时间戳为字符串
    now = datetime.utcnow().isoformat()
    if "created_at" not in doc or not doc["created_at"]:
        doc["created_at"] = now
    doc["updated_at"] = now
    return doc


def _request_to_doc(req: SkillCreateRequest) -> Dict[str, Any]:
    """将创建请求转换为 MongoDB 文档"""
    doc = req.model_dump(exclude_none=True)
    now = datetime.utcnow().isoformat()
    doc["created_at"] = now
    doc["updated_at"] = now
    doc["is_builtin"] = False
    return doc


async def _register_skill_to_registry(doc: Dict[str, Any]):
    """将 Skill 注册到 ToolRegistry（如果是可执行 Skill）"""
    impl = doc.get("implementation")
    params = doc.get("parameters", [])
    if not impl or not params:
        return
    try:
        skill = SkillMetadata(**{k: v for k, v in doc.items() if k != "_id"})
        wrapper = SkillExecutor.create_sync_wrapper(skill)
        registry = get_tool_registry()
        tool_id = skill.name.replace("-", "_")
        registry.register_function(
            tool_id=tool_id,
            func=wrapper,
            name=skill.description[:50],
            category=skill.category,
            description=skill.description,
            is_online=True,
            override=True,
        )
        logger.info(f"✅ Skill '{skill.name}' 已注册到 ToolRegistry (tool_id={tool_id})")
    except Exception as e:
        logger.warning(f"⚠️ Skill 注册到 ToolRegistry 失败: {e}")


async def _sync_capability_index(db: AsyncIOMotorDatabase):
    try:
        await CapabilityIndexService(db).ensure_index()
    except Exception as e:
        logger.warning(f"⚠️ CapabilityIndex 同步失败: {e}")


# =============================================================================
# API 端点
# =============================================================================

@router.get("", response_model=List[SkillResponse])
async def list_skills(
    category: Optional[str] = Query(None, description="按分类筛选"),
    enabled: Optional[bool] = Query(None, description="按启用状态筛选"),
    skill_type: Optional[str] = Query(None, description="按类型筛选: knowledge, python, http, mcp"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取所有 Skill 列表"""
    query = {}
    if category:
        query["category"] = category
    if enabled is not None:
        query["enabled"] = enabled

    skills = []
    async for doc in db[COLLECTION].find(query).sort("created_at", -1):
        resp = _doc_to_response(doc)
        if skill_type:
            if resp.skill_type != skill_type:
                continue
        skills.append(resp)
    return skills


@router.get("/categories")
async def list_skill_categories(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取所有 Skill 分类"""
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    categories = []
    async for doc in db[COLLECTION].aggregate(pipeline):
        categories.append({"id": doc["_id"], "name": doc["_id"], "count": doc["count"]})
    return categories


@router.post("", response_model=SkillResponse)
async def create_skill(
    req: SkillCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """创建新 Skill"""
    # 检查是否已存在
    existing = await db[COLLECTION].find_one({"name": req.name})
    if existing:
        raise HTTPException(status_code=400, detail=f"Skill '{req.name}' 已存在")

    doc = _request_to_doc(req)
    await db[COLLECTION].insert_one(doc)

    # 注册到 ToolRegistry
    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    doc.pop("_id", None)
    return _doc_to_response(doc)


@router.post("/import", response_model=SkillResponse)
async def import_skill(
    req: SkillImportRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从 SKILL.md 内容导入 Skill"""
    try:
        skill = SkillParser.parse_content(req.content)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"SKILL.md 解析失败: {e}")

    # 检查是否已存在
    existing = await db[COLLECTION].find_one({"name": skill.name})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{skill.name}' 已存在，请使用更新接口",
        )

    doc = _skill_to_doc(skill)
    await db[COLLECTION].insert_one(doc)

    # 注册到 ToolRegistry
    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    doc.pop("_id", None)
    return _doc_to_response(doc)


@router.post("/import-url", response_model=SkillResponse)
async def import_skill_from_url(
    req: SkillImportUrlRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """从网络 URL 获取并导入 SKILL.md"""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # 若为 GitHub 网页链接，尝试转为 raw 链接
    if "github.com" in url and "/blob/" in url and "raw.githubusercontent.com" not in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
            if not text or len(text.strip()) < 10:
                raise HTTPException(status_code=400, detail="URL 返回内容为空或无效")
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="请求超时，请检查 URL 或网络")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"无法获取 URL 内容: HTTP {e.response.status_code}",
        )
    except Exception as e:
        logger.warning(f"从 URL 获取 Skill 失败: {e}")
        raise HTTPException(status_code=400, detail=f"获取 URL 失败: {str(e)}")

    try:
        skill = SkillParser.parse_content(text)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"SKILL.md 解析失败: {e}")

    existing = await db[COLLECTION].find_one({"name": skill.name})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{skill.name}' 已存在，请使用更新接口或先删除再导入",
        )

    doc = _skill_to_doc(skill)
    doc["source_url"] = url
    await db[COLLECTION].insert_one(doc)
    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    doc.pop("_id", None)
    logger.info(f"✅ 从 URL 导入 Skill: {skill.name}")
    return _doc_to_response(doc)


@router.post("/import-file", response_model=SkillResponse)
async def import_skill_file(
    file: UploadFile = File(..., description="SKILL.md 文件"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """上传并导入 SKILL.md 文件"""
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码必须为 UTF-8")

    try:
        skill = SkillParser.parse_content(text)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"SKILL.md 解析失败: {e}")

    existing = await db[COLLECTION].find_one({"name": skill.name})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{skill.name}' 已存在，请使用更新接口",
        )

    doc = _skill_to_doc(skill)
    doc["source_file"] = file.filename
    await db[COLLECTION].insert_one(doc)

    await _register_skill_to_registry(doc)
    await _sync_capability_index(db)

    doc.pop("_id", None)
    return _doc_to_response(doc)


@router.get("/{skill_name}", response_model=SkillResponse)
async def get_skill(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 Skill 详情"""
    doc = await db[COLLECTION].find_one({"name": skill_name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")
    return _doc_to_response(doc)


@router.put("/{skill_name}", response_model=SkillResponse)
async def update_skill(
    skill_name: str,
    req: SkillCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新 Skill"""
    existing = await db[COLLECTION].find_one({"name": skill_name})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    if existing.get("is_builtin", False):
        raise HTTPException(status_code=400, detail="内置 Skill 不可修改")

    update_doc = req.model_dump(exclude_none=True)
    update_doc["updated_at"] = datetime.utcnow().isoformat()
    # 如果改名，需要同时更新 name
    update_doc["name"] = req.name

    await db[COLLECTION].update_one({"name": skill_name}, {"$set": update_doc})

    # 重新注册到 ToolRegistry
    updated = await db[COLLECTION].find_one({"name": req.name})
    if updated:
        await _register_skill_to_registry(updated)
        await _sync_capability_index(db)

    return _doc_to_response(updated or update_doc)


@router.delete("/{skill_name}")
async def delete_skill(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除 Skill"""
    existing = await db[COLLECTION].find_one({"name": skill_name})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    if existing.get("is_builtin", False):
        raise HTTPException(status_code=400, detail="内置 Skill 不可删除")

    await db[COLLECTION].delete_one({"name": skill_name})

    # 从 ToolRegistry 注销
    tool_id = skill_name.replace("-", "_")
    registry = get_tool_registry()
    registry.unregister(tool_id)
    await _sync_capability_index(db)

    return {"success": True, "message": f"Skill '{skill_name}' 已删除"}


@router.post("/{skill_name}/toggle")
async def toggle_skill(
    skill_name: str,
    req: SkillToggleRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """启用/禁用 Skill"""
    existing = await db[COLLECTION].find_one({"name": skill_name})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    await db[COLLECTION].update_one(
        {"name": skill_name},
        {"$set": {"enabled": req.enabled, "updated_at": datetime.utcnow().isoformat()}},
    )

    tool_id = skill_name.replace("-", "_")
    registry = get_tool_registry()
    if req.enabled:
        updated = await db[COLLECTION].find_one({"name": skill_name})
        if updated:
            await _register_skill_to_registry(updated)
    else:
        registry.unregister(tool_id)
    await _sync_capability_index(db)

    status = "启用" if req.enabled else "禁用"
    return {"success": True, "message": f"Skill '{skill_name}' 已{status}"}


@router.get("/{skill_name}/export")
async def export_skill(
    skill_name: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """导出 Skill 为 SKILL.md 格式"""
    doc = await db[COLLECTION].find_one({"name": skill_name})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 不存在")

    doc.pop("_id", None)

    # 构建 YAML frontmatter
    import yaml
    frontmatter_fields = {}
    for key in ("name", "description", "version", "author", "category", "tags",
                "when_to_use", "parameters", "returns", "implementation",
                "enabled", "fc_enabled"):
        val = doc.get(key)
        if val is not None and val != "" and val != []:
            frontmatter_fields[key] = val

    yaml_str = yaml.dump(frontmatter_fields, allow_unicode=True, default_flow_style=False, sort_keys=False)
    instructions = doc.get("instructions", "")

    skill_md = f"---\n{yaml_str}---\n\n{instructions}\n"

    return {"content": skill_md, "filename": f"{skill_name}.SKILL.md"}

