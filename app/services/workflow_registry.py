"""
分析工作流注册表

提供统一的工作流配置管理和查询功能
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from app.models.analysis import AnalysisTaskType
import logging

logger = logging.getLogger(__name__)


class AnalysisWorkflowConfig(BaseModel):
    """分析工作流配置
    
    定义一个分析流程的完整配置信息
    """
    task_type: AnalysisTaskType = Field(..., description="任务类型")
    workflow_id: str = Field(..., description="工作流ID")
    name: str = Field(..., description="流程名称")
    description: str = Field(default="", description="流程描述")
    
    # 引擎配置
    default_engine: str = Field(default="workflow", description="默认引擎: workflow/legacy/llm")
    supported_engines: List[str] = Field(
        default_factory=lambda: ["workflow", "legacy", "llm"],
        description="支持的引擎列表"
    )
    
    # 参数配置
    required_params: List[str] = Field(default_factory=list, description="必需参数列表")
    optional_params: Dict[str, Any] = Field(default_factory=dict, description="可选参数及默认值")
    
    # 执行配置
    timeout: int = Field(default=300, description="超时时间（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    
    # 偏好支持
    supports_preference: bool = Field(default=True, description="是否支持分析偏好（aggressive/neutral/conservative）")
    
    # 元数据
    version: str = Field(default="1.0.0", description="版本号")
    tags: List[str] = Field(default_factory=list, description="标签")
    is_active: bool = Field(default=True, description="是否启用")


class AnalysisWorkflowRegistry:
    """分析工作流注册表
    
    单例模式，管理所有分析流程的配置
    
    使用示例:
        # 注册流程
        AnalysisWorkflowRegistry.register(config)
        
        # 获取流程配置
        config = AnalysisWorkflowRegistry.get_config(AnalysisTaskType.STOCK_ANALYSIS)
        
        # 列出所有流程
        all_configs = AnalysisWorkflowRegistry.list_all()
    """
    
    _registry: Dict[AnalysisTaskType, AnalysisWorkflowConfig] = {}
    _initialized: bool = False
    
    @classmethod
    def register(cls, config: AnalysisWorkflowConfig) -> None:
        """注册工作流配置
        
        Args:
            config: 工作流配置对象
        """
        if config.task_type in cls._registry:
            logger.warning(f"工作流配置已存在，将被覆盖: {config.task_type}")
        
        cls._registry[config.task_type] = config
        logger.info(f"✅ 注册工作流: {config.task_type} -> {config.workflow_id}")
    
    @classmethod
    def get_config(cls, task_type: AnalysisTaskType) -> Optional[AnalysisWorkflowConfig]:
        """获取工作流配置
        
        Args:
            task_type: 任务类型（可以是枚举值或字符串）
            
        Returns:
            工作流配置对象，如果不存在则返回 None
        """
        # 如果 task_type 是字符串，尝试转换为枚举
        if isinstance(task_type, str):
            try:
                task_type = AnalysisTaskType(task_type)
            except ValueError:
                logger.warning(f"无效的任务类型字符串: {task_type}")
                return None
        
        return cls._registry.get(task_type)
    
    @classmethod
    def list_all(cls, active_only: bool = True) -> List[AnalysisWorkflowConfig]:
        """列出所有工作流配置
        
        Args:
            active_only: 是否只返回启用的流程
            
        Returns:
            工作流配置列表
        """
        configs = list(cls._registry.values())
        if active_only:
            configs = [c for c in configs if c.is_active]
        return configs
    
    @classmethod
    def list_by_tag(cls, tag: str) -> List[AnalysisWorkflowConfig]:
        """根据标签筛选工作流
        
        Args:
            tag: 标签名称
            
        Returns:
            匹配的工作流配置列表
        """
        return [c for c in cls._registry.values() if tag in c.tags and c.is_active]
    
    @classmethod
    def validate_params(cls, task_type: AnalysisTaskType, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证任务参数
        
        Args:
            task_type: 任务类型（可以是枚举值或字符串）
            params: 任务参数
            
        Returns:
            (是否有效, 错误信息)
        """
        # 如果 task_type 是字符串，尝试转换为枚举
        if isinstance(task_type, str):
            try:
                task_type = AnalysisTaskType(task_type)
            except ValueError:
                return False, f"无效的任务类型字符串: {task_type}"
        
        config = cls.get_config(task_type)
        if not config:
            return False, f"未注册的任务类型: {task_type}"
        
        # 检查必需参数
        for required_param in config.required_params:
            if required_param not in params:
                return False, f"缺少必需参数: {required_param}"
        
        return True, None
    
    @classmethod
    def get_default_params(cls, task_type: AnalysisTaskType) -> Dict[str, Any]:
        """获取默认参数
        
        Args:
            task_type: 任务类型（可以是枚举值或字符串）
            
        Returns:
            默认参数字典
        """
        # 如果 task_type 是字符串，尝试转换为枚举
        if isinstance(task_type, str):
            try:
                task_type = AnalysisTaskType(task_type)
            except ValueError:
                logger.warning(f"无效的任务类型字符串: {task_type}")
                return {}
        
        config = cls.get_config(task_type)
        if not config:
            return {}
        
        return config.optional_params.copy()
    
    @classmethod
    def is_initialized(cls) -> bool:
        """检查是否已初始化"""
        return cls._initialized
    
    @classmethod
    def mark_initialized(cls) -> None:
        """标记为已初始化"""
        cls._initialized = True


def initialize_builtin_workflows() -> None:
    """初始化内置工作流配置

    注册系统内置的分析流程：
    1. 股票分析（TradingAgents完整流程）
    2. 持仓分析
    3. 交易复盘
    """
    if AnalysisWorkflowRegistry.is_initialized():
        logger.info("⏭️  工作流注册表已初始化，跳过")
        return

    logger.info("🚀 开始初始化内置工作流配置...")

    # 1. 股票分析流程
    AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        workflow_id="v2_stock_analysis",
        name="股票完整分析",
        description="基于v2.0 Agent架构的完整多智能体协作分析流程。包含6个专业分析师并行分析，2个研究员辩论，研究经理综合评估，交易员制定策略，风险经理把控风险。",
        default_engine="workflow",
        supported_engines=["workflow", "legacy"],
        required_params=["symbol", "market_type"],
        optional_params={
            "research_depth": "标准",
            "analysis_date": None,
            "selected_analysts": ["market", "fundamentals", "news", "social"],
            "include_sentiment": True,
            "include_risk": True
        },
        timeout=600,  # 10分钟
        max_retries=3,
        supports_preference=True,
        version="2.0.0",
        tags=["股票", "完整分析", "多智能体", "辩论机制"],
        is_active=True
    ))

    # 2. 持仓分析流程
    AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
        task_type=AnalysisTaskType.POSITION_ANALYSIS,
        workflow_id="position_analysis",
        name="持仓分析",
        description="单股持仓分析流程。包含持仓技术面分析师、持仓基本面分析师、持仓风险评估师、持仓操作建议师。",
        default_engine="workflow",
        supported_engines=["workflow", "llm"],
        required_params=["position_id"],
        optional_params={
            "research_depth": "标准",
            "include_add_position": True,
            "target_profit_pct": 20.0,
            "total_capital": None,
            "max_position_pct": 30.0,
            "max_loss_pct": 10.0
        },
        timeout=300,  # 5分钟
        max_retries=3,
        supports_preference=True,
        version="1.0.0",
        tags=["持仓", "操作建议", "风险评估"],
        is_active=True
    ))

    # 3. 交易复盘流程
    AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
        task_type=AnalysisTaskType.TRADE_REVIEW,
        workflow_id="trade_review",
        name="交易复盘",
        description="交易复盘分析流程。包含时机分析师、仓位分析师、情绪与纪律分析师、归因分析师、复盘总结师。",
        default_engine="workflow",
        supported_engines=["workflow", "llm"],
        required_params=["review_id"],
        optional_params={
            "trading_system_id": None,
            "include_plan_analysis": True
        },
        timeout=300,  # 5分钟
        max_retries=3,
        supports_preference=True,
        version="2.0.0",
        tags=["复盘", "交易计划", "情绪分析"],
        is_active=True
    ))

    # 4. 组合健康度分析流程（预留）
    AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
        task_type=AnalysisTaskType.PORTFOLIO_HEALTH,
        workflow_id="portfolio_health",
        name="组合健康度分析",
        description="投资组合健康度分析流程。评估组合的风险、收益、集中度等指标。",
        default_engine="llm",
        supported_engines=["llm"],
        required_params=["user_id"],
        optional_params={
            "include_paper": True,
            "research_depth": "标准"
        },
        timeout=180,  # 3分钟
        max_retries=3,
        supports_preference=True,
        version="1.0.0",
        tags=["组合", "健康度", "风险评估"],
        is_active=True
    ))

    AnalysisWorkflowRegistry.mark_initialized()

    logger.info(f"✅ 内置工作流配置初始化完成，共注册 {len(AnalysisWorkflowRegistry.list_all())} 个流程")
    for config in AnalysisWorkflowRegistry.list_all():
        logger.info(f"   - {config.task_type}: {config.name} ({config.workflow_id})")

