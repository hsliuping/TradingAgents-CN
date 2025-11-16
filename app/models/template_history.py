"""
模板历史记录数据模型
"""

from datetime import datetime
from typing import Optional, Dict, Any, Annotated
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


class TemplateHistory(BaseModel):
    """模板历史记录模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    template_id: PyObjectId = Field(..., description="模板ID")
    user_id: Optional[PyObjectId] = Field(None, description="用户ID，系统模板为null")
    version: int = Field(..., description="版本号")
    content: Dict[str, str] = Field(..., description="模板内容快照")
    change_description: Optional[str] = Field(None, description="变更描述")
    change_type: str = Field(..., description="变更类型: create, update, delete, restore")
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class TemplateHistoryCreate(BaseModel):
    """创建历史记录请求"""
    template_id: str
    version: int
    content: Dict[str, str]
    change_description: Optional[str] = None
    change_type: str = "update"


class TemplateHistoryResponse(BaseModel):
    """历史记录响应"""
    id: str
    template_id: str
    user_id: Optional[str]
    version: int
    content: Dict[str, str]
    change_description: Optional[str]
    change_type: str
    created_at: str

