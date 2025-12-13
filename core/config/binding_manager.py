"""
绑定管理器

管理工具-Agent、Agent-工作流之间的绑定关系
支持从数据库和代码配置两种方式加载
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BindingManager:
    """
    统一绑定管理器
    
    管理：
    1. 工具 -> Agent 的绑定
    2. Agent -> 工作流的绑定
    3. Agent 的 IO 定义
    
    优先级：数据库配置 > 代码配置
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
        self._cache = {
            "tool_agent": {},      # agent_id -> [tool_id, ...]
            "agent_workflow": {},  # workflow_id -> [agent_id, ...]
            "agent_io": {},        # agent_id -> AgentIODefinition
        }
        self._cache_ttl = 300  # 5分钟缓存
        self._cache_time = {}
        self._initialized = True
    
    def set_database(self, db):
        """设置数据库连接"""
        self._db = db
        self._clear_cache()
    
    def _clear_cache(self):
        """清空缓存"""
        for key in self._cache:
            self._cache[key] = {}
        self._cache_time = {}
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._cache_time:
            return False
        elapsed = (datetime.utcnow() - self._cache_time[cache_key]).total_seconds()
        return elapsed < self._cache_ttl
    
    # ==================== 工具-Agent 绑定 ====================
    
    def get_tools_for_agent(self, agent_id: str) -> List[str]:
        """
        获取 Agent 绑定的工具列表
        
        Args:
            agent_id: Agent ID
            
        Returns:
            工具ID列表
        """
        cache_key = f"tool_agent:{agent_id}"
        
        # 检查缓存
        if agent_id in self._cache["tool_agent"] and self._is_cache_valid(cache_key):
            return self._cache["tool_agent"][agent_id]
        
        tool_ids = []
        
        # 从数据库加载
        if self._db is not None:
            try:
                bindings = list(self._db.tool_agent_bindings.find(
                    {"agent_id": agent_id, "is_active": {"$ne": False}},
                    sort=[("priority", -1)]
                ))
                tool_ids = [b["tool_id"] for b in bindings]
            except Exception as e:
                logger.warning(f"从数据库加载工具绑定失败: {e}")
        
        # 如果数据库没有，从代码配置加载
        if not tool_ids:
            tool_ids = self._get_default_tools_for_agent(agent_id)
        
        # 更新缓存
        self._cache["tool_agent"][agent_id] = tool_ids
        self._cache_time[cache_key] = datetime.utcnow()
        
        return tool_ids
    
    def _get_default_tools_for_agent(self, agent_id: str) -> List[str]:
        """从代码配置获取默认工具列表"""
        from core.agents.config import BUILTIN_AGENTS

        if agent_id in BUILTIN_AGENTS:
            agent = BUILTIN_AGENTS[agent_id]
            return agent.default_tools if hasattr(agent, 'default_tools') else []
        return []
    
    def bind_tool(self, agent_id: str, tool_id: str, priority: int = 0) -> bool:
        """
        绑定工具到 Agent
        
        Args:
            agent_id: Agent ID
            tool_id: 工具 ID
            priority: 优先级（越大越优先）
            
        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接，无法绑定工具")
            return False
        
        try:
            self._db.tool_agent_bindings.update_one(
                {"agent_id": agent_id, "tool_id": tool_id},
                {
                    "$set": {
                        "agent_id": agent_id,
                        "tool_id": tool_id,
                        "priority": priority,
                        "is_active": True,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow().isoformat(),
                    }
                },
                upsert=True
            )
            
            # 清除缓存
            cache_key = f"tool_agent:{agent_id}"
            if agent_id in self._cache["tool_agent"]:
                del self._cache["tool_agent"][agent_id]
            if cache_key in self._cache_time:
                del self._cache_time[cache_key]
            
            return True
        except Exception as e:
            logger.error(f"绑定工具失败: {e}")
            return False
    
    def unbind_tool(self, agent_id: str, tool_id: str) -> bool:
        """解绑工具"""
        if self._db is None:
            return False

        try:
            self._db.tool_agent_bindings.update_one(
                {"agent_id": agent_id, "tool_id": tool_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow().isoformat()}}
            )

            # 清除缓存
            if agent_id in self._cache["tool_agent"]:
                del self._cache["tool_agent"][agent_id]

            return True
        except Exception as e:
            logger.error(f"解绑工具失败: {e}")
            return False

    # ==================== Agent-工作流绑定 ====================

    def get_agents_for_workflow(self, workflow_id: str) -> List[str]:
        """
        获取工作流包含的 Agent 列表

        Args:
            workflow_id: 工作流 ID

        Returns:
            Agent ID 列表（按顺序）
        """
        cache_key = f"agent_workflow:{workflow_id}"

        if workflow_id in self._cache["agent_workflow"] and self._is_cache_valid(cache_key):
            return self._cache["agent_workflow"][workflow_id]

        agent_ids = []

        if self._db is not None:
            try:
                bindings = list(self._db.agent_workflow_bindings.find(
                    {"workflow_id": workflow_id, "is_active": {"$ne": False}},
                    sort=[("order", 1)]
                ))
                agent_ids = [b["agent_id"] for b in bindings]
            except Exception as e:
                logger.warning(f"从数据库加载Agent绑定失败: {e}")

        # 更新缓存
        self._cache["agent_workflow"][workflow_id] = agent_ids
        self._cache_time[cache_key] = datetime.utcnow()

        return agent_ids

    def bind_agent(self, workflow_id: str, agent_id: str, order: int = 0) -> bool:
        """绑定 Agent 到工作流"""
        if self._db is None:
            logger.error("数据库未连接，无法绑定Agent")
            return False

        try:
            self._db.agent_workflow_bindings.update_one(
                {"workflow_id": workflow_id, "agent_id": agent_id},
                {
                    "$set": {
                        "workflow_id": workflow_id,
                        "agent_id": agent_id,
                        "order": order,
                        "is_active": True,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow().isoformat(),
                    }
                },
                upsert=True
            )

            if workflow_id in self._cache["agent_workflow"]:
                del self._cache["agent_workflow"][workflow_id]

            return True
        except Exception as e:
            logger.error(f"绑定Agent失败: {e}")
            return False

    # ==================== 工作流级别工具覆盖 ====================

    def get_tools_for_workflow_agent(
        self, workflow_id: str, agent_id: str
    ) -> List[str]:
        """
        获取工作流中特定 Agent 的工具列表

        优先级：工作流级别覆盖 > Agent 默认绑定

        Args:
            workflow_id: 工作流 ID
            agent_id: Agent ID

        Returns:
            工具 ID 列表
        """
        # 先检查工作流级别的覆盖
        if self._db is not None:
            try:
                override = self._db.agent_workflow_bindings.find_one(
                    {"workflow_id": workflow_id, "agent_id": agent_id}
                )
                if override and override.get("tool_overrides"):
                    return override["tool_overrides"]
            except Exception as e:
                logger.warning(f"获取工作流工具覆盖失败: {e}")

        # 回退到 Agent 默认绑定
        return self.get_tools_for_agent(agent_id)

    # ==================== Agent IO 定义 ====================

    def get_agent_io_definition(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Agent 的输入输出定义

        Args:
            agent_id: Agent ID

        Returns:
            IO 定义字典，包含 inputs, outputs, reads_from
        """
        cache_key = f"agent_io:{agent_id}"

        if agent_id in self._cache["agent_io"] and self._is_cache_valid(cache_key):
            return self._cache["agent_io"][agent_id]

        io_def = None

        # 从数据库加载
        if self._db is not None:
            try:
                io_def = self._db.agent_io_definitions.find_one({"agent_id": agent_id})
            except Exception as e:
                logger.warning(f"从数据库加载IO定义失败: {e}")

        # 从代码配置加载
        if io_def is None:
            io_def = self._get_default_io_definition(agent_id)

        # 更新缓存
        if io_def:
            self._cache["agent_io"][agent_id] = io_def
            self._cache_time[cache_key] = datetime.utcnow()

        return io_def

    def _get_default_io_definition(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """从代码配置获取默认 IO 定义"""
        from core.agents.config import BUILTIN_AGENTS

        if agent_id in BUILTIN_AGENTS:
            agent = BUILTIN_AGENTS[agent_id]
            # 将 Pydantic 模型转换为字典
            inputs = [inp.model_dump() for inp in agent.inputs] if hasattr(agent, 'inputs') else []
            outputs = [out.model_dump() for out in agent.outputs] if hasattr(agent, 'outputs') else []
            reads_from = agent.reads_from if hasattr(agent, 'reads_from') else []

            return {
                "agent_id": agent_id,
                "inputs": inputs,
                "outputs": outputs,
                "reads_from": reads_from,
            }
        return None

    def save_agent_io_definition(self, io_def: Dict[str, Any]) -> bool:
        """保存 Agent IO 定义到数据库"""
        if self._db is None:
            logger.error("数据库未连接")
            return False

        agent_id = io_def.get("agent_id")
        if not agent_id:
            logger.error("IO定义缺少agent_id")
            return False

        try:
            io_def["updated_at"] = datetime.utcnow().isoformat()
            self._db.agent_io_definitions.update_one(
                {"agent_id": agent_id},
                {
                    "$set": io_def,
                    "$setOnInsert": {"created_at": datetime.utcnow().isoformat()}
                },
                upsert=True
            )

            # 清除缓存
            if agent_id in self._cache["agent_io"]:
                del self._cache["agent_io"][agent_id]

            return True
        except Exception as e:
            logger.error(f"保存IO定义失败: {e}")
            return False

    # ==================== 批量操作 ====================

    def get_all_agent_io_definitions(self) -> List[Dict[str, Any]]:
        """获取所有 Agent 的 IO 定义"""
        result = []

        if self._db is not None:
            try:
                result = list(self._db.agent_io_definitions.find({}))
            except Exception as e:
                logger.warning(f"获取所有IO定义失败: {e}")

        # 合并代码配置中的定义
        from core.agents.config import BUILTIN_AGENTS
        db_agent_ids = {r["agent_id"] for r in result}

        for agent_id, agent in BUILTIN_AGENTS.items():
            if agent_id not in db_agent_ids:
                inputs = [inp.model_dump() for inp in agent.inputs] if hasattr(agent, 'inputs') else []
                outputs = [out.model_dump() for out in agent.outputs] if hasattr(agent, 'outputs') else []
                reads_from = agent.reads_from if hasattr(agent, 'reads_from') else []

                result.append({
                    "agent_id": agent_id,
                    "inputs": inputs,
                    "outputs": outputs,
                    "reads_from": reads_from,
                    "source": "builtin",
                })

        return result

