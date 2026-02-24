from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class AgentContext:
    """Agent 执行上下文

    包含用户、会话、调试模式和工作流等相关信息。
    在 Agent 执行过程中传递，用于：
    - 提示词模板加载（根据 user_id、preference_id、workflow_id）
    - 调试模式控制（is_debug_mode、debug_template_id）
    - 日志追踪（session_id、request_id）
    """
    user_id: Optional[str] = None
    preference_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    # 🔥 调试模式相关字段
    is_debug_mode: bool = False  # 是否为调试模式
    debug_template_id: Optional[str] = None  # 调试模式下使用的模板ID

    # 🆕 工作流相关字段（用于流程专属提示词加载）
    workflow_id: Optional[str] = None  # 当前执行的工作流ID
    node_id: Optional[str] = None      # 🆕 当前执行的节点ID（同一 agent 在不同节点加载不同提示词）

    extra: Dict[str, Any] = field(default_factory=dict)