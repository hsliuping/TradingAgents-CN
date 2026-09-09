"""
社区版权限门控 stub（v3.6.0 社区版开源分离 · M1 §7.3）

社区版发布时的门控替换实现：无授权服务器、无 token 验证、无网络请求。
发布脚本（scripts/publish_community.py，方案 §8.1 步骤 c）按以下方式指向本模块：

1. app/core/permissions.py → 整文件替换为薄壳：从本模块 re-export
   get_app_token / get_license_info / require_pro / require_feature / PRO_FEATURES
2. app/services/license_service.py → 整文件替换为薄壳：从本模块 re-export
   LicenseInfo / LicenseService(=CommunityLicenseService) / get_license_service / FREE_ACCESS_FEATURES
3. core/licensing/：删除 validator.py / manager.py / features.py，保留 models.py 与本文件，
   __init__.py 改为从本模块 re-export（core/api/agent_api.py 的 LicenseManager 引用自动切换）

语义约定：
- require_pro / require_feature（FastAPI 依赖）：放行透传。社区版 Pro 功能靠发布管道
  物理剔除（PRO_ROUTERS / views/pro），保留文件中的残留门控（如 advanced_courses.py
  路由级依赖）不应阻断社区版主链路。
- has_feature：保持免费语义——FREE_ACCESS_FEATURES 放行，其余 False。
  社区版保留代码中的 Pro 子功能门控（如 review.py 的 trading_plan_check）继续拦截。
- is_pro：恒 False（社区版无付费体系，plan 恒为 "free"）。
- 配额：内置 Free 档（分析师 4、研究员 2、单并发、API 100/日），
  数值与 core/licensing/models.py 的 TIER_FEATURES[FREE] 保持一致。

见 docs/05-design/v3.0/v3.6.0-community-edition-separation-plan.md §7.3
"""

import logging
from typing import Any, Callable, Optional

from fastapi import Depends, Header
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from .models import LicenseFeatures, LicenseTier

logger = logging.getLogger("core.licensing.community_stub")


# =============================================================================
# 社区版配额（Free 档）
# =============================================================================

COMMUNITY_TIER_FEATURES = LicenseFeatures(
    max_analysts=4,               # 最大分析师数量
    max_researchers=2,            # 最大研究员数量
    allow_custom_agents=False,    # 不允许自定义智能体
    max_workflows=3,              # 最大保存工作流数
    max_nodes_per_workflow=10,    # 每个工作流最大节点数
    allow_workflow_export=False,  # 不允许导出工作流
    allow_sector_analyst=False,   # 行业分析师
    allow_index_analyst=False,    # 大盘分析师
    allow_parallel_execution=False,   # 并行执行
    allow_memory_persistence=False,   # 记忆持久化
    daily_api_calls=100,          # 每日 API 调用限制
    max_concurrent_executions=1,  # 最大并发执行数（单并发）
)

# 社区版免费放行的功能（与 app/services/license_service.py 的 FREE_ACCESS_FEATURES 对齐）
FREE_ACCESS_FEATURES = {"portfolio_analysis", "trade_review"}

# 社区版无 Pro 专属功能（Pro 功能靠发布管道物理剔除，不靠运行时门控）
PRO_FEATURES: list[str] = []


# =============================================================================
# LicenseInfo 模型（同 app/services/license_service.py 字段定义）
# =============================================================================

class LicenseInfo(BaseModel):
    """授权信息（社区版：恒为 free 档有效授权）"""
    email: str
    plan: str  # 社区版恒为 "free"
    features: list[str] = Field(default_factory=list)
    device_registered: bool = False
    is_valid: bool = True
    error_message: Optional[str] = None
    verified_at: Optional[Any] = None
    # 到期时间
    trial_end_at: Optional[str] = None  # 试用到期时间
    pro_expire_at: Optional[str] = None  # PRO到期时间
    # 缓存相关
    cached: bool = False
    cache_expires_at: Optional[Any] = None
    # 离线模式
    offline_mode: bool = False


def _community_license_info(email: str = "") -> LicenseInfo:
    """构造社区版授权信息（free 档、有效、无网络验证）"""
    return LicenseInfo(email=email, plan="free", is_valid=True, error_message=None)


# =============================================================================
# 授权服务 stub（同 app/services/license_service.py 入口签名）
# =============================================================================

class CommunityLicenseService:
    """社区版授权服务：无外部验证，仅提供免费语义判断"""

    def get_available_servers(self) -> list[dict[str, str]]:
        """社区版无授权服务器"""
        return []

    def resolve_auth_server(self, auth_server: Optional[str] = None) -> str:
        """社区版无授权服务器"""
        return ""

    def get_base_url(self, auth_server: Optional[str] = None) -> str:
        """社区版无授权服务器"""
        return ""

    async def verify_app_token(self, token: str, auth_server: Optional[str] = None) -> LicenseInfo:
        """社区版不验证 token（license 路由已剔除，此方法仅为兼容残留调用，防御性返回 free 档）"""
        logger.debug("社区版跳过 App Token 验证")
        return _community_license_info()

    def is_pro(self, license_info: LicenseInfo) -> bool:
        """社区版无付费体系，恒为非 PRO"""
        return False

    def has_feature(self, license_info: LicenseInfo, feature: str) -> bool:
        """免费语义：FREE_ACCESS_FEATURES 放行，其余拦截（社区版 plan 恒为 free）"""
        if not license_info.is_valid:
            return False
        if feature in FREE_ACCESS_FEATURES:
            return True
        if feature in license_info.features:
            return True
        return False

    def clear_cache(self, token: Optional[str] = None, auth_server: Optional[str] = None) -> None:
        """社区版无缓存"""
        pass


# 单例服务（同 get_license_service 形态）
_license_service: Optional[CommunityLicenseService] = None


def get_license_service() -> CommunityLicenseService:
    """获取社区版授权服务实例（单例）"""
    global _license_service
    if _license_service is None:
        _license_service = CommunityLicenseService()
    return _license_service


# =============================================================================
# FastAPI 路由依赖（同 app/core/permissions.py 入口签名）
# =============================================================================

async def get_app_token(
    x_app_token: Optional[str] = Header(None, alias="X-App-Token")
) -> Optional[str]:
    """从请求头获取 App Token（社区版不使用，保留签名兼容）"""
    return x_app_token


async def get_license_info(
    app_token: Optional[str] = Depends(get_app_token),
    user: dict = Depends(get_current_user)
) -> LicenseInfo:
    """
    获取用户的授权信息（社区版：恒为 free 档有效授权，无网络验证）

    与 app/core/permissions.py 同签名；社区版发布时
    app/routers/auth_db.py 为保留路由，依赖链可正常解析。
    """
    email = user.get("email", "") if isinstance(user, dict) else ""
    return _community_license_info(email)


async def require_pro(
    license_info: LicenseInfo = Depends(get_license_info)
) -> LicenseInfo:
    """
    要求 PRO 权限的依赖（社区版：放行透传）

    社区版 Pro 路由已被发布管道物理剔除，本依赖仅在保留文件的残留调用中
    出现时放行，保证社区版主链路不被阻断。
    """
    return license_info


def require_feature(feature: str) -> Callable:
    """
    要求特定功能的依赖工厂（社区版：放行透传）

    使用方式（与 app/core/permissions.py 完全一致）:
        @router.get("/feature", dependencies=[Depends(require_feature("xxx"))])
        async def endpoint(...): ...
    """
    async def _check_feature(
        license_info: LicenseInfo = Depends(get_license_info),
    ) -> LicenseInfo:
        return license_info

    return _check_feature


# =============================================================================
# 引擎侧许可证管理器 stub（同 core/licensing/manager.py 的 LicenseManager 签名）
# =============================================================================

class CommunityLicenseManager:
    """
    社区版许可证管理器（单例）：恒为 Free 档 + 内置社区版配额

    供 core/api/agent_api.py 等引擎侧代码使用：
    tier 恒为 FREE → 仅 free 档智能体可见（与社区版功能边界一致）。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def tier(self) -> LicenseTier:
        """当前级别：恒为 FREE"""
        return LicenseTier.FREE

    @property
    def is_valid(self) -> bool:
        """社区版始终有效"""
        return True

    @property
    def features(self) -> LicenseFeatures:
        """社区版配额（Free 档）"""
        return COMMUNITY_TIER_FEATURES

    def can_use_feature(self, feature_name: str) -> bool:
        """检查是否可以使用某功能（按 Free 档配额）"""
        features = self.features
        if hasattr(features, f"allow_{feature_name}"):
            return getattr(features, f"allow_{feature_name}")
        return True

    def check_limit(self, limit_name: str, current_value: int) -> bool:
        """检查是否超过限制（按 Free 档配额）"""
        features = self.features
        if hasattr(features, limit_name):
            max_value = getattr(features, limit_name)
            return current_value < max_value
        return True

    def get_remaining(self, limit_name: str, current_value: int) -> int:
        """获取剩余配额（按 Free 档配额）"""
        features = self.features
        if hasattr(features, limit_name):
            max_value = getattr(features, limit_name)
            return max(0, max_value - current_value)
        return 999999

    def activate(self, license_key: str, prefer_online: bool = True) -> tuple[bool, Optional[str]]:
        """社区版不支持许可证激活"""
        return False, "社区版不支持许可证激活"

    def deactivate(self) -> None:
        """社区版无许可证概念"""
        pass


# LicenseManager 别名：薄壳层与 __init__.py re-export 用，
# 使 `from ..licensing import LicenseManager` 的调用方（core/api/agent_api.py）无感切换
LicenseManager = CommunityLicenseManager
