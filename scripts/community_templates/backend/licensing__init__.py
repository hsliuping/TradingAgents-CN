"""
授权管理模块（社区版）

本文件由发布管道（scripts/publish_community.py）生成：
社区版删除 validator.py / manager.py / features.py（授权服务器验证逻辑，
付费体系专属），保留 models.py（配额模型）与 community_stub.py（社区版实现），
并从此处 re-export 引擎侧依赖的 LicenseManager。
"""

from .models import License, LicenseFeatures, LicenseTier  # noqa: F401
from .community_stub import CommunityLicenseManager as LicenseManager  # noqa: F401

__all__ = [
    "License",
    "LicenseFeatures",
    "LicenseTier",
    "LicenseManager",
]
