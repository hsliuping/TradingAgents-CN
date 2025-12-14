"""
工具注册表

管理所有可用工具的元数据和发现
"""

import logging
import threading
from typing import Dict, List, Optional, Callable, Any

from .config import ToolMetadata, ToolCategory, BUILTIN_TOOLS

logger = logging.getLogger(__name__)


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
            self._functions: Dict[str, Callable] = {}  # 存储实际函数实现
            self._load_builtin_tools()
            self._load_tool_implementations()  # 自动加载工具实现
            self._initialized = True

    def _load_builtin_tools(self) -> None:
        """加载内置工具元数据"""
        for tool_id, metadata in BUILTIN_TOOLS.items():
            self._tools[tool_id] = metadata

    def _load_tool_implementations(self) -> None:
        """加载工具函数实现"""
        try:
            from .loader import ToolLoader
            loader = ToolLoader()
            count = loader.load_all()
            logger.info(f"✅ 自动加载了 {count} 个工具模块")
        except Exception as e:
            logger.warning(f"⚠️ 自动加载工具模块失败: {e}")
    
    def register(self, metadata: ToolMetadata, override: bool = False) -> None:
        """注册工具"""
        if metadata.id in self._tools and not override:
            raise ValueError(f"工具 '{metadata.id}' 已注册，使用 override=True 覆盖")
        self._tools[metadata.id] = metadata
    
    def unregister(self, tool_id: str) -> None:
        """注销工具"""
        self._tools.pop(tool_id, None)
        self._functions.pop(tool_id, None)
    
    def get(self, tool_id: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        return self._tools.get(tool_id)

    def has_tool(self, tool_id: str) -> bool:
        """检查工具是否已注册"""
        return tool_id in self._tools

    def get_tool(self, tool_id: str) -> Optional[ToolMetadata]:
        """获取工具元数据（别名方法）"""
        return self.get(tool_id)

    def get_all_tools(self) -> List[ToolMetadata]:
        """获取所有工具（别名方法）"""
        return self.list_all()

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

    # ==================== 函数注册（新增） ====================

    def register_function(
        self,
        tool_id: str,
        func: Callable,
        name: str,
        category: str,
        description: str = "",
        is_online: bool = True,
        is_legacy: bool = False,
        override: bool = False,
        **kwargs
    ) -> None:
        """
        注册一个函数作为工具

        Args:
            tool_id: 工具唯一ID
            func: 实际的函数实现
            name: 工具显示名称
            category: 工具分类
            description: 工具描述
            is_online: 是否需要在线
            is_legacy: 是否为旧工具适配
            override: 是否覆盖已有工具
        """
        # 如果工具已注册但没有函数实现，则添加函数实现
        if tool_id in self._tools:
            if tool_id not in self._functions:
                # 元数据已存在，只添加函数实现
                self._functions[tool_id] = func
                logger.debug(f"为已注册工具添加函数实现: {tool_id}")
                return
            elif not override:
                logger.warning(f"工具 '{tool_id}' 已注册，跳过")
                return

        # 创建元数据
        metadata = ToolMetadata(
            id=tool_id,
            name=name,
            description=description,
            category=category,
            is_online=is_online,
        )

        self._tools[tool_id] = metadata
        self._functions[tool_id] = func

        logger.debug(f"注册工具函数: {tool_id} (legacy={is_legacy})")

    def get_function(self, tool_id: str) -> Optional[Callable]:
        """获取工具的函数实现"""
        return self._functions.get(tool_id)

    def get_langchain_tool(self, tool_id: str):
        """
        获取 LangChain 格式的工具

        Returns:
            LangChain Tool 对象，如果工具未注册或无函数实现则返回 None
        """
        if tool_id not in self._tools:
            return None

        func = self._functions.get(tool_id)
        if func is None:
            return None

        # 如果已经是 LangChain tool，直接返回
        if hasattr(func, 'invoke') or hasattr(func, 'run'):
            return func

        # 否则包装为 LangChain tool
        from langchain_core.tools import StructuredTool

        metadata = self._tools[tool_id]

        # 使用 StructuredTool.from_function 来创建工具
        # 这样可以显式指定 name 和 description
        lc_tool = StructuredTool.from_function(
            func=func,
            name=tool_id,
            description=metadata.description or func.__doc__ or "No description available"
        )

        return lc_tool

    def get_langchain_tools(self, tool_ids: List[str]) -> List:
        """批量获取 LangChain 格式的工具"""
        tools = []
        for tool_id in tool_ids:
            tool = self.get_langchain_tool(tool_id)
            if tool:
                tools.append(tool)
        return tools


# 全局注册表实例
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry

