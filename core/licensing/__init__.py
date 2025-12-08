"""
授权管理模块

管理许可证验证、功能门控和使用量追踪
"""

from .models import License, LicenseFeatures, LicenseTier
from .manager import LicenseManager
from .features import FeatureGate

__all__ = [
    "License",
    "LicenseFeatures",
    "LicenseTier",
    "LicenseManager",
    "FeatureGate",
]

