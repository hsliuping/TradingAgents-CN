# tradingagents/core/engine/memory_provider.py
"""
Memory 提供者

管理各类 Agent 所需的 Memory 实例：
- bull_memory: 多头研究员记忆
- bear_memory: 空头研究员记忆
- trader_memory: 交易员记忆
- invest_judge_memory: 研究经理记忆
- risk_manager_memory: 风控经理记忆

配置来源:
- memory_enabled: 是否启用记忆功能
- llm_provider: 使用的 LLM 提供商（影响嵌入模型选择）
"""

from typing import Any, Dict, Optional

from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")


# Memory 名称到 Agent ID 的映射
# 同时支持 memory_name 和 agent_id 作为 key
MEMORY_AGENT_MAPPING = {
    "bull_memory": ["bull_researcher"],
    "bear_memory": ["bear_researcher"],
    "trader_memory": ["trader"],
    "invest_judge_memory": ["research_manager"],
    "risk_manager_memory": ["risk_manager"],
    "risk_memory": ["risk_manager"],  # 别名
}


class MemoryProvider:
    """
    Memory 提供者
    
    管理和创建各类 Memory 实例，支持懒加载。
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        memory_enabled: bool = True
    ):
        """
        初始化 Memory 提供者
        
        Args:
            config: 配置字典，包含 llm_provider, backend_url 等
            memory_enabled: 是否启用记忆功能
        """
        self.config = config or self._get_default_config()
        self.memory_enabled = memory_enabled
        self._memories: Dict[str, Any] = {}
        
        if memory_enabled:
            logger.info("🧠 [MemoryProvider] Memory 功能已启用")
        else:
            logger.info("⚠️ [MemoryProvider] Memory 功能已禁用")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        try:
            from tradingagents.default_config import DEFAULT_CONFIG
            return DEFAULT_CONFIG.copy()
        except ImportError:
            return {
                "llm_provider": "deepseek",
                "backend_url": "https://api.deepseek.com",
                "memory_enabled": True
            }
    
    def get_memory(self, memory_name: str) -> Optional[Any]:
        """
        获取指定的 Memory 实例
        
        Args:
            memory_name: Memory 名称，如 "bull_memory"
            
        Returns:
            FinancialSituationMemory 实例或 None
        """
        if not self.memory_enabled:
            return None
            
        if memory_name not in self._memories:
            self._memories[memory_name] = self._create_memory(memory_name)
        
        return self._memories[memory_name]
    
    def _create_memory(self, memory_name: str) -> Optional[Any]:
        """创建 Memory 实例"""
        if not self.memory_enabled:
            return None
            
        try:
            from tradingagents.agents.utils.memory import FinancialSituationMemory
            memory = FinancialSituationMemory(memory_name, self.config)
            logger.debug(f"🧠 [MemoryProvider] 创建 Memory: {memory_name}")
            return memory
        except Exception as e:
            logger.warning(f"⚠️ [MemoryProvider] 创建 Memory 失败 {memory_name}: {e}")
            return None
    
    def get_memory_config(self) -> Dict[str, Any]:
        """
        获取所有 Agent 的 Memory 配置

        Returns:
            字典，key 为 agent_id 和 memory_name，value 为对应的 Memory 实例
        """
        memory_config = {}

        for memory_name, agent_ids in MEMORY_AGENT_MAPPING.items():
            memory = self.get_memory(memory_name)
            # 同时用 memory_name 和 agent_id 作为 key
            memory_config[memory_name] = memory
            for agent_id in agent_ids:
                memory_config[agent_id] = memory

        # 设置默认 memory
        memory_config["default"] = self.get_memory("invest_judge_memory")

        return memory_config
    
    def get_memory_by_agent(self, agent_id: str) -> Optional[Any]:
        """
        根据 Agent ID 获取对应的 Memory
        
        Args:
            agent_id: Agent ID，如 "bull_researcher"
            
        Returns:
            对应的 Memory 实例或 None
        """
        for memory_name, agent_ids in MEMORY_AGENT_MAPPING.items():
            if agent_id in agent_ids:
                return self.get_memory(memory_name)
        
        # 默认返回 invest_judge_memory
        return self.get_memory("invest_judge_memory")
    
    def clear_memories(self):
        """清除所有 Memory 缓存"""
        self._memories.clear()
        logger.debug("🧹 [MemoryProvider] Memory 缓存已清除")

