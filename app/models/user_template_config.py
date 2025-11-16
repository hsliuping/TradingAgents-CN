"""
用户模板配置数据模型
"""

from datetime import datetime
from typing import Optional, Any, Annotated
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


class UserTemplateConfig(BaseModel):
    """用户模板配置模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="用户ID")
    agent_type: str = Field(..., description="Agent类型")
    agent_name: str = Field(..., description="Agent名称")
    template_id: PyObjectId = Field(..., description="模板ID")
    preference_id: Optional[PyObjectId] = Field(None, description="偏好ID")
    is_active: bool = Field(default=True, description="是否为当前生效配置")
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")
    
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class UserTemplateConfigCreate(BaseModel):
    """创建配置请求"""
    agent_type: str
    agent_name: str
    template_id: str
    preference_id: Optional[str] = None


class UserTemplateConfigUpdate(BaseModel):
    """更新配置请求"""
    template_id: Optional[str] = None
    preference_id: Optional[str] = None
    is_active: Optional[bool] = None


class UserTemplateConfigResponse(BaseModel):
    """配置响应"""
    id: str
    user_id: str
    agent_type: str
    agent_name: str
    template_id: str
    preference_id: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

