"""
通用 HITL（Human-in-the-Loop）模块。

提供跨子系统的待确认操作管理：
- 智能助手关键操作确认（项4）
- Skill 生成后审核才绑定（项6）

核心服务：HITLCheckpointService
"""

from .checkpoint_store import (
    HITLCheckpointService,
    PendingOperation,
    get_hitl_service,
    COLLECTION_NAME,
)

__all__ = [
    "HITLCheckpointService",
    "PendingOperation",
    "get_hitl_service",
    "COLLECTION_NAME",
]

