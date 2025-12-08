"""
工作流 API 路由

提供工作流的 CRUD 和执行端点
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from app.core.response import ok, fail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ==================== 数据模型 ====================

class Position(BaseModel):
    """节点位置"""
    x: float
    y: float


class NodeDefinition(BaseModel):
    """节点定义"""
    id: str
    type: str
    agent_id: Optional[str] = None
    label: str
    position: Position
    config: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None


class EdgeDefinition(BaseModel):
    """边定义"""
    id: str
    source: str
    target: str
    type: str = "normal"
    condition: Optional[str] = None
    label: Optional[str] = None
    animated: bool = False


class WorkflowCreate(BaseModel):
    """创建工作流请求"""
    id: Optional[str] = None  # 可选，验证时可传入
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    version: str = "1.0.0"
    nodes: List[NodeDefinition] = Field(default_factory=list)
    edges: List[EdgeDefinition] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_template: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkflowUpdate(BaseModel):
    """更新工作流请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    nodes: Optional[List[NodeDefinition]] = None
    edges: Optional[List[EdgeDefinition]] = None
    tags: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class WorkflowExecuteRequest(BaseModel):
    """执行工作流请求"""
    ticker: str = Field(..., min_length=1)
    analysis_date: Optional[datetime] = None
    research_depth: str = Field(default="标准", description="分析深度：快速/基础/标准/深度/全面")
    quick_analysis_model: Optional[str] = Field(default=None, description="快速分析模型")
    deep_analysis_model: Optional[str] = Field(default=None, description="深度分析模型")
    lookback_days: int = Field(default=30, ge=1, le=365)
    max_debate_rounds: int = Field(default=3, ge=1, le=10)


class ValidationResult(BaseModel):
    """验证结果"""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


# ==================== API 端点 ====================

@router.get("")
async def list_workflows():
    """获取所有工作流列表"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        workflows = api.list_all()
        return ok(workflows)
    except Exception as e:
        logger.error(f"获取工作流列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def get_templates():
    """获取预定义模板"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        templates = api.get_templates()
        return ok(templates)
    except Exception as e:
        logger.error(f"获取模板失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """获取单个工作流详情"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        workflow = api.get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="工作流不存在")
        return ok(workflow)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_workflow(data: WorkflowCreate):
    """创建新工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        result = api.create(data.model_dump())

        if not result.get("success"):
            return fail(
                message="创建工作流失败",
                code=400,
                data={"errors": result.get("errors", ["创建失败"])}
            )

        return ok(result.get("workflow"), message="创建成功")
    except Exception as e:
        logger.error(f"创建工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, data: WorkflowUpdate):
    """更新工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 过滤掉 None 值
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        result = api.update(workflow_id, update_data)

        if not result.get("success"):
            error = result.get("error") or result.get("errors", ["更新失败"])
            return fail(message=str(error), code=400)

        return ok(result.get("workflow"), message="更新成功")
    except Exception as e:
        logger.error(f"更新工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """删除工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        result = api.delete(workflow_id)

        if not result.get("success"):
            return fail(message=result.get("error", "删除失败"), code=400)

        return ok(None, message="删除成功")
    except Exception as e:
        logger.error(f"删除工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_workflow(data: WorkflowCreate):
    """验证工作流定义"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        result = api.validate(data.model_dump())
        return ok(result)
    except Exception as e:
        logger.error(f"验证工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    data: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks
):
    """执行工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 构建输入参数
        inputs = {
            "ticker": data.ticker,
            "analysis_date": data.analysis_date.isoformat() if data.analysis_date else None,
            "research_depth": data.research_depth,
            "quick_analysis_model": data.quick_analysis_model,
            "deep_analysis_model": data.deep_analysis_model,
            "lookback_days": data.lookback_days,
            "max_debate_rounds": data.max_debate_rounds
        }

        # 执行工作流
        result = api.execute(workflow_id, inputs)

        if not result.get("success"):
            return fail(message=result.get("error", "执行失败"), code=400)

        return ok(result, message="执行完成")
    except Exception as e:
        logger.error(f"执行工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CreateFromTemplateRequest(BaseModel):
    """从模板创建请求"""
    template_id: str
    name: str


@router.post("/from-template")
async def create_from_template(data: CreateFromTemplateRequest):
    """从模板创建工作流"""
    template_id = data.template_id
    name = data.name
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 获取模板
        templates = api.get_templates()
        template = next((t for t in templates if t.get("id") == template_id), None)

        if template is None:
            raise HTTPException(status_code=404, detail="模板不存在")

        # 创建新工作流
        new_workflow = {
            **template,
            "name": name,
            "is_template": False
        }
        # 移除原 ID，让系统生成新 ID
        new_workflow.pop("id", None)
        new_workflow.pop("created_at", None)
        new_workflow.pop("updated_at", None)

        result = api.create(new_workflow)

        if not result.get("success"):
            return fail(
                message="从模板创建失败",
                code=400,
                data={"errors": result.get("errors", ["创建失败"])}
            )

        return ok(result.get("workflow"), message="创建成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从模板创建工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DuplicateRequest(BaseModel):
    """复制工作流请求"""
    name: str


@router.post("/{workflow_id}/duplicate")
async def duplicate_workflow(workflow_id: str, data: DuplicateRequest):
    """复制工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 获取原工作流
        workflow = api.get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="工作流不存在")

        # 创建副本
        new_workflow = {
            **workflow,
            "name": data.name,
            "is_template": False,
        }
        # 移除原 ID，让系统生成新 ID
        new_workflow.pop("id", None)
        new_workflow.pop("created_at", None)
        new_workflow.pop("updated_at", None)

        result = api.create(new_workflow)

        if not result.get("success"):
            return fail(
                message="复制失败",
                code=400,
                data={"errors": result.get("errors", ["复制失败"])}
            )

        return ok(result.get("workflow"), message="复制成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"复制工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/set-default")
async def set_as_default(workflow_id: str):
    """设为默认分析流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 获取工作流
        workflow = api.get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="工作流不存在")

        # 保存为默认分析流配置
        # 这里将默认工作流ID保存到配置文件
        import json
        from pathlib import Path

        config_path = Path("config/settings.json")
        config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

        config["default_workflow_id"] = workflow_id
        config["default_workflow_name"] = workflow.get("name", "")

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return ok(message=f"已将 '{workflow.get('name')}' 设为默认分析流")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置默认分析流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

