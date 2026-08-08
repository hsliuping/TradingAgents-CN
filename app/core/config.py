from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os
import sys
import warnings

# Legacy env var aliases (deprecated): map API_HOST/PORT/DEBUG -> HOST/PORT/DEBUG
_LEGACY_ENV_ALIASES = {
    "API_HOST": "HOST",
    "API_PORT": "PORT",
    "API_DEBUG": "DEBUG",
}
for _legacy, _new in _LEGACY_ENV_ALIASES.items():
    if _new not in os.environ and _legacy in os.environ:
        os.environ[_new] = os.environ[_legacy]
        warnings.warn(
            f"Environment variable {_legacy} is deprecated; use {_new} instead.",
            DeprecationWarning,
            stacklevel=2,
        )

class Settings(BaseSettings):
    # 基础配置
    DEBUG: bool = Field(default=True)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
    )
    ALLOWED_HOSTS: List[str] = Field(default_factory=lambda: ["*"])

    # MongoDB配置
    MONGODB_HOST: str = Field(default="localhost")
    MONGODB_PORT: int = Field(default=27017)
    MONGODB_USERNAME: str = Field(default="")
    MONGODB_PASSWORD: str = Field(default="")
    MONGODB_DATABASE: str = Field(default="tradingagents")
    MONGODB_AUTH_SOURCE: str = Field(default="admin")
    MONGO_MAX_CONNECTIONS: int = Field(default=100)
    MONGO_MIN_CONNECTIONS: int = Field(default=10)
    # MongoDB超时参数（毫秒）- 用于处理大量历史数据
    MONGO_CONNECT_TIMEOUT_MS: int = Field(default=30000)  # 连接超时：30秒（原为10秒）
    MONGO_SOCKET_TIMEOUT_MS: int = Field(default=60000)   # 套接字超时：60秒（原为20秒）
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = Field(default=5000)  # 服务器选择超时：5秒

    @property
    def MONGO_URI(self) -> str:
        """构建MongoDB URI"""
        if self.MONGODB_USERNAME and self.MONGODB_PASSWORD:
            return f"mongodb://{self.MONGODB_USERNAME}:{self.MONGODB_PASSWORD}@{self.MONGODB_HOST}:{self.MONGODB_PORT}/{self.MONGODB_DATABASE}?authSource={self.MONGODB_AUTH_SOURCE}"
        else:
            return f"mongodb://{self.MONGODB_HOST}:{self.MONGODB_PORT}/{self.MONGODB_DATABASE}"

    @property
    def MONGO_DB(self) -> str:
        """获取数据库名称"""
        return self.MONGODB_DATABASE

    # Redis配置
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(default="")
    REDIS_DB: int = Field(default=0)
    REDIS_MAX_CONNECTIONS: int = Field(default=20)
    REDIS_RETRY_ON_TIMEOUT: bool = Field(default=True)

    @property
    def REDIS_URL(self) -> str:
        """构建Redis URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # JWT配置
    JWT_SECRET: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)

    # 队列配置
    QUEUE_MAX_SIZE: int = Field(default=10000)
    QUEUE_VISIBILITY_TIMEOUT: int = Field(default=300)  # 5分钟
    QUEUE_MAX_RETRIES: int = Field(default=3)
    WORKER_HEARTBEAT_INTERVAL: int = Field(default=30)  # 30秒


    # 队列轮询/清理间隔（秒）
    QUEUE_POLL_INTERVAL_SECONDS: float = Field(default=1.0)
    QUEUE_CLEANUP_INTERVAL_SECONDS: float = Field(default=60.0)

    # 并发控制
    DEFAULT_USER_CONCURRENT_LIMIT: int = Field(default=3)
    GLOBAL_CONCURRENT_LIMIT: int = Field(default=50)
    DEFAULT_DAILY_QUOTA: int = Field(default=1000)

    # 速率限制
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    DEFAULT_RATE_LIMIT: int = Field(default=100)  # 每分钟请求数

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG_FILE: str = Field(default="logs/tradingagents.log")

    # 代理配置
    # 用于配置需要绕过代理的域名（国内数据源）
    # 多个域名用逗号分隔
    # ⚠️ Windows 不支持通配符 *，必须使用完整域名
    # 详细说明: docs/proxy_configuration.md
    PROXY_ENABLED: bool = Field(default=False)  # 代理总开关，默认关闭
    HTTP_PROXY: str = Field(default="")
    HTTPS_PROXY: str = Field(default="")
    NO_PROXY: str = Field(
        default="localhost,127.0.0.1,eastmoney.com,push2.eastmoney.com,82.push2.eastmoney.com,82.push2delay.eastmoney.com,gtimg.cn,sinaimg.cn,api.tushare.pro,baostock.com"
    )

    # 文件上传配置
    MAX_UPLOAD_SIZE: int = Field(default=10 * 1024 * 1024)  # 10MB
    UPLOAD_DIR: str = Field(default="uploads")

    # 缓存配置
    CACHE_TTL: int = Field(default=3600)  # 1小时
    SCREENING_CACHE_TTL: int = Field(default=1800)  # 30分钟

    # 安全配置
    BCRYPT_ROUNDS: int = Field(default=12)
    SESSION_EXPIRE_HOURS: int = Field(default=24)
    CSRF_SECRET: str = Field(default="change-me-csrf-secret")

    # 外部服务配置
    STOCK_DATA_API_URL: str = Field(default="")
    STOCK_DATA_API_KEY: str = Field(default="")

    # 更新检查服务配置
    # 检查更新和下载更新包的 API 基础地址，留空则使用默认官网
    # 用于测试时可配置为测试域名，例如: https://test.example.com/api
    UPDATE_CHECK_BASE_URL: str = Field(
        default="https://www.tradingagentscn.com/api",
        description="Update check API base URL (empty = use default)"
    )
    UPDATE_CHECK_CHANNEL: str = Field(
        default="stable",
        description="Update release channel: stable or test"
    )

    # 授权服务配置 (TradingAgents Account Service)
    # ⚠️ 注意：LICENSE_SERVICE_URL 已移除，验证服务器地址在 core/licensing/validator.py 中硬编码
    # 这样可以防止用户通过修改环境变量搭建假服务器绕过许可证验证
    LICENSE_SERVICE_TIMEOUT: int = Field(default=10, description="授权服务请求超时(秒)")
    LICENSE_CACHE_TTL: int = Field(default=300, description="授权信息缓存时间(秒)")

    # SSE 配置
    SSE_POLL_TIMEOUT_SECONDS: float = Field(default=1.0)
    SSE_HEARTBEAT_INTERVAL_SECONDS: int = Field(default=10)
    SSE_TASK_MAX_IDLE_SECONDS: int = Field(default=300)
    SSE_BATCH_POLL_INTERVAL_SECONDS: float = Field(default=2.0)
    SSE_BATCH_MAX_IDLE_SECONDS: int = Field(default=600)


    # 监控配置
    METRICS_ENABLED: bool = Field(default=True)
    HEALTH_CHECK_INTERVAL: int = Field(default=60)  # 60秒

    # Agent 执行轨迹采集（P1: 机器可读执行轨迹）
    AGENT_EXECUTION_TRACE_ENABLED: bool = Field(
        default=False,
        description="启用 Agent 执行轨迹采集（写入 MongoDB agent_execution_traces 集合）。默认关闭，排查问题时可开启，或通过分析任务的 enable_trace 参数单次开启。"
    )

    # Agent 断言执行（P2: 反思 lesson 升级为可执行断言）
    AGENT_ASSERTION_ENABLED: bool = Field(
        default=True,
        description="启用 Agent 断言执行（从 agent_assertions 集合加载并执行断言）"
    )
    AGENT_ASSERTION_CACHE_TTL_SECONDS: int = Field(
        default=60,
        description="断言进程内缓存 TTL（秒），避免每次执行都查 MongoDB"
    )


    # 配置真相来源（方案A）：file|db|hybrid
    # - file：以文件/env 为准（推荐，生产缺省）
    # - db：以数据库为准（仅兼容旧版，不推荐）
    # - hybrid：文件/env 优先，DB 作为兜底
    CONFIG_SOT: str = Field(default="file")


    # 基础信息同步任务配置（可配置调度）
    SYNC_STOCK_BASICS_ENABLED: bool = Field(default=True)
    # 优先使用 CRON 表达式，例如 "30 6 * * *" 表示每日 06:30
    SYNC_STOCK_BASICS_CRON: str = Field(default="")
    # 若未提供 CRON，则使用简单时间字符串 "HH:MM"（24小时制）
    SYNC_STOCK_BASICS_TIME: str = Field(default="06:30")
    # 时区
    TIMEZONE: str = Field(default="Asia/Shanghai")

    # 实时行情入库任务
    QUOTES_INGEST_ENABLED: bool = Field(default=True)
    QUOTES_INGEST_INTERVAL_SECONDS: int = Field(
        default=360,
        description="实时行情采集间隔（秒）。默认360秒（6分钟），免费用户建议>=300秒，付费用户可设置5-60秒"
    )
    # 休市期/启动兜底补数（填充上一笔快照）
    QUOTES_BACKFILL_ON_STARTUP: bool = Field(default=True)
    QUOTES_BACKFILL_ON_OFFHOURS: bool = Field(default=True)

    # 止损提醒扫描任务
    STOP_LOSS_ALERT_ENABLED: bool = Field(default=True, description="启用止损提醒扫描任务")
    STOP_LOSS_ALERT_INTERVAL_SECONDS: int = Field(default=600, description="止损提醒扫描间隔（秒）")
    STOP_LOSS_ALERT_NEAR_PCT: float = Field(default=0.02, description="接近止损线判定比例（默认2%）")
    STOP_LOSS_ALERT_COOLDOWN_MINUTES: int = Field(default=180, description="同一状态重复提醒冷却时间（分钟）")

    # 实时行情接口轮换配置
    QUOTES_ROTATION_ENABLED: bool = Field(
        default=True,
        description="启用接口轮换机制（Tushare → AKShare东方财富 → AKShare新浪财经）"
    )
    QUOTES_TUSHARE_HOURLY_LIMIT: int = Field(
        default=2,
        description="Tushare rt_k接口每小时调用次数限制（免费用户2次，付费用户可设置更高）"
    )
    QUOTES_AUTO_DETECT_TUSHARE_PERMISSION: bool = Field(
        default=True,
        description="自动检测Tushare rt_k接口权限，付费用户自动切换到高频模式（5秒）"
    )

    # Tushare基础配置
    TUSHARE_TOKEN: str = Field(default="", description="Tushare API Token")
    TUSHARE_ENABLED: bool = Field(default=True, description="启用Tushare数据源")
    TUSHARE_TIER: str = Field(default="standard", description="Tushare积分等级 (free/basic/standard/premium/vip)")
    TUSHARE_RATE_LIMIT_SAFETY_MARGIN: float = Field(default=0.8, ge=0.1, le=1.0, description="速率限制安全边际")

    # ==================== 京东云合作版配置 ====================
    # 通过 JDYUN_MODE=true 启用京东云合作版模式
    # 启用后，LLM 和数据源配置从京东云平台注入的环境变量读取：
    # - OPENAI_API_BASE: 京东云模型服务地址
    # - OPENAI_API_KEY: 京东云 API Key
    # - OPENAI_MODEL: 默认对话模型（GLM-5 / GLM-5.1 / GLM-5.2 / DeepSeek-V4-Flash）
    # - EMBEDDING_MODEL: Embedding 模型（默认 Qwen3-Embedding-8B）
    # - TUSHARE_TOKEN: Tushare 数据源 Token
    JDYUN_MODE: bool = Field(default=False, description="京东云合作版模式开关")

    # ==================== 开发环境 License 跳过开关 ====================
    # 仅当 DEBUG=True 且 LICENSE_SKIP_PRO_CHECK=true 时生效：
    # 所有 PRO 功能（工作流、高级课程等）对当前登录用户直接放行，方便本地开发测试。
    # 生产环境（DEBUG=False）即使误设为 true 也不会生效，保证 License 校验不被绕过。
    LICENSE_SKIP_PRO_CHECK: bool = Field(default=False, description="开发模式跳过 PRO License 校验（仅 DEBUG=True 时生效）")

    # Tushare统一数据同步配置
    TUSHARE_UNIFIED_ENABLED: bool = Field(default=True)
    TUSHARE_BASIC_INFO_SYNC_ENABLED: bool = Field(default=True)
    TUSHARE_BASIC_INFO_SYNC_CRON: str = Field(default="0 2 * * *")  # 每日凌晨2点
    TUSHARE_QUOTES_SYNC_ENABLED: bool = Field(default=True)
    TUSHARE_QUOTES_SYNC_CRON: str = Field(default="*/5 9-15 * * 1-5")  # 交易时间每5分钟
    TUSHARE_HISTORICAL_SYNC_ENABLED: bool = Field(default=True)
    TUSHARE_HISTORICAL_SYNC_CRON: str = Field(default="0 18 * * 1-5")  # 工作日18点
    TUSHARE_FINANCIAL_SYNC_ENABLED: bool = Field(default=True)
    TUSHARE_FINANCIAL_SYNC_CRON: str = Field(default="0 3 * * 0")  # 周日凌晨3点
    TUSHARE_STATUS_CHECK_ENABLED: bool = Field(default=True)
    TUSHARE_STATUS_CHECK_CRON: str = Field(default="0 * * * *")  # 每小时
    
    # Tushare实时行情每小时同步任务（免费用户每小时只能调用一次）
    TUSHARE_REALTIME_QUOTES_HOURLY_ENABLED: bool = Field(default=True, description="启用Tushare实时行情每小时同步（免费用户每小时只能调用一次）")
    TUSHARE_REALTIME_QUOTES_HOURLY_CRON: str = Field(default="31 * * * *", description="实时行情每小时同步CRON表达式（每小时31分执行）")

    # 股票关注列表A股数据同步任务配置
    FAVORITES_DATA_SYNC_ENABLED: bool = Field(default=True, description="启用股票关注列表A股数据同步")
    FAVORITES_DATA_SYNC_CRON: str = Field(default="0 19 * * 1-5", description="股票关注列表A股数据同步CRON表达式（交易日晚上7点）")

    # 技术指标物化任务配置
    TECHNICAL_INDICATORS_MATERIALIZATION_ENABLED: bool = Field(default=True, description="启用技术指标物化任务")
    TECHNICAL_INDICATORS_MATERIALIZATION_CRON: str = Field(default="20 18 * * 1-5", description="技术指标物化CRON表达式（默认交易日18:20）")

    # 外部渠道无主题会话沉淀任务
    IM_TOPIC_DIGEST_ENABLED: bool = Field(default=True, description="启用外部会话定期沉淀到研究主题")
    IM_TOPIC_DIGEST_CRON: str = Field(default="30 22 * * *", description="外部会话沉淀CRON表达式，默认每日22:30")
    IM_TOPIC_DIGEST_MIN_MESSAGES: int = Field(default=6, ge=2, le=100, description="触发沉淀所需的最少新增消息数")
    IM_TOPIC_DIGEST_LOOKBACK_LIMIT: int = Field(default=20, ge=6, le=200, description="每次沉淀读取的最大消息数")

    # Tushare数据初始化配置
    TUSHARE_INIT_HISTORICAL_DAYS: int = Field(default=365, ge=1, le=3650, description="初始化历史数据天数")
    TUSHARE_INIT_BATCH_SIZE: int = Field(default=100, ge=10, le=1000, description="初始化批处理大小")
    TUSHARE_INIT_AUTO_START: bool = Field(default=False, description="应用启动时自动检查并初始化数据")

    # AKShare统一数据同步配置
    AKSHARE_UNIFIED_ENABLED: bool = Field(default=True, description="启用AKShare统一数据同步")
    AKSHARE_BASIC_INFO_SYNC_ENABLED: bool = Field(default=True, description="启用基础信息同步")
    AKSHARE_BASIC_INFO_SYNC_CRON: str = Field(default="0 3 * * *", description="基础信息同步CRON表达式")  # 每日凌晨3点
    AKSHARE_QUOTES_SYNC_ENABLED: bool = Field(default=True, description="启用行情同步")
    AKSHARE_QUOTES_SYNC_CRON: str = Field(default="*/30 9-15 * * 1-5", description="行情同步CRON表达式")  # 交易时间每30分钟（避免频率限制）
    AKSHARE_HISTORICAL_SYNC_ENABLED: bool = Field(default=True, description="启用历史数据同步")
    AKSHARE_HISTORICAL_SYNC_CRON: str = Field(default="0 18 * * 1-5", description="历史数据同步CRON表达式")  # 工作日18点
    AKSHARE_FINANCIAL_SYNC_ENABLED: bool = Field(default=True, description="启用财务数据同步")
    AKSHARE_FINANCIAL_SYNC_CRON: str = Field(default="0 4 * * 0", description="财务数据同步CRON表达式")  # 周日凌晨4点
    AKSHARE_STATUS_CHECK_ENABLED: bool = Field(default=True, description="启用状态检查")
    AKSHARE_STATUS_CHECK_CRON: str = Field(default="30 * * * *", description="状态检查CRON表达式")  # 每小时30分

    # ETF 数据同步配置（首次全量，后续按最新入库日期增量补齐）
    ETF_SYNC_ENABLED: bool = Field(default=True, description="启用 ETF 数据同步")
    ETF_SYNC_CRON: str = Field(default="0 4 * * 1-5", description="ETF 同步 CRON 表达式")  # 工作日凌晨4点
    ETF_SYNC_DAYS: int = Field(default=30, ge=1, le=365, description="ETF 强制同步回溯天数（force/manual 模式使用）")
    ETF_SYNC_ITEM_TIMEOUT_SECONDS: int = Field(default=60, ge=5, le=600, description="ETF 单只标的日线抓取超时时间（秒）")

    # 官方行业数据（从官网 URL 获取，避免 AKShare 轮询封号）
    OFFICIAL_INDUSTRY_DATA_URL: Optional[str] = Field(
        default=None,
        description="A股行业数据 JSON URL，格式: {\"600519\":\"白酒\",\"000001\":\"银行\"} 或 [{\"code\":\"600519\",\"industry\":\"白酒\"}]"
    )

    # AKShare数据初始化配置
    AKSHARE_INIT_HISTORICAL_DAYS: int = Field(default=365, ge=1, le=3650, description="初始化历史数据天数")
    AKSHARE_INIT_BATCH_SIZE: int = Field(default=100, ge=10, le=1000, description="初始化批处理大小")
    AKSHARE_INIT_AUTO_START: bool = Field(default=False, description="应用启动时自动检查并初始化数据")

    # ==================== 分析师数据获取配置 ====================

    # 市场分析师数据范围配置
    # 默认60天：可覆盖MA60等所有常用技术指标（MA5/10/20/60, MACD, RSI, BOLL）
    MARKET_ANALYST_LOOKBACK_DAYS: int = Field(default=60, ge=5, le=365, description="市场分析回溯天数（用于技术分析）")

    # ==================== BaoStock统一数据同步配置 ====================

    # BaoStock统一数据同步总开关
    BAOSTOCK_UNIFIED_ENABLED: bool = Field(default=True, description="启用BaoStock统一数据同步")

    # BaoStock数据同步任务配置
    BAOSTOCK_BASIC_INFO_SYNC_ENABLED: bool = Field(default=True, description="启用基础信息同步")
    BAOSTOCK_BASIC_INFO_SYNC_CRON: str = Field(default="0 4 * * *", description="基础信息同步CRON表达式")  # 每日凌晨4点
    BAOSTOCK_DAILY_QUOTES_SYNC_ENABLED: bool = Field(default=True, description="启用日K线同步（注意：BaoStock不支持实时行情）")
    BAOSTOCK_DAILY_QUOTES_SYNC_CRON: str = Field(default="0 18 * * 1-5", description="日K线同步CRON表达式")  # 工作日收盘后16:00
    BAOSTOCK_HISTORICAL_SYNC_ENABLED: bool = Field(default=True, description="启用历史数据同步")
    BAOSTOCK_HISTORICAL_SYNC_CRON: str = Field(default="0 18 * * 1-5", description="历史数据同步CRON表达式")  # 工作日18点
    BAOSTOCK_STATUS_CHECK_ENABLED: bool = Field(default=True, description="启用状态检查")
    BAOSTOCK_STATUS_CHECK_CRON: str = Field(default="45 * * * *", description="状态检查CRON表达式")  # 每小时45分

    # BaoStock数据初始化配置
    BAOSTOCK_INIT_HISTORICAL_DAYS: int = Field(default=365, ge=1, le=3650, description="初始化历史数据天数")
    BAOSTOCK_INIT_BATCH_SIZE: int = Field(default=50, ge=10, le=500, description="初始化批处理大小")
    BAOSTOCK_INIT_AUTO_START: bool = Field(default=False, description="应用启动时自动检查并初始化数据")

    # ==================== QMT 统一数据同步配置 ====================
    QMT_UNIFIED_ENABLED: bool = Field(default=False, description="启用QMT统一数据同步（需 QMT 交易终端运行）")
    QMT_BASIC_INFO_SYNC_ENABLED: bool = Field(default=True, description="启用QMT基础信息同步")
    QMT_BASIC_INFO_SYNC_CRON: str = Field(default="0 7 * * 1-5", description="QMT基础信息同步CRON表达式，默认工作日7点")
    QMT_QUOTES_SYNC_ENABLED: bool = Field(default=False, description="启用QMT实时行情同步")
    QMT_QUOTES_SYNC_CRON: str = Field(default="*/10 9-15 * * 1-5", description="QMT实时行情同步CRON表达式，默认交易时间每10分钟")
    QMT_HISTORICAL_SYNC_ENABLED: bool = Field(default=False, description="启用QMT历史数据同步")
    QMT_HISTORICAL_SYNC_CRON: str = Field(default="0 18 * * 1-5", description="QMT历史数据同步CRON表达式，默认交易日18点")
    QMT_FINANCIAL_SYNC_ENABLED: bool = Field(default=False, description="启用QMT财务数据同步")
    QMT_FINANCIAL_SYNC_CRON: str = Field(default="0 4 * * 0", description="QMT财务数据同步CRON表达式，默认周日4点")
    QMT_STATUS_CHECK_ENABLED: bool = Field(default=True, description="启用QMT状态检查")
    QMT_STATUS_CHECK_CRON: str = Field(default="15 * * * *", description="QMT状态检查CRON表达式，默认每小时15分")
    QMT_TOKEN: str = Field(default="", description="QMT行情服务Token（可选，用于VIP或独立行情连接）")
    QMT_DATA_DIR: str = Field(default="", description="QMT本地数据目录（可选）")
    QMT_LISTEN_PORT: int = Field(default=0, description="QMT监听端口，0 表示自动选择")
    QMT_LISTEN_PORT_RANGE: str = Field(default="58620-58650", description="QMT监听端口范围")
    QMT_INIT_MARKETS: str = Field(default="SH,SZ,BJ", description="QMT初始化市场列表，逗号分隔")
    QMT_KLINE_MIRROR_MARKETS: str = Field(default="", description="QMT K线全推市场列表，逗号分隔")
    QMT_ALLOW_OPTIMIZE_ADDRESSES: str = Field(default="", description="QMT行情优选服务器列表，逗号分隔")
    QMT_START_LOCAL_SERVICE: bool = Field(default=False, description="初始化QMT时是否启动本地服务")
    QMT_KLINE_MIRROR_ENABLED: bool = Field(default=False, description="是否启用QMT K线全推")
    QMT_AUTO_DOWNLOAD_HISTORY: bool = Field(default=True, description="读取QMT K线前自动补充历史数据")
    QMT_AUTO_DOWNLOAD_FINANCIAL: bool = Field(default=False, description="读取QMT财务数据前自动下载财务数据")
    QMT_AUTO_DOWNLOAD_SECTOR: bool = Field(default=False, description="读取QMT股票列表前自动下载板块数据（默认关闭，避免卡死）")

    # BaoStock 配置
    ENABLE_BAOSTOCK: bool = Field(default=True, description="是否启用BaoStock数据源（同步股票列表、每日行情、估值数据等）")
    QMT_HISTORY_START_TIME: str = Field(default="", description="QMT历史数据自动下载起始日期 YYYYMMDD")
    QMT_HISTORICAL_SYNC_DAYS: int = Field(default=365, ge=1, le=3650, description="QMT历史数据同步天数")
    QMT_HISTORICAL_BATCH_SIZE: int = Field(default=100, ge=1, le=1000, description="QMT历史数据同步批量大小")
    QMT_FINANCIAL_BATCH_SIZE: int = Field(default=50, ge=1, le=500, description="QMT财务数据同步批量大小")

    # 数据目录配置
    TRADINGAGENTS_DATA_DIR: str = Field(default="./data")

    @property
    def log_dir(self) -> str:
        """获取日志目录"""
        return os.path.dirname(self.LOG_FILE)

    # ==================== 港股数据配置 ====================

    # 港股数据源配置（按需获取+缓存模式）
    HK_DATA_CACHE_HOURS: int = Field(default=24, ge=1, le=168, description="港股数据缓存时长（小时）")
    HK_DEFAULT_DATA_SOURCE: str = Field(default="yfinance", description="港股默认数据源（yfinance/akshare）")

    # ==================== 美股数据配置 ====================

    # 美股数据源配置（按需获取+缓存模式）
    US_DATA_CACHE_HOURS: int = Field(default=24, ge=1, le=168, description="美股数据缓存时长（小时）")
    US_DEFAULT_DATA_SOURCE: str = Field(default="yfinance", description="美股默认数据源（yfinance/finnhub）")

    # ===== 新闻数据同步服务配置 =====
    NEWS_SYNC_ENABLED: bool = Field(default=True)
    NEWS_SYNC_CRON: str = Field(default="0 */2 * * *")  # 每2小时
    NEWS_SYNC_HOURS_BACK: int = Field(default=24)
    NEWS_SYNC_MAX_PER_SOURCE: int = Field(default=50)

    # ===== 股票关注列表定时分析配置 =====
    WATCHLIST_ANALYSIS_ENABLED: bool = Field(default=False, description="启用股票关注列表定时分析")
    WATCHLIST_ANALYSIS_CRON: str = Field(default="0 8 * * 1-5", description="定时分析CRON表达式，默认工作日早8点")

    # ===== SMTP邮件配置 =====
    SMTP_ENABLED: bool = Field(default=False, description="启用邮件通知功能")
    SMTP_HOST: str = Field(default="smtp.qq.com", description="SMTP服务器地址")
    SMTP_PORT: int = Field(default=587, description="SMTP端口")
    SMTP_USERNAME: str = Field(default="", description="SMTP用户名")
    SMTP_PASSWORD: str = Field(default="", description="SMTP密码或授权码")
    SMTP_FROM_EMAIL: str = Field(default="", description="发件人邮箱")
    SMTP_FROM_NAME: str = Field(default="TradingAgents-CN", description="发件人名称")
    SMTP_USE_TLS: bool = Field(default=True, description="使用TLS加密")
    SMTP_USE_SSL: bool = Field(default=False, description="使用SSL加密")

    # 邮件发送限制
    EMAIL_DAILY_LIMIT: int = Field(default=100, description="每用户每天最多发送邮件数")
    EMAIL_RATE_LIMIT: int = Field(default=10, description="每分钟最多发送邮件数")

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return not self.DEBUG

    _DEFAULT_SECRETS = frozenset({
        # 历史默认值
        "change-me-in-production",
        "change-me-csrf-secret",
        # .env.example / .env.docker 中的可预测占位符（占位符不是真密钥，禁止直接使用）
        "your-super-secret-jwt-key-change-in-production",
        "your-csrf-secret-key-change-in-production",
        "docker-jwt-secret-key-change-in-production-2024",
        "docker-csrf-secret-key-change-in-production-2024",
        # 京东云 docker-compose 中的不安全默认值，必须禁止在生产环境使用
        "jdyun-jwt-secret-key-change-in-production-2024",
        "jdyun-csrf-secret-key-change-in-production-2024",
        # 新增占位符（防止用户直接复制 .env.example 而未修改）
        "PLEASE_CHANGE_JWT_SECRET_USE_openssl_rand_base64_48",
        "PLEASE_CHANGE_CSRF_SECRET_USE_openssl_rand_base64_48",
    })

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if not self.DEBUG:
            if self.JWT_SECRET in self._DEFAULT_SECRETS:
                print(
                    "\n!!! FATAL: JWT_SECRET is still the default value. "
                    "Set a strong random secret in .env before running in production.\n",
                    file=sys.stderr,
                )
                sys.exit(1)
            if self.CSRF_SECRET in self._DEFAULT_SECRETS:
                print(
                    "\n!!! FATAL: CSRF_SECRET is still the default value. "
                    "Set a strong random secret in .env before running in production.\n",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            if self.JWT_SECRET in self._DEFAULT_SECRETS:
                warnings.warn(
                    "JWT_SECRET is using the default value. "
                    "This is acceptable in DEBUG mode only.",
                    stacklevel=2,
                )
        if "*" in self.ALLOWED_ORIGINS and not self.DEBUG:
            print(
                "\n!!! FATAL: ALLOWED_ORIGINS contains '*' in production. "
                "Specify explicit origins in .env.\n",
                file=sys.stderr,
            )
            sys.exit(1)
        return self

    # Ignore any extra environment variables present in .env or process env
    # 支持通过 DOTENV_FILE 环境变量指定不同的 .env 文件（如京东云模式用 .env.jdyun）
    _env_file = os.getenv("DOTENV_FILE", ".env")
    model_config = SettingsConfigDict(env_file=_env_file, env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# 🔧 自动将代理配置设置到环境变量（仅在启用代理时）
# 这样 requests 库可以直接读取 os.environ['HTTP_PROXY'] 等
if settings.PROXY_ENABLED:
    if settings.HTTP_PROXY:
        os.environ['HTTP_PROXY'] = settings.HTTP_PROXY
        os.environ['http_proxy'] = settings.HTTP_PROXY  # 小写版本（某些库需要）
    if settings.HTTPS_PROXY:
        os.environ['HTTPS_PROXY'] = settings.HTTPS_PROXY
        os.environ['https_proxy'] = settings.HTTPS_PROXY  # 小写版本
else:
    # 🔧 代理未启用，清除环境变量中的代理设置（避免系统代理干扰）
    for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if key in os.environ:
            del os.environ[key]

# 🔧 NO_PROXY 始终设置（国内数据源不使用代理）
if settings.NO_PROXY:
    os.environ['NO_PROXY'] = settings.NO_PROXY
    os.environ['no_proxy'] = settings.NO_PROXY  # 小写版本


def get_settings() -> Settings:
    """获取配置实例"""
    return settings