"""
行业/个股分析配置数据模型

用于上下文感知提示词注入：
- IndustryAnalysisProfile: 行业级分析维度（如银行关注NIM、不良率）
- StockAnalysisProfile: 个股级分析维度（如比亚迪关注月销量、DM-i占比）
"""

from datetime import datetime
from typing import Optional, List, Any, Annotated
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


PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(validate_object_id),
    PlainSerializer(serialize_object_id, return_type=str),
]


class AnalysisDimension(BaseModel):
    """分析维度"""
    name: str = Field(..., description="维度名称，如'净息差(NIM)'")
    description: str = Field(..., description="维度说明，如'银行核心盈利能力指标'")
    importance: str = Field(default="high", description="重要性: critical, high, medium, low")
    data_source: str = Field(default="fundamentals", description="数据来源: fundamentals, news, technical, mixed")


class IndustryAnalysisProfile(BaseModel):
    """行业分析配置"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    industry: str = Field(..., description="行业名称（与 stock_basic_info 的 industry 字段对齐）")
    display_name: str = Field(default="", description="行业显示名称")
    analysis_dimensions: List[AnalysisDimension] = Field(default_factory=list, description="行业核心分析维度")
    analysis_focus: str = Field(default="", description="行业分析重点说明")
    key_metrics: List[str] = Field(default_factory=list, description="关键指标列表")
    comparable_companies: List[str] = Field(default_factory=list, description="行业内可比公司")
    source: str = Field(default="system", description="来源: system, ai_generated, user")
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class StockAnalysisProfile(BaseModel):
    """个股分析配置（覆盖行业默认配置）"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    stock_symbol: str = Field(..., description="股票代码，如 002594.SZ")
    company_name: str = Field(default="", description="公司名称")
    industry: str = Field(default="", description="所属行业")
    analysis_dimensions: List[AnalysisDimension] = Field(default_factory=list, description="个股专属分析维度")
    special_notes: str = Field(default="", description="个股特殊说明")
    source: str = Field(default="user", description="来源: system, ai_generated, user")
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


# === Request/Response 模型 ===

class AnalysisDimensionCreate(BaseModel):
    """创建分析维度请求"""
    name: str
    description: str
    importance: str = "high"
    data_source: str = "fundamentals"


class IndustryProfileCreate(BaseModel):
    """创建行业配置请求"""
    industry: str
    display_name: str = ""
    analysis_dimensions: List[AnalysisDimensionCreate] = []
    analysis_focus: str = ""
    key_metrics: List[str] = []
    comparable_companies: List[str] = []
    source: str = "user"


class IndustryProfileUpdate(BaseModel):
    """更新行业配置请求"""
    display_name: Optional[str] = None
    analysis_dimensions: Optional[List[AnalysisDimensionCreate]] = None
    analysis_focus: Optional[str] = None
    key_metrics: Optional[List[str]] = None
    comparable_companies: Optional[List[str]] = None
    is_active: Optional[bool] = None


class StockProfileCreate(BaseModel):
    """创建个股配置请求"""
    stock_symbol: str
    company_name: str = ""
    industry: str = ""
    analysis_dimensions: List[AnalysisDimensionCreate] = []
    special_notes: str = ""
    source: str = "user"


class StockProfileUpdate(BaseModel):
    """更新个股配置请求"""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    analysis_dimensions: Optional[List[AnalysisDimensionCreate]] = None
    special_notes: Optional[str] = None
    is_active: Optional[bool] = None


class IndustryProfileResponse(BaseModel):
    """行业配置响应"""
    id: str
    industry: str
    display_name: str
    analysis_dimensions: List[AnalysisDimension]
    analysis_focus: str
    key_metrics: List[str]
    comparable_companies: List[str]
    source: str
    is_active: bool
    created_at: str
    updated_at: str


class StockProfileResponse(BaseModel):
    """个股配置响应"""
    id: str
    stock_symbol: str
    company_name: str
    industry: str
    analysis_dimensions: List[AnalysisDimension]
    special_notes: str
    source: str
    is_active: bool
    created_at: str
    updated_at: str

