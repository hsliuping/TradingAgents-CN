"""
权限门控（社区版薄壳）

本文件由发布管道（scripts/publish_community.py）生成：
完整实现见 core/licensing/community_stub.py，此处仅 re-export，
保持 app.core.permissions 的对外签名不变，社区版调用方零改动。
"""

from core.licensing.community_stub import (  # noqa: F401
    get_app_token,
    get_license_info,
    require_pro,
    require_feature,
    PRO_FEATURES,
)
