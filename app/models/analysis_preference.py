"""
分析偏好数据模型
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


class AnalysisPreference(BaseModel):
    """分析偏好模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId = Field(..., description="用户ID")
    preference_type: str = Field(..., description="偏好类型: aggressive, neutral, conservative")
    risk_level: float = Field(default=0.5, ge=0.0, le=1.0, description="风险等级 0.0-1.0")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="置信度阈值 0.0-1.0")
    position_size_multiplier: float = Field(default=1.0, ge=0.5, le=2.0, description="仓位倍数 0.5-2.0")
    decision_speed: str = Field(default="normal", description="决策速度: fast, normal, slow")
    is_default: bool = Field(default=False, description="是否为默认偏好")
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")
    
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class AnalysisPreferenceCreate(BaseModel):
    """创建偏好请求"""
    preference_type: str
    risk_level: float = 0.5
    confidence_threshold: float = 0.7
    position_size_multiplier: float = 1.0
    decision_speed: str = "normal"
    is_default: bool = False


class AnalysisPreferenceUpdate(BaseModel):
    """更新偏好请求"""
    risk_level: Optional[float] = None
    confidence_threshold: Optional[float] = None
    position_size_multiplier: Optional[float] = None
    decision_speed: Optional[str] = None
    is_default: Optional[bool] = None


class AnalysisPreferenceResponse(BaseModel):
    """偏好响应"""
    id: str
    user_id: str
    preference_type: str
    risk_level: float
    confidence_threshold: float
    position_size_multiplier: float
    decision_speed: str
    is_default: bool
    created_at: str
    updated_at: str

