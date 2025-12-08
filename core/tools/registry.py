"""
工具注册表

管理所有可用工具的元数据和发现
"""

import threading
from typing import Dict, List, Optional

from .config import ToolMetadata, ToolCategory, BUILTIN_TOOLS


class ToolRegistry:
    """
    工具注册表（单例模式）
    
    用法:
        registry = ToolRegistry()
        
        # 获取所有工具
        all_tools = registry.list_all()
        
        # 获取特定类别工具
        market_tools = registry.get_by_category("market")
        
        # 获取某个 Agent 的可用工具
        tools = registry.get_tools_for_agent("market_analyst")
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ToolRegistry, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._tools: Dict[str, ToolMetadata] = {}
            self._load_builtin_tools()
            self._initialized = True
    
    def _load_builtin_tools(self) -> None:
        """加载内置工具"""
        for tool_id, metadata in BUILTIN_TOOLS.items():
            self._tools[tool_id] = metadata
    
    def register(self, metadata: ToolMetadata, override: bool = False) -> None:
        """注册工具"""
        if metadata.id in self._tools and not override:
            raise ValueError(f"工具 '{metadata.id}' 已注册，使用 override=True 覆盖")
        self._tools[metadata.id] = metadata
    
    def unregister(self, tool_id: str) -> None:
        """注销工具"""
        self._tools.pop(tool_id, None)
    
    def get(self, tool_id: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        return self._tools.get(tool_id)
    
    def list_all(self) -> List[ToolMetadata]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def get_by_category(self, category: str) -> List[ToolMetadata]:
        """按类别获取工具"""
        return [t for t in self._tools.values() if t.category == category]
    
    def get_by_ids(self, tool_ids: List[str]) -> List[ToolMetadata]:
        """根据 ID 列表获取工具"""
        return [self._tools[tid] for tid in tool_ids if tid in self._tools]
    
    def get_online_tools(self) -> List[ToolMetadata]:
        """获取所有在线工具"""
        return [t for t in self._tools.values() if t.is_online]
    
    def get_offline_tools(self) -> List[ToolMetadata]:
        """获取所有离线工具"""
        return [t for t in self._tools.values() if not t.is_online]


# 全局注册表实例
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry

