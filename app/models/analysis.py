"""
分析相关数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from enum import Enum
from bson import ObjectId
from .user import PyObjectId
from app.utils.timezone import now_tz


class AnalysisStatus(str, Enum):
    """分析状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchStatus(str, Enum):
    """批次状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisParameters(BaseModel):
    """分析参数模型（已移除分级深度概念，保留字段仅为兼容）"""
    market_type: str = "A股"
    analysis_date: Optional[datetime] = None
    # ⚠️ 兼容字段：前端已取消分级分析，本字段仅为兼容旧数据，不再驱动任何逻辑
    research_depth: Optional[str] = Field(default="不分级")
    selected_analysts: List[str] = Field(default_factory=list)
    custom_prompt: Optional[str] = None
    include_sentiment: bool = True
    include_risk: bool = True
    language: str = "zh-CN"
    # 模型配置
    quick_analysis_model: Optional[str] = "qwen-turbo"
    deep_analysis_model: Optional[str] = "qwen-max"

    # 阶段配置
    phase2_enabled: bool = False
    phase2_debate_rounds: int = 2
    phase3_enabled: bool = False
    phase3_debate_rounds: int = 2
    phase4_enabled: bool = False
    phase4_debate_rounds: int = 1

    # MCP工具
    mcp_enabled: bool = Field(default=False, description="是否启用 MCP 工具")
    mcp_tools: List[str] = Field(default_factory=list, description="兼容旧字段：MCP 工具ID列表")
    mcp_tool_ids: List[str] = Field(default_factory=list, description="MCP 工具ID列表（推荐字段）")


class AnalysisResult(BaseModel):
    """分析结果模型"""
    analysis_id: Optional[str] = None
    summary: Optional[str] = None
    recommendation: Optional[str] = None
    confidence_score: Optional[float] = None
    risk_level: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    detailed_analysis: Optional[Dict[str, Any]] = None
    charts: List[str] = Field(default_factory=list)
    tokens_used: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    model_info: Optional[str] = None  # 🔥 添加模型信息字段


class AnalysisTask(BaseModel):
    """分析任务模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    task_id: str = Field(..., description="任务唯一标识")
    batch_id: Optional[str] = None
    user_id: PyObjectId
    symbol: str = Field(..., description="6位股票代码")
    stock_code: Optional[str] = Field(None, description="股票代码(已废弃,使用symbol)")
    stock_name: Optional[str] = None
    status: AnalysisStatus = AnalysisStatus.PENDING

    progress: int = Field(default=0, ge=0, le=100, description="任务进度 0-100")

    # 时间戳
    created_at: datetime = Field(default_factory=now_tz)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 执行信息
    worker_id: Optional[str] = None
    parameters: AnalysisParameters = Field(default_factory=AnalysisParameters)
    result: Optional[AnalysisResult] = None
    
    # 重试机制
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class AnalysisBatch(BaseModel):
    """分析批次模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    batch_id: str = Field(..., description="批次唯一标识")
    user_id: PyObjectId
    title: str = Field(..., description="批次标题")
    description: Optional[str] = None
    status: BatchStatus = BatchStatus.PENDING
    
    # 任务统计
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    progress: int = Field(default=0, ge=0, le=100, description="整体进度 0-100")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 配置参数
    parameters: AnalysisParameters = Field(default_factory=AnalysisParameters)
    
    # 结果摘要
    results_summary: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class StockInfo(BaseModel):
    """股票信息模型"""
    symbol: str = Field(..., description="6位股票代码")
    code: Optional[str] = Field(None, description="股票代码(已废弃,使用symbol)")
    name: str = Field(..., description="股票名称")
    market: str = Field(..., description="市场类型")
    industry: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    price: Optional[float] = None
    change_percent: Optional[float] = None


# API请求/响应模型

class SingleAnalysisRequest(BaseModel):
    """单股分析请求"""
    symbol: Optional[str] = Field(None, description="6位股票代码")
    stock_code: Optional[str] = Field(None, description="股票代码(已废弃,使用symbol)")
    parameters: Optional[AnalysisParameters] = None

    def get_symbol(self) -> str:
        """获取股票代码(兼容旧字段)"""
        return self.symbol or self.stock_code or ""


class BatchAnalysisRequest(BaseModel):
    """批量分析请求"""
    title: str = Field(..., description="批次标题")
    description: Optional[str] = None
    symbols: Optional[List[str]] = Field(None, min_items=1, max_items=10, description="股票代码列表（最多10个）")
    stock_codes: Optional[List[str]] = Field(None, min_items=1, max_items=10, description="股票代码列表(已废弃,使用symbols，最多10个)")
    parameters: Optional[AnalysisParameters] = None

    def get_symbols(self) -> List[str]:
        """获取股票代码列表(兼容旧字段)"""
        return self.symbols or self.stock_codes or []


class AnalysisTaskResponse(BaseModel):
    """分析任务响应"""
    task_id: str
    batch_id: Optional[str]
    symbol: str
    stock_code: Optional[str] = None  # 兼容字段
    stock_name: Optional[str]
    status: AnalysisStatus
    progress: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[AnalysisResult]

    @field_serializer('created_at', 'started_at', 'completed_at')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        """序列化 datetime 为 ISO 8601 格式，保留时区信息"""
        if dt:
            return dt.isoformat()
        return None


class AnalysisBatchResponse(BaseModel):
    """分析批次响应"""
    batch_id: str
    title: str
    description: Optional[str]
    status: BatchStatus
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    progress: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    parameters: AnalysisParameters

    @field_serializer('created_at', 'started_at', 'completed_at')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        """序列化 datetime 为 ISO 8601 格式，保留时区信息"""
        if dt:
            return dt.isoformat()
        return None


class AnalysisHistoryQuery(BaseModel):
    """分析历史查询参数"""
    status: Optional[AnalysisStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    symbol: Optional[str] = None
    stock_code: Optional[str] = None  # 兼容字段
    batch_id: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    def get_symbol(self) -> Optional[str]:
        """获取股票代码(兼容旧字段)"""
        return self.symbol or self.stock_code
