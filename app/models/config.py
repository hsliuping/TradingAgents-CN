"""
系统配置相关数据模型
"""

from datetime import datetime, timezone
from app.utils.timezone import now_tz
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from enum import Enum
from bson import ObjectId
from .user import PyObjectId


class ModelProvider(str, Enum):
    """大模型提供商枚举"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ZHIPU = "zhipu"
    QWEN = "qwen"
    BAIDU = "baidu"
    TENCENT = "tencent"
    GEMINI = "gemini"
    GLM = "glm"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    DASHSCOPE = "dashscope"
    GOOGLE = "google"
    SILICONFLOW = "siliconflow"
    OPENROUTER = "openrouter"
    CUSTOM_OPENAI = "custom_openai"
    QIANFAN = "qianfan"
    LOCAL = "local"

    # 🆕 聚合渠道
    AI302 = "302ai"              # 302.AI
    ONEAPI = "oneapi"            # One API
    NEWAPI = "newapi"            # New API
    FASTGPT = "fastgpt"          # FastGPT
    CUSTOM_AGGREGATOR = "custom_aggregator"  # 自定义聚合渠道


class LLMProvider(BaseModel):
    """大模型厂家配置"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str = Field(..., description="厂家唯一标识")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="厂家描述")
    website: Optional[str] = Field(None, description="官网地址")
    api_doc_url: Optional[str] = Field(None, description="API文档地址")
    logo_url: Optional[str] = Field(None, description="Logo地址")
    is_active: bool = Field(True, description="是否启用")
    supported_features: List[str] = Field(default_factory=list, description="支持的功能")
    default_base_url: Optional[str] = Field(None, description="默认API地址")
    api_key: Optional[str] = Field(None, description="API密钥")
    api_secret: Optional[str] = Field(None, description="API密钥（某些厂家需要）")
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="额外配置参数")

    # 🆕 聚合渠道支持
    is_aggregator: bool = Field(default=False, description="是否为聚合渠道（如302.AI、OpenRouter）")
    aggregator_type: Optional[str] = Field(None, description="聚合渠道类型（openai_compatible/custom）")
    model_name_format: Optional[str] = Field(None, description="模型名称格式（如：{provider}/{model}）")

    created_at: Optional[datetime] = Field(default_factory=now_tz)
    updated_at: Optional[datetime] = Field(default_factory=now_tz)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class ModelInfo(BaseModel):
    """模型信息"""
    name: str = Field(..., description="模型标识名称")
    display_name: str = Field(..., description="模型显示名称")
    description: Optional[str] = Field(None, description="模型描述")
    context_length: Optional[int] = Field(None, description="上下文长度")
    max_tokens: Optional[int] = Field(None, description="最大输出token数")
    input_price_per_1k: Optional[float] = Field(None, description="输入价格(每1K tokens)")
    output_price_per_1k: Optional[float] = Field(None, description="输出价格(每1K tokens)")
    currency: str = Field(default="CNY", description="货币单位")
    is_deprecated: bool = Field(default=False, description="是否已废弃")
    release_date: Optional[str] = Field(None, description="发布日期")
    capabilities: List[str] = Field(default_factory=list, description="能力标签(如: vision, function_calling)")

    # 🆕 聚合渠道模型映射支持
    original_provider: Optional[str] = Field(None, description="原厂商标识（用于聚合渠道）")
    original_model: Optional[str] = Field(None, description="原厂商模型名（用于能力映射）")


class ModelCatalog(BaseModel):
    """模型目录"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    provider: str = Field(..., description="厂家标识")
    provider_name: str = Field(..., description="厂家显示名称")
    models: List[ModelInfo] = Field(default_factory=list, description="模型列表")
    created_at: Optional[datetime] = Field(default_factory=now_tz)
    updated_at: Optional[datetime] = Field(default_factory=now_tz)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class LLMProviderRequest(BaseModel):
    """大模型厂家请求"""
    name: str = Field(..., description="厂家唯一标识")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="厂家描述")
    website: Optional[str] = Field(None, description="官网地址")
    api_doc_url: Optional[str] = Field(None, description="API文档地址")
    logo_url: Optional[str] = Field(None, description="Logo地址")
    is_active: bool = Field(True, description="是否启用")
    supported_features: List[str] = Field(default_factory=list, description="支持的功能")
    default_base_url: Optional[str] = Field(None, description="默认API地址")
    api_key: Optional[str] = Field(None, description="API密钥")
    api_secret: Optional[str] = Field(None, description="API密钥（某些厂家需要）")
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="额外配置参数")

    # 🆕 聚合渠道支持
    is_aggregator: bool = Field(default=False, description="是否为聚合渠道")
    aggregator_type: Optional[str] = Field(None, description="聚合渠道类型")
    model_name_format: Optional[str] = Field(None, description="模型名称格式")


class LLMProviderResponse(BaseModel):
    """大模型厂家响应"""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    website: Optional[str] = None
    api_doc_url: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool
    supported_features: List[str]
    default_base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    extra_config: Dict[str, Any] = Field(default_factory=dict)

    # 🆕 聚合渠道支持
    is_aggregator: bool = False
    aggregator_type: Optional[str] = None
    model_name_format: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DataSourceType(str, Enum):
    """
    数据源类型枚举

    注意：这个枚举与 tradingagents.constants.DataSourceCode 保持同步
    添加新数据源时，请先在 tradingagents/constants/data_sources.py 中注册
    """
    # 缓存数据源
    MONGODB = "mongodb"

    # 中国市场数据源
    TUSHARE = "tushare"
    AKSHARE = "akshare"
    BAOSTOCK = "baostock"

    # 美股数据源
    FINNHUB = "finnhub"
    YAHOO_FINANCE = "yahoo_finance"
    ALPHA_VANTAGE = "alpha_vantage"
    IEX_CLOUD = "iex_cloud"

    # 专业数据源
    WIND = "wind"
    CHOICE = "choice"

    # 其他数据源
    QUANDL = "quandl"
    LOCAL_FILE = "local_file"
    CUSTOM = "custom"


class DatabaseType(str, Enum):
    """数据库类型枚举"""
    MONGODB = "mongodb"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    REDIS = "redis"
    SQLITE = "sqlite"


class LLMConfig(BaseModel):
    """大模型配置"""
    provider: str = Field(default="openai", description="供应商标识（支持动态添加）")
    model_name: str = Field(..., description="模型名称/代码")
    model_display_name: Optional[str] = Field(None, description="模型显示名称")
    api_key: Optional[str] = Field(None, description="API密钥(可选，优先从厂家配置获取)")
    api_base: Optional[str] = Field(None, description="API基础URL")
    max_tokens: int = Field(default=4000, description="最大token数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    timeout: int = Field(default=180, description="请求超时时间(秒)")
    retry_times: int = Field(default=3, description="重试次数")
    enabled: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(None, description="配置描述")

    # 新增字段 - 来自sidebar.py的配置项
    model_category: Optional[str] = Field(None, description="模型类别(用于OpenRouter等)")
    custom_endpoint: Optional[str] = Field(None, description="自定义端点URL")
    enable_memory: bool = Field(default=False, description="启用记忆功能")
    enable_debug: bool = Field(default=False, description="启用调试模式")
    priority: int = Field(default=0, description="优先级")

    # 定价配置
    input_price_per_1k: Optional[float] = Field(None, description="输入token价格(每1000个token)")
    output_price_per_1k: Optional[float] = Field(None, description="输出token价格(每1000个token)")
    currency: str = Field(default="CNY", description="货币单位(CNY/USD/EUR)")

    # 🆕 模型能力分级系统
    capability_level: int = Field(
        default=2,
        ge=1,
        le=5,
        description="模型能力等级(1-5): 1=基础, 2=标准, 3=高级, 4=专业, 5=旗舰"
    )
    suitable_roles: List[str] = Field(
        default_factory=lambda: ["both"],
        description="适用角色: quick_analysis(快速分析), deep_analysis(深度分析), both(两者都适合)"
    )
    features: List[str] = Field(
        default_factory=list,
        description="模型特性: tool_calling(工具调用), long_context(长上下文), reasoning(推理), vision(视觉), fast_response(快速), cost_effective(经济)"
    )
    recommended_depths: List[str] = Field(
        default_factory=lambda: ["快速", "基础", "标准"],
        description="推荐的分析深度级别"
    )
    performance_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="性能指标: speed(速度1-5), cost(成本1-5), quality(质量1-5)"
    )


class DataSourceConfig(BaseModel):
    """数据源配置"""
    name: str = Field(..., description="数据源名称")
    type: DataSourceType = Field(..., description="数据源类型")
    api_key: Optional[str] = Field(None, description="API密钥")
    api_secret: Optional[str] = Field(None, description="API密钥")
    endpoint: Optional[str] = Field(None, description="API端点")
    timeout: int = Field(default=30, description="请求超时时间(秒)")
    rate_limit: int = Field(default=100, description="每分钟请求限制")
    enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=0, description="优先级，数字越大优先级越高")
    config_params: Dict[str, Any] = Field(default_factory=dict, description="额外配置参数")
    description: Optional[str] = Field(None, description="配置描述")
    # 新增字段：支持市场分类
    market_categories: Optional[List[str]] = Field(default_factory=list, description="所属市场分类列表")
    display_name: Optional[str] = Field(None, description="显示名称")
    provider: Optional[str] = Field(None, description="数据提供商")
    created_at: Optional[datetime] = Field(default_factory=now_tz, description="创建时间")
    updated_at: Optional[datetime] = Field(default_factory=now_tz, description="更新时间")


class DatabaseConfig(BaseModel):
    """数据库配置"""
    name: str = Field(..., description="数据库名称")
    type: DatabaseType = Field(..., description="数据库类型")
    host: str = Field(..., description="主机地址")
    port: int = Field(..., description="端口号")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    database: Optional[str] = Field(None, description="数据库名")
    connection_params: Dict[str, Any] = Field(default_factory=dict, description="连接参数")
    pool_size: int = Field(default=10, description="连接池大小")
    max_overflow: int = Field(default=20, description="最大溢出连接数")
    enabled: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(None, description="配置描述")


class MarketCategory(BaseModel):
    """市场分类配置"""
    id: str = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="分类描述")
    enabled: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=1, description="排序顺序")
    created_at: Optional[datetime] = Field(default_factory=now_tz, description="创建时间")
    updated_at: Optional[datetime] = Field(default_factory=now_tz, description="更新时间")


class DataSourceGrouping(BaseModel):
    """数据源分组关系"""
    data_source_name: str = Field(..., description="数据源名称")
    market_category_id: str = Field(..., description="市场分类ID")
    priority: int = Field(default=0, description="在该分类中的优先级")
    enabled: bool = Field(default=True, description="是否启用")
    created_at: Optional[datetime] = Field(default_factory=now_tz, description="创建时间")
    updated_at: Optional[datetime] = Field(default_factory=now_tz, description="更新时间")


class UsageRecord(BaseModel):
    """使用记录"""
    id: Optional[str] = Field(None, description="记录ID")
    timestamp: str = Field(..., description="时间戳")
    provider: str = Field(..., description="供应商")
    model_name: str = Field(..., description="模型名称")
    input_tokens: int = Field(..., description="输入token数")
    output_tokens: int = Field(..., description="输出token数")
    cost: float = Field(..., description="成本")
    currency: str = Field(default="CNY", description="货币单位")
    session_id: str = Field(..., description="会话ID")
    analysis_type: str = Field(default="stock_analysis", description="分析类型")
    stock_code: Optional[str] = Field(None, description="股票代码")


class UsageStatistics(BaseModel):
    """使用统计"""
    total_requests: int = Field(default=0, description="总请求数")
    total_input_tokens: int = Field(default=0, description="总输入token数")
    total_output_tokens: int = Field(default=0, description="总输出token数")
    total_cost: float = Field(default=0.0, description="总成本（已废弃，使用 cost_by_currency）")
    cost_by_currency: Dict[str, float] = Field(default_factory=dict, description="按货币统计的成本")
    by_provider: Dict[str, Any] = Field(default_factory=dict, description="按供应商统计")
    by_model: Dict[str, Any] = Field(default_factory=dict, description="按模型统计")
    by_date: Dict[str, Any] = Field(default_factory=dict, description="按日期统计")


class SystemConfig(BaseModel):
    """系统配置模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    config_name: str = Field(..., description="配置名称")
    config_type: str = Field(..., description="配置类型")
    
    # 大模型配置
    llm_configs: List[LLMConfig] = Field(default_factory=list, description="大模型配置列表")
    default_llm: Optional[str] = Field(None, description="默认大模型")
    
    # 数据源配置
    data_source_configs: List[DataSourceConfig] = Field(default_factory=list, description="数据源配置列表")
    default_data_source: Optional[str] = Field(None, description="默认数据源")
    
    # 数据库配置
    database_configs: List[DatabaseConfig] = Field(default_factory=list, description="数据库配置列表")
    
    # 系统设置
    system_settings: Dict[str, Any] = Field(default_factory=dict, description="系统设置")
    
    # 元数据
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)
    created_by: Optional[PyObjectId] = Field(None, description="创建者")
    updated_by: Optional[PyObjectId] = Field(None, description="更新者")
    version: int = Field(default=1, description="配置版本")
    is_active: bool = Field(default=True, description="是否激活")
    
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


# API请求/响应模型

class LLMConfigRequest(BaseModel):
    """大模型配置请求"""
    provider: str = Field(..., description="供应商标识（支持动态添加）")
    model_name: str
    model_display_name: Optional[str] = None  # 新增：模型显示名称
    api_key: Optional[str] = None  # 可选，优先从厂家配置获取
    api_base: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 180  # 默认超时时间改为180秒
    retry_times: int = 3
    enabled: bool = True
    description: Optional[str] = None

    # 新增字段以匹配前端
    enable_memory: bool = False
    enable_debug: bool = False
    priority: int = 0
    model_category: Optional[str] = None

    # 定价配置
    input_price_per_1k: Optional[float] = None
    output_price_per_1k: Optional[float] = None
    currency: str = "CNY"

    # 🆕 模型能力分级系统
    capability_level: int = Field(default=2, ge=1, le=5)
    suitable_roles: List[str] = Field(default_factory=lambda: ["both"])
    features: List[str] = Field(default_factory=list)
    recommended_depths: List[str] = Field(default_factory=lambda: ["快速", "基础", "标准"])
    performance_metrics: Optional[Dict[str, Any]] = None


class DataSourceConfigRequest(BaseModel):
    """数据源配置请求"""
    name: str
    type: DataSourceType
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    endpoint: Optional[str] = None
    timeout: int = 30
    rate_limit: int = 100
    enabled: bool = True
    priority: int = 0
    config_params: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    # 新增字段
    market_categories: Optional[List[str]] = Field(default_factory=list)
    display_name: Optional[str] = None
    provider: Optional[str] = None


class MarketCategoryRequest(BaseModel):
    """市场分类请求"""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    enabled: bool = True
    sort_order: int = 1


class DataSourceGroupingRequest(BaseModel):
    """数据源分组请求"""
    data_source_name: str
    market_category_id: str
    priority: int = 0
    enabled: bool = True


class DataSourceOrderRequest(BaseModel):
    """数据源排序请求"""
    data_sources: List[Dict[str, Any]] = Field(..., description="排序后的数据源列表")


class DatabaseConfigRequest(BaseModel):
    """数据库配置请求"""
    name: str
    type: DatabaseType
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    connection_params: Dict[str, Any] = Field(default_factory=dict)
    pool_size: int = 10
    max_overflow: int = 20
    enabled: bool = True
    description: Optional[str] = None


class SystemConfigResponse(BaseModel):
    """系统配置响应"""
    config_name: str
    config_type: str
    llm_configs: List[LLMConfig]
    default_llm: Optional[str]
    data_source_configs: List[DataSourceConfig]
    default_data_source: Optional[str]
    database_configs: List[DatabaseConfig]
    system_settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    version: int
    is_active: bool

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        """序列化 datetime 为 ISO 8601 格式，保留时区信息"""
        if dt:
            return dt.isoformat()
        return None


class ConfigTestRequest(BaseModel):
    """配置测试请求"""
    config_type: str = Field(..., description="配置类型: llm/datasource/database")
    config_data: Dict[str, Any] = Field(..., description="配置数据")


class ConfigTestResponse(BaseModel):
    """配置测试响应"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    response_time: Optional[float] = None
