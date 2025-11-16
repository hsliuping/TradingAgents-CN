from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class AgentContext:
    user_id: Optional[str] = None
    preference_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)