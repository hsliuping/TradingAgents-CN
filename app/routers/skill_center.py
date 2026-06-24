from datetime import datetime
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId
from core.tools.registry import get_tool_registry
from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skill-center", tags=["skill-center"])

class SkillSummary(BaseModel):
    skill_id: str = Field(description="Skill ID")
    display_name: str = Field(description="显示名称")
    description: str = Field(description="描述")
    source: str = Field(description="来源: system/imported/ai_generated/gap_generated")
    type: str = Field(description="类型: knowledge/executable/api/mcp")
    status: str = Field(description="状态: draft/testing/active/disabled/archived/failed")
    bindable: bool = Field(description="是否可绑定")
    tool_id: Optional[str] = Field(description="工具ID")
    test_status: Optional[str] = Field(description="测试状态: passed/failed/unknown")
    last_tested_at: Optional[str] = Field(description="最后测试时间")
    bindings: Dict[str, List[str]] = Field(description="绑定关系")
    created_at: Optional[str] = Field(description="创建时间")
    updated_at: Optional[str] = Field(description="更新时间")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

def _convert_standard_skill(doc: dict) -> SkillSummary:
    tool_id = doc.get("name", "").replace("-", "_")
    implementation = doc.get("implementation")
    source_type = doc.get("source_type")
    return SkillSummary(
        skill_id=doc.get("name", str(doc.get("_id"))),
        display_name=doc.get("name", ""),
        description=doc.get("description", ""),
        source="clawhub" if source_type == "clawhub" else "imported",
        type="executable" if implementation or doc.get("executable", False) else "knowledge",
        status="active" if doc.get("enabled", False) else "disabled",
        bindable=True,
        tool_id=tool_id,
        test_status="unknown",
        last_tested_at=None,
        bindings={"agents": [], "workflows": []},
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at")
    )

def _convert_external_skill(doc: dict) -> SkillSummary:
    return SkillSummary(
        skill_id=doc.get("tool_id", str(doc.get("_id"))),
        display_name=doc.get("name", doc.get("tool_id", "")),
        description=doc.get("description", ""),
        source="ai_generated",
        type="executable",
        status=doc.get("status", "draft"),
        bindable=True,
        tool_id=doc.get("tool_id"),
        test_status=doc.get("test_status", "unknown"),
        last_tested_at=doc.get("last_test_at"),
        bindings={"agents": [], "workflows": []},
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at")
    )

async def _get_bindings_for_tool(db, tool_id: str) -> Dict[str, List[str]]:
    bindings = {"agents": [], "workflows": []}
    async for binding in db.tool_agent_bindings.find({"tool_id": tool_id, "is_active": {"$ne": False}}):
        if "agent_id" in binding:
            bindings["agents"].append(binding["agent_id"])
    return bindings

async def _check_registry_status(tool_id: str) -> bool:
    try:
        registry = get_tool_registry()
        return registry.has_tool(tool_id)
    except:
        return False

@router.get("/skills", response_model=List[SkillSummary])
async def list_all_skills(
    db = Depends(get_mongo_db),
    status: Optional[str] = Query(None, description="按状态过滤"),
    source: Optional[str] = Query(None, description="按来源过滤"),
    user = Depends(get_current_user)
):
    all_skills = []
    
    async for doc in db.skills.find():
        skill = _convert_standard_skill(doc)
        skill.bindings = await _get_bindings_for_tool(db, skill.tool_id)
        all_skills.append(skill)
    
    async for doc in db.external_skills.find():
        skill = _convert_external_skill(doc)
        skill.bindings = await _get_bindings_for_tool(db, skill.tool_id)
        all_skills.append(skill)
    
    if status:
        all_skills = [s for s in all_skills if s.status == status]
    
    if source:
        all_skills = [s for s in all_skills if s.source == source]
    
    all_skills.sort(key=lambda x: x.updated_at or x.created_at or "", reverse=True)
    return all_skills

@router.get("/skills/{skill_id}", response_model=SkillSummary)
async def get_skill_detail(
    skill_id: str,
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    doc = await db.skills.find_one({"name": skill_id})
    if doc:
        skill = _convert_standard_skill(doc)
        skill.bindings = await _get_bindings_for_tool(db, skill.tool_id)
        return skill
    
    doc = await db.external_skills.find_one({"tool_id": skill_id})
    if doc:
        skill = _convert_external_skill(doc)
        skill.bindings = await _get_bindings_for_tool(db, skill.tool_id)
        return skill
    
    doc = await db.external_skills.find_one({"_id": ObjectId(skill_id)})
    if doc:
        skill = _convert_external_skill(doc)
        skill.bindings = await _get_bindings_for_tool(db, skill.tool_id)
        return skill
    
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Skill not found")

@router.get("/skills/{skill_id}/test")
async def test_skill(
    skill_id: str,
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    from fastapi import HTTPException
    
    doc = await db.external_skills.find_one({"tool_id": skill_id})
    if doc:
        from core.tools.external_skill_loader import register_single_external_skill
        from core.tools.registry import get_tool_registry
        
        registry = get_tool_registry()
        try:
            register_single_external_skill(None, registry, doc)
            tool = registry.get_tool(skill_id)
            if tool:
                test_result = tool.test() if hasattr(tool, 'test') else {"status": "no_test_method"}
                return {"success": True, "result": test_result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    doc = await db.skills.find_one({"name": skill_id})
    if doc:
        tool_id = doc.get("name", "").replace("-", "_")
        registry = get_tool_registry()
        tool = registry.get_tool(tool_id)
        if tool:
            try:
                test_result = tool.test() if hasattr(tool, 'test') else {"status": "no_test_method"}
                return {"success": True, "result": test_result}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    raise HTTPException(status_code=404, detail="Skill not found")

@router.post("/skills/{skill_id}/bind/{agent_id}")
async def bind_skill_to_agent(
    skill_id: str,
    agent_id: str,
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    """绑定 Skill 到 Agent"""
    from core.config.binding_manager import BindingManager

    binding_mgr = BindingManager()
    binding_mgr.set_database(db)

    success = binding_mgr.bind_tool(agent_id, skill_id, priority=0)
    if not success:
        raise HTTPException(status_code=500, detail="绑定失败")

    return {"success": True, "message": "Skill bound to agent"}

@router.delete("/skills/{skill_id}/bind/{agent_id}")
async def unbind_skill_from_agent(
    skill_id: str,
    agent_id: str,
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    """解绑 Skill 与 Agent"""
    from core.config.binding_manager import BindingManager

    binding_mgr = BindingManager()
    binding_mgr.set_database(db)

    success = binding_mgr.unbind_tool(agent_id, skill_id)
    if not success:
        raise HTTPException(status_code=500, detail="解绑失败")

    return {"success": True, "message": "Skill unbound from agent"}


class BatchBindRequest(BaseModel):
    """批量绑定请求"""
    agent_ids: List[str] = Field(..., description="Agent ID 列表")
    priority: int = Field(0, description="优先级（越大越优先）")


@router.post("/skills/{skill_id}/bind-batch")
async def batch_bind_skill_to_agents(
    skill_id: str,
    req: BatchBindRequest,
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    """批量绑定 Skill 到多个 Agent"""
    from core.config.binding_manager import BindingManager

    binding_mgr = BindingManager()
    binding_mgr.set_database(db)

    bound = []
    failed = []
    for agent_id in req.agent_ids:
        try:
            success = binding_mgr.bind_tool(agent_id, skill_id, priority=req.priority)
            if success:
                bound.append(agent_id)
            else:
                failed.append(agent_id)
        except Exception as e:
            logger.error(f"绑定 {skill_id} -> {agent_id} 失败: {e}")
            failed.append(agent_id)

    return {
        "success": len(failed) == 0,
        "bound": bound,
        "failed": failed,
        "message": f"已绑定到 {len(bound)} 个 Agent" + (f"，{len(failed)} 个失败" if failed else "")
    }


@router.get("/skills/{skill_id}/bindings")
async def get_skill_bindings(
    skill_id: str,
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    """获取 Skill 的所有绑定关系"""
    bindings = await db.tool_agent_bindings.find(
        {"tool_id": skill_id, "is_active": {"$ne": False}}
    ).to_list(100)

    # 获取 Agent 详情
    agent_ids = [b["agent_id"] for b in bindings]
    agents = []
    for aid in agent_ids:
        # 从 BUILTIN_AGENTS 查找
        from core.agents.config import BUILTIN_AGENTS
        agent_meta = BUILTIN_AGENTS.get(aid)
        if agent_meta:
            agents.append({
                "agent_id": aid,
                "name": agent_meta.name,
                "category": agent_meta.category,
                "priority": next((b.get("priority", 0) for b in bindings if b["agent_id"] == aid), 0)
            })
        else:
            agents.append({
                "agent_id": aid,
                "name": aid,
                "category": "custom",
                "priority": next((b.get("priority", 0) for b in bindings if b["agent_id"] == aid), 0)
            })

    return {"agents": agents}


@router.get("/tool-logs")
async def get_tool_execution_logs(
    tool_id: Optional[str] = Query(None, description="按工具 ID 过滤"),
    agent_id: Optional[str] = Query(None, description="按 Agent ID 过滤"),
    analysis_id: Optional[str] = Query(None, description="按分析任务 ID 过滤"),
    success: Optional[bool] = Query(None, description="按成功/失败过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    """查询工具执行日志"""
    query = {}
    if tool_id:
        query["tool_id"] = tool_id
    if agent_id:
        query["agent_id"] = agent_id
    if analysis_id:
        query["analysis_id"] = analysis_id
    if success is not None:
        query["success"] = success

    logs = await db["tool_execution_logs"].find(query).sort("created_at", -1).limit(limit).to_list(limit)

    # 序列化
    for log in logs:
        log["_id"] = str(log["_id"])

    return {"logs": logs, "count": len(logs)}


@router.get("/tool-logs/stats")
async def get_tool_log_stats(
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    """工具执行日志统计"""
    total = await db["tool_execution_logs"].count_documents({})
    success_count = await db["tool_execution_logs"].count_documents({"success": True})
    fail_count = await db["tool_execution_logs"].count_documents({"success": False})

    # 按工具统计
    tool_pipeline = [
        {"$group": {"_id": "$tool_id", "count": {"$sum": 1}, "avg_ms": {"$avg": "$execution_time_ms"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    tool_stats = await db["tool_execution_logs"].aggregate(tool_pipeline).to_list(10)

    # 按 Agent 统计
    agent_pipeline = [
        {"$group": {"_id": "$agent_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    agent_stats = await db["tool_execution_logs"].aggregate(agent_pipeline).to_list(10)

    return {
        "total": total,
        "success": success_count,
        "failed": fail_count,
        "by_tool": [{"tool_id": s["_id"], "count": s["count"], "avg_ms": int(s.get("avg_ms", 0))} for s in tool_stats],
        "by_agent": [{"agent_id": s["_id"], "count": s["count"]} for s in agent_stats],
    }


@router.get("/stats")
async def get_skill_stats(
    db = Depends(get_mongo_db),
    user = Depends(get_current_user)
):
    standard_count = await db.skills.count_documents({})
    external_count = await db.external_skills.count_documents({})
    active_count = await db.skills.count_documents({"enabled": True}) + await db.external_skills.count_documents({"status": "active"})
    binding_count = await db.tool_agent_bindings.count_documents({"is_active": {"$ne": False}})
    
    return {
        "total": standard_count + external_count,
        "standard": standard_count,
        "external": external_count,
        "active": active_count,
        "bindings": binding_count
    }