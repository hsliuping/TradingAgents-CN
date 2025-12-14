"""
工具配置管理器

管理工具的运行时配置和状态
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ToolConfigManager:
    """
    工具配置管理器
    
    管理：
    1. 工具的启用/禁用状态
    2. 工具的运行时配置（timeout, retry, cache_ttl）
    3. 工具的参数定义
    4. 工具的元数据
    
    优先级：数据库配置 > 代码默认配置
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._db = None
        self._cache = {}  # tool_id -> config
        self._cache_ttl = 300  # 5分钟缓存
        self._cache_time = {}
        self._initialized = True
    
    def set_database(self, db):
        """设置数据库连接"""
        self._db = db
        self._clear_cache()
    
    def _clear_cache(self):
        """清空缓存"""
        self._cache = {}
        self._cache_time = {}
    
    def _is_cache_valid(self, tool_id: str) -> bool:
        """检查缓存是否有效"""
        if tool_id not in self._cache_time:
            return False
        elapsed = (datetime.utcnow() - self._cache_time[tool_id]).total_seconds()
        return elapsed < self._cache_ttl
    
    def get_tool_config(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工具配置
        
        Args:
            tool_id: 工具ID
            
        Returns:
            工具配置字典，包含：
            - enabled: 是否启用
            - config: 运行时配置（timeout, retry_count, cache_ttl）
            - parameters: 参数定义
            - metadata: 元数据
        """
        # 检查缓存
        if tool_id in self._cache and self._is_cache_valid(tool_id):
            return self._cache[tool_id]
        
        config = None
        
        # 从数据库加载
        if self._db is not None:
            try:
                config = self._db.tool_configs.find_one({"tool_id": tool_id})
                if config:
                    # 移除 MongoDB 的 _id 字段
                    config.pop("_id", None)
            except Exception as e:
                logger.warning(f"从数据库加载工具配置失败: {e}")
        
        # 如果数据库没有，使用默认配置
        if config is None:
            config = self._get_default_tool_config(tool_id)
        
        # 更新缓存
        if config:
            self._cache[tool_id] = config
            self._cache_time[tool_id] = datetime.utcnow()
        
        return config
    
    def _get_default_tool_config(self, tool_id: str) -> Dict[str, Any]:
        """获取工具的默认配置"""
        from core.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        tool = registry.get_tool(tool_id)
        
        if tool is None:
            return {
                "tool_id": tool_id,
                "enabled": False,
                "config": {},
                "parameters": {},
                "metadata": {}
            }
        
        # 从工具类获取默认配置
        return {
            "tool_id": tool_id,
            "name": getattr(tool, "name", tool_id),
            "description": getattr(tool, "description", ""),
            "category": getattr(tool, "category", "general"),
            "enabled": True,
            "config": {
                "timeout": getattr(tool, "timeout", 30),
                "retry_count": getattr(tool, "retry_count", 3),
                "cache_ttl": getattr(tool, "cache_ttl", 300),
            },
            "parameters": getattr(tool, "args_schema", {}).schema() if hasattr(tool, "args_schema") else {},
            "metadata": {
                "is_builtin": True,
                "version": getattr(tool, "version", "1.0.0"),
            }
        }
    
    def save_tool_config(self, config: Dict[str, Any]) -> bool:
        """
        保存工具配置到数据库
        
        Args:
            config: 工具配置字典
            
        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        tool_id = config.get("tool_id")
        if not tool_id:
            logger.error("配置缺少 tool_id")
            return False

        try:
            config["updated_at"] = datetime.utcnow().isoformat()
            self._db.tool_configs.update_one(
                {"tool_id": tool_id},
                {
                    "$set": config,
                    "$setOnInsert": {"created_at": datetime.utcnow().isoformat()}
                },
                upsert=True
            )

            # 清除缓存
            if tool_id in self._cache:
                del self._cache[tool_id]
            if tool_id in self._cache_time:
                del self._cache_time[tool_id]

            logger.info(f"✅ 工具配置已保存: {tool_id}")
            return True
        except Exception as e:
            logger.error(f"保存工具配置失败: {e}")
            return False

    def is_tool_enabled(self, tool_id: str) -> bool:
        """检查工具是否启用"""
        config = self.get_tool_config(tool_id)
        return config.get("enabled", False) if config else False

    def enable_tool(self, tool_id: str) -> bool:
        """启用工具"""
        return self._set_tool_enabled(tool_id, True)

    def disable_tool(self, tool_id: str) -> bool:
        """禁用工具"""
        return self._set_tool_enabled(tool_id, False)

    def _set_tool_enabled(self, tool_id: str, enabled: bool) -> bool:
        """设置工具启用状态"""
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.tool_configs.update_one(
                {"tool_id": tool_id},
                {
                    "$set": {
                        "enabled": enabled,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if tool_id in self._cache:
                del self._cache[tool_id]

            logger.info(f"✅ 工具 {tool_id} 已{'启用' if enabled else '禁用'}")
            return True
        except Exception as e:
            logger.error(f"设置工具状态失败: {e}")
            return False

    def get_all_tool_configs(self, category: Optional[str] = None, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有工具配置

        Args:
            category: 可选，按分类筛选
            enabled_only: 是否只返回启用的工具

        Returns:
            工具配置列表
        """
        result = []

        if self._db is not None:
            try:
                query = {}
                if category:
                    query["category"] = category
                if enabled_only:
                    query["enabled"] = True

                result = list(self._db.tool_configs.find(query))
                # 移除 _id 字段
                for config in result:
                    config.pop("_id", None)
            except Exception as e:
                logger.warning(f"获取工具配置列表失败: {e}")

        # 如果数据库为空，从代码加载默认配置
        if not result:
            from core.tools.registry import ToolRegistry
            registry = ToolRegistry()
            for tool_id in registry.list_tools():
                config = self._get_default_tool_config(tool_id)
                if category and config.get("category") != category:
                    continue
                if enabled_only and not config.get("enabled", False):
                    continue
                result.append(config)

        return result

    def update_tool_runtime_config(self, tool_id: str, runtime_config: Dict[str, Any]) -> bool:
        """
        更新工具的运行时配置

        Args:
            tool_id: 工具ID
            runtime_config: 运行时配置（timeout, retry_count, cache_ttl等）

        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.tool_configs.update_one(
                {"tool_id": tool_id},
                {
                    "$set": {
                        "config": runtime_config,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if tool_id in self._cache:
                del self._cache[tool_id]

            logger.info(f"✅ 工具运行时配置已更新: {tool_id}")
            return True
        except Exception as e:
            logger.error(f"更新工具运行时配置失败: {e}")
            return False


