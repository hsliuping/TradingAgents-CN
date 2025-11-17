from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class AgentContext:
    user_id: Optional[str] = None
    preference_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    # 🔥 调试模式相关字段
    is_debug_mode: bool = False  # 是否为调试模式
    debug_template_id: Optional[str] = None  # 调试模式下使用的模板ID
    extra: Dict[str, Any] = field(default_factory=dict)