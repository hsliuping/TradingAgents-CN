"""
授权相关数据模型
"""

from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class LicenseTier(str, Enum):
    """许可证级别"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class LicenseFeatures(BaseModel):
    """许可证功能定义"""
    
    # 智能体限制
    max_analysts: int = 4          # 最大分析师数量
    max_researchers: int = 2       # 最大研究员数量
    allow_custom_agents: bool = False  # 允许自定义智能体
    
    # 工作流限制
    max_workflows: int = 3         # 最大保存工作流数
    max_nodes_per_workflow: int = 10  # 每个工作流最大节点数
    allow_workflow_export: bool = False  # 允许导出工作流
    
    # 高级功能
    allow_sector_analyst: bool = False   # 行业分析师
    allow_index_analyst: bool = False    # 大盘分析师
    allow_parallel_execution: bool = False  # 并行执行
    allow_memory_persistence: bool = False  # 记忆持久化
    
    # API 限制
    daily_api_calls: int = 100     # 每日 API 调用限制
    max_concurrent_executions: int = 1  # 最大并发执行数
    
    # 支持
    priority_support: bool = False
    custom_branding: bool = False


# 预定义的功能配置
TIER_FEATURES = {
    LicenseTier.FREE: LicenseFeatures(
        max_analysts=4,
        max_researchers=2,
        max_workflows=3,
        max_nodes_per_workflow=10,
        daily_api_calls=100,
        max_concurrent_executions=1,
    ),
    LicenseTier.BASIC: LicenseFeatures(
        max_analysts=4,
        max_researchers=2,
        max_workflows=10,
        max_nodes_per_workflow=20,
        allow_workflow_export=True,
        daily_api_calls=500,
        max_concurrent_executions=2,
    ),
    LicenseTier.PRO: LicenseFeatures(
        max_analysts=6,  # 包含 sector_analyst, index_analyst
        max_researchers=2,
        allow_custom_agents=True,
        max_workflows=50,
        max_nodes_per_workflow=50,
        allow_workflow_export=True,
        allow_sector_analyst=True,
        allow_index_analyst=True,
        allow_parallel_execution=True,
        allow_memory_persistence=True,
        daily_api_calls=2000,
        max_concurrent_executions=5,
        priority_support=True,
    ),
    LicenseTier.ENTERPRISE: LicenseFeatures(
        max_analysts=999,
        max_researchers=999,
        allow_custom_agents=True,
        max_workflows=999,
        max_nodes_per_workflow=999,
        allow_workflow_export=True,
        allow_sector_analyst=True,
        allow_index_analyst=True,
        allow_parallel_execution=True,
        allow_memory_persistence=True,
        daily_api_calls=999999,
        max_concurrent_executions=50,
        priority_support=True,
        custom_branding=True,
    ),
}


class License(BaseModel):
    """许可证"""
    
    id: str                        # 许可证 ID
    tier: LicenseTier              # 级别
    
    # 用户信息
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    organization: Optional[str] = None
    
    # 有效期
    issued_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # 功能
    features: LicenseFeatures = Field(default_factory=LicenseFeatures)
    
    # 状态
    is_active: bool = True
    
    class Config:
        use_enum_values = True
    
    @classmethod
    def create_free(cls) -> "License":
        """创建免费许可证"""
        return cls(
            id="free",
            tier=LicenseTier.FREE,
            features=TIER_FEATURES[LicenseTier.FREE],
        )
    
    @classmethod
    def create_for_tier(cls, tier: LicenseTier, **kwargs) -> "License":
        """为指定级别创建许可证"""
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            tier=tier,
            features=TIER_FEATURES[tier],
            **kwargs
        )
    
    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """是否有效"""
        return self.is_active and not self.is_expired

