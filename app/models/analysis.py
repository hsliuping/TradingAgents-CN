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


class AnalysisEngine(str, Enum):
    """分析引擎类型"""
    LEGACY = "legacy"       # 旧引擎: TradingAgentsGraph
    UNIFIED = "unified"     # 新引擎: UnifiedAnalysisService + WorkflowEngine
    V2 = "v2"               # v2.0引擎: 使用v2.0工作流模板


class AnalysisParameters(BaseModel):
    """分析参数模型

    研究深度说明：
    - 快速: 1级 - 快速分析 (2-4分钟)
    - 基础: 2级 - 基础分析 (4-6分钟)
    - 标准: 3级 - 标准分析 (6-10分钟，推荐)
    - 深度: 4级 - 深度分析 (10-15分钟)
    - 全面: 5级 - 全面分析 (15-25分钟)

    引擎选择 (AB 测试):
    - legacy: 使用旧引擎 TradingAgentsGraph (默认)
    - unified: 使用新的统一引擎 WorkflowEngine (LangGraph 动态构建)
    """
    market_type: str = "A股"
    analysis_date: Optional[datetime] = None
    research_depth: str = "标准"  # 默认使用3级标准分析（推荐）
    selected_analysts: List[str] = Field(default_factory=lambda: ["market", "fundamentals", "news", "social"])
    custom_prompt: Optional[str] = None
    include_sentiment: bool = True
    include_risk: bool = True
    language: str = "zh-CN"
    # 模型配置
    quick_analysis_model: Optional[str] = "qwen-turbo"
    deep_analysis_model: Optional[str] = "qwen-max"
    # AB 测试: 引擎选择
    engine: AnalysisEngine = Field(
        default=AnalysisEngine.LEGACY,
        description="分析引擎: legacy=旧引擎, unified=新统一引擎"
    )
    # 新引擎工作流配置
    workflow_id: Optional[str] = Field(
        default=None,
        description="工作流 ID (仅 unified 引擎有效)，不指定则使用系统默认工作流"
    )


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
