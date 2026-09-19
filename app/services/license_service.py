"""
授权服务（社区版薄壳）

本文件由发布管道（scripts/publish_community.py）生成：
完整实现见 core/licensing/community_stub.py，此处仅 re-export，
保持 app.services.license_service 的对外签名不变，社区版调用方零改动。
"""

from core.licensing.community_stub import (  # noqa: F401
    LicenseInfo,
    CommunityLicenseService as LicenseService,
    get_license_service,
    FREE_ACCESS_FEATURES,
)
