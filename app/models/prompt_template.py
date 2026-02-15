"""
提示词模板数据模型
"""

from datetime import datetime
from typing import Optional, Dict, Any, Annotated, List
from pydantic import BaseModel, Field, BeforeValidator, PlainSerializer, ConfigDict
from bson import ObjectId
from app.utils.timezone import now_tz


def validate_object_id(v: Any) -> ObjectId:
    """验证ObjectId"""
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str):
        if ObjectId.is_valid(v):
            return ObjectId(v)
    raise ValueError("Invalid ObjectId")


def serialize_object_id(v: ObjectId) -> str:
    """序列化ObjectId为字符串"""
    return str(v)


# 创建自定义ObjectId类型
PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(validate_object_id),
    PlainSerializer(serialize_object_id, return_type=str),
]


class TemplateContent(BaseModel):
    """模板内容"""
    system_prompt: str = Field(..., description="系统提示词")
    user_prompt: Optional[str] = Field(default="", description="用户提示词（支持变量替换）")
    tool_guidance: str = Field(..., description="工具使用指导")
    analysis_requirements: str = Field(..., description="分析要求")
    output_format: str = Field(..., description="输出格式")
    constraints: str = Field(default="", description="约束条件")  # 🔥 修改：设置默认值，允许为空


class PromptTemplate(BaseModel):
    """提示词模板模型

    支持流程专属提示词：
    - workflow_id 为 None 时，表示默认提示词（适用于所有流程）
    - workflow_id 有值时，表示特定流程的专属提示词

    加载优先级：
    1. 调试模板 (is_debug_mode=True)
    2. 流程专属模板 (workflow_id, agent_type, agent_name)
    3. 用户模板 (user_id, agent_type, agent_name)
    4. 系统默认模板 (agent_type, agent_name, workflow_id=None)
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    agent_type: str = Field(..., description="Agent类型: analysts, researchers, debators, managers, trader")
    agent_name: str = Field(..., description="具体Agent名称")
    template_name: str = Field(..., description="模板名称")

    # 🆕 流程专属提示词支持
    workflow_id: Optional[str] = Field(
        None,
        description="关联的工作流ID，None表示默认提示词（适用于所有流程）"
    )

    preference_type: Optional[str] = Field(None, description="偏好类型: aggressive, neutral, conservative")
    content: TemplateContent = Field(..., description="模板内容")
    remark: Optional[str] = Field(default="", description="备注信息")
    is_system: bool = Field(default=False, description="是否为系统模板")
    created_by: Optional[PyObjectId] = Field(None, description="创建者ID，系统模板为null")
    base_template_id: Optional[PyObjectId] = Field(None, description="来源系统模板ID")
    base_version: Optional[int] = Field(None, description="来源系统模板版本号")
    status: str = Field(default="active", description="模板状态: draft, active")
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")
    version: int = Field(default=1, description="当前版本号")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class PromptTemplateCreate(BaseModel):
    """创建模板请求"""
    agent_type: str
    agent_name: str
    template_name: str
    workflow_id: Optional[str] = None  # 🆕 流程专属提示词支持
    preference_type: Optional[str] = None
    content: TemplateContent
    remark: Optional[str] = ""
    status: str = "active"


class PromptTemplateUpdate(BaseModel):
    """更新模板请求"""
    template_name: Optional[str] = None
    workflow_id: Optional[str] = None  # 🆕 允许更新流程关联
    content: Optional[TemplateContent] = None
    remark: Optional[str] = None
    status: Optional[str] = None
    change_description: Optional[str] = None


class PromptTemplateResponse(BaseModel):
    """模板响应"""
    id: str
    agent_type: str
    agent_name: str
    template_name: str
    workflow_id: Optional[str] = None  # 🆕 流程专属提示词支持
    preference_type: Optional[str]
    content: TemplateContent
    remark: Optional[str]
    is_system: bool
    status: str
    version: int
    created_at: str
    updated_at: str

