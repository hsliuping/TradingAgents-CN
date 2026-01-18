"""
Agent 配置管理器

管理 Agent 的运行时配置和状态
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentConfigManager:
    """
    Agent 配置管理器
    
    管理：
    1. Agent 的启用/禁用状态
    2. Agent 的执行配置（max_iterations, timeout, temperature）
    3. Agent 的提示词模板配置
    4. Agent 的默认工具列表
    
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
        self._cache = {}  # agent_id -> config
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
    
    def _is_cache_valid(self, agent_id: str) -> bool:
        """检查缓存是否有效"""
        if agent_id not in self._cache_time:
            return False
        elapsed = (datetime.utcnow() - self._cache_time[agent_id]).total_seconds()
        return elapsed < self._cache_ttl
    
    def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Agent 配置
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent 配置字典，包含：
            - enabled: 是否启用
            - config: 执行配置（max_iterations, timeout, temperature）
            - prompt_template_type: 提示词模板类型
            - prompt_template_name: 提示词模板名称
            - default_tools: 默认工具列表
            - required_tools: 必需工具列表
        """
        # 检查缓存
        if agent_id in self._cache and self._is_cache_valid(agent_id):
            return self._cache[agent_id]
        
        config = None
        
        # 从数据库加载
        if self._db is not None:
            try:
                config = self._db.agent_configs.find_one({"agent_id": agent_id})
                if config:
                    # 移除 MongoDB 的 _id 字段
                    config.pop("_id", None)
            except Exception as e:
                logger.warning(f"从数据库加载 Agent 配置失败: {e}")
        
        # 如果数据库没有，使用默认配置
        if config is None:
            config = self._get_default_agent_config(agent_id)
        
        # 更新缓存
        if config:
            self._cache[agent_id] = config
            self._cache_time[agent_id] = datetime.utcnow()
        
        return config
    
    def _get_default_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取 Agent 的默认配置"""
        from core.agents.registry import AgentRegistry
        
        registry = AgentRegistry()
        metadata = registry.get_metadata(agent_id)
        
        if metadata is None:
            return None
        
        # 🔥 根据 Agent 类型设置不同的默认温度
        # 辩论 Agent：0.6（需要创造性和多样性）
        # 数值计算和评估 Agent：0.1（需要高精度）
        # 其他 Agent：0.2（平衡准确性和灵活性）
        default_temperature = self._get_default_temperature(agent_id)
        
        # 从 metadata 构建默认配置
        return {
            "agent_id": agent_id,
            "name": metadata.name,
            "description": metadata.description,
            "category": metadata.category.value if hasattr(metadata.category, 'value') else str(metadata.category),
            "version": metadata.version,
            "enabled": True,
            "config": {
                "max_iterations": 3,
                "timeout": 120,
                "temperature": default_temperature,  # 🔥 使用类型特定的默认温度
            },
            "prompt_template_type": metadata.category.value if hasattr(metadata.category, 'value') else "general",
            "prompt_template_name": agent_id,
            "default_tools": metadata.default_tools if metadata.default_tools else [],
            "required_tools": metadata.default_tools if metadata.default_tools else [],
            "metadata": {
                "is_builtin": True,
                "license_tier": metadata.license_tier.value if hasattr(metadata.license_tier, 'value') else "free",
            }
        }
    
    def _get_default_temperature(self, agent_id: str) -> float:
        """
        根据 Agent 类型获取默认温度

        Args:
            agent_id: Agent ID

        Returns:
            默认温度值
        """
        # 辩论 Agent（需要创造性和多样性）
        debate_agents = [
            "bull_researcher", "bear_researcher",  # 投资辩论
            "risky_analyst", "safe_analyst", "neutral_analyst",  # 风险辩论
            "risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2",  # v2.0 风险辩论
        ]
        if agent_id in debate_agents:
            logger.info(f"[Agent配置] 🌡️ {agent_id} 是辩论 Agent，设置默认温度: 0.6")
            return 0.6
        
        # 数值计算和评估 Agent（需要高精度）
        calculation_agents = [
            "risk_assessor", "risk_assessor_v2",  # 风险评估
            "position_analyst",  # 持仓分析（数值计算）
        ]
        if agent_id in calculation_agents:
            logger.info(f"[Agent配置] 🌡️ {agent_id} 是数值计算 Agent，设置默认温度: 0.1")
            return 0.1
        
        # 其他 Agent（平衡准确性和灵活性）
        logger.info(f"[Agent配置] 🌡️ {agent_id} 是标准 Agent，设置默认温度: 0.2")
        return 0.2
    
    def save_agent_config(self, config: Dict[str, Any]) -> bool:
        """
        保存 Agent 配置到数据库
        
        Args:
            config: Agent 配置字典
            
        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        agent_id = config.get("agent_id")
        if not agent_id:
            logger.error("配置缺少 agent_id")
            return False

        try:
            # 准备更新数据
            update_data = config.copy()
            update_data["updated_at"] = datetime.utcnow().isoformat()

            # 如果配置中有created_at，移除它（让$setOnInsert处理）
            created_at = update_data.pop("created_at", None)

            # 构建更新操作
            update_op = {"$set": update_data}

            # 只在插入时设置created_at
            if created_at:
                update_op["$setOnInsert"] = {"created_at": created_at}
            else:
                update_op["$setOnInsert"] = {"created_at": datetime.utcnow().isoformat()}

            self._db.agent_configs.update_one(
                {"agent_id": agent_id},
                update_op,
                upsert=True
            )

            # 清除缓存
            if agent_id in self._cache:
                del self._cache[agent_id]
            if agent_id in self._cache_time:
                del self._cache_time[agent_id]

            logger.info(f"✅ Agent 配置已保存: {agent_id}")
            return True
        except Exception as e:
            logger.error(f"保存 Agent 配置失败: {e}")
            return False

    def is_agent_enabled(self, agent_id: str) -> bool:
        """检查 Agent 是否启用"""
        config = self.get_agent_config(agent_id)
        return config.get("enabled", False) if config else False

    def enable_agent(self, agent_id: str) -> bool:
        """启用 Agent"""
        return self._set_agent_enabled(agent_id, True)

    def disable_agent(self, agent_id: str) -> bool:
        """禁用 Agent"""
        return self._set_agent_enabled(agent_id, False)

    def _set_agent_enabled(self, agent_id: str, enabled: bool) -> bool:
        """设置 Agent 启用状态"""
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.agent_configs.update_one(
                {"agent_id": agent_id},
                {
                    "$set": {
                        "enabled": enabled,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if agent_id in self._cache:
                del self._cache[agent_id]

            logger.info(f"✅ Agent {agent_id} 已{'启用' if enabled else '禁用'}")
            return True
        except Exception as e:
            logger.error(f"设置 Agent 状态失败: {e}")
            return False

    def get_all_agent_configs(self, category: Optional[str] = None, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有 Agent 配置

        Args:
            category: 可选，按分类筛选
            enabled_only: 是否只返回启用的 Agent

        Returns:
            Agent 配置列表
        """
        result = []

        if self._db is not None:
            try:
                query = {}
                if category:
                    query["category"] = category
                if enabled_only:
                    query["enabled"] = True

                result = list(self._db.agent_configs.find(query))
                # 移除 _id 字段
                for config in result:
                    config.pop("_id", None)
            except Exception as e:
                logger.warning(f"获取 Agent 配置列表失败: {e}")

        # 如果数据库为空，从代码加载默认配置
        if not result:
            from core.agents.registry import AgentRegistry
            registry = AgentRegistry()
            for metadata in registry.list_all():
                agent_id = metadata.id
                config = self._get_default_agent_config(agent_id)
                if config is None:
                    continue
                if category and config.get("category") != category:
                    continue
                if enabled_only and not config.get("enabled", False):
                    continue
                result.append(config)

        return result

    def update_agent_execution_config(self, agent_id: str, execution_config: Dict[str, Any]) -> bool:
        """
        更新 Agent 的执行配置

        Args:
            agent_id: Agent ID
            execution_config: 执行配置（max_iterations, timeout, temperature等）

        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.agent_configs.update_one(
                {"agent_id": agent_id},
                {
                    "$set": {
                        "config": execution_config,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if agent_id in self._cache:
                del self._cache[agent_id]

            logger.info(f"✅ Agent 执行配置已更新: {agent_id}")
            return True
        except Exception as e:
            logger.error(f"更新 Agent 执行配置失败: {e}")
            return False

    def update_agent_prompt_template(self, agent_id: str, template_type: str, template_name: str) -> bool:
        """
        更新 Agent 的提示词模板配置

        Args:
            agent_id: Agent ID
            template_type: 模板类型
            template_name: 模板名称

        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.agent_configs.update_one(
                {"agent_id": agent_id},
                {
                    "$set": {
                        "prompt_template_type": template_type,
                        "prompt_template_name": template_name,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if agent_id in self._cache:
                del self._cache[agent_id]

            logger.info(f"✅ Agent 提示词模板已更新: {agent_id}")
            return True
        except Exception as e:
            logger.error(f"更新 Agent 提示词模板失败: {e}")
            return False


