"""Public projections of workflow result metadata; no runtime dependencies."""

from typing import Any, Dict, Optional


def public_degraded_nodes(value: Any) -> Optional[Dict[str, Dict[str, str]]]:
    """Keep node identity without publishing raw exceptions or extra context.

    Missing/malformed metadata is unrecorded, not an empty success claim.
    An explicitly recorded empty mapping remains empty. Detailed exceptions
    stay in the workflow's existing invocation/execution logs.
    """
    if not isinstance(value, dict):
        return None
    if any(not isinstance(key, str) or not isinstance(node, dict)
           for key, node in value.items()):
        return None

    return {
        key: {
            **{field: node[field] for field in ("agent_id", "label")
               if isinstance(node.get(field), str)},
            "error": "该分析节点执行失败，详细原因请查看执行日志。",
        }
        for key, node in value.items()
    }
