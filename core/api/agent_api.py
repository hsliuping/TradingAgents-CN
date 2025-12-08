"""
智能体 API

提供智能体的查询和管理接口
"""

from typing import Any, Dict, List, Optional

from ..agents import (
    AgentRegistry,
    AgentFactory,
    AgentMetadata,
    AgentCategory,
    LicenseTier,
    get_registry,
)
from ..licensing import LicenseManager


class AgentAPI:
    """
    智能体 API
    
    提供智能体的查询、过滤和元数据获取功能
    """
    
    def __init__(self):
        self._registry = get_registry()
        self._factory = AgentFactory(self._registry)
        self._license_manager = LicenseManager()
    
    def list_all(self) -> List[Dict[str, Any]]:
        """
        列出所有智能体
        
        Returns:
            智能体元数据列表
        """
        agents = []
        for metadata in self._registry.list_all():
            agents.append(self._metadata_to_dict(metadata))
        return agents
    
    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        按类别列出智能体
        
        Args:
            category: 类别名称 (analyst/researcher/trader/risk/manager)
            
        Returns:
            智能体元数据列表
        """
        try:
            cat = AgentCategory(category)
        except ValueError:
            return []
        
        agents = []
        for metadata in self._registry.list_by_category(cat):
            agents.append(self._metadata_to_dict(metadata))
        return agents
    
    def list_available(self) -> List[Dict[str, Any]]:
        """
        列出当前许可证可用的智能体（使用本地许可证）

        Returns:
            可用的智能体元数据列表
        """
        current_tier = self._license_manager.tier
        return self.list_available_for_tier(current_tier.value if hasattr(current_tier, 'value') else current_tier)

    def list_available_for_tier(self, tier_str: str) -> List[Dict[str, Any]]:
        """
        列出指定许可证级别可用的智能体

        Args:
            tier_str: 许可证级别字符串 ("free", "basic", "pro", "enterprise")

        Returns:
            可用的智能体元数据列表
        """
        # 转换为 LicenseTier
        try:
            tier = LicenseTier(tier_str)
        except ValueError:
            tier = LicenseTier.FREE

        agents = []

        for metadata in self._registry.list_available(tier):
            agent_dict = self._metadata_to_dict(metadata)
            agent_dict["is_available"] = True
            agents.append(agent_dict)

        # 添加不可用的智能体（标记为锁定）
        all_agents = self._registry.list_all()
        available_ids = {a["id"] for a in agents}

        for metadata in all_agents:
            if metadata.id not in available_ids:
                agent_dict = self._metadata_to_dict(metadata)
                agent_dict["is_available"] = False
                tier_value = metadata.license_tier.value if hasattr(metadata.license_tier, 'value') else metadata.license_tier
                agent_dict["locked_reason"] = f"需要 {tier_value} 或更高级别许可证"
                agents.append(agent_dict)

        return agents
    
    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        获取智能体详情
        
        Args:
            agent_id: 智能体 ID
            
        Returns:
            智能体元数据，如果不存在返回 None
        """
        metadata = self._registry.get_metadata(agent_id)
        if metadata is None:
            return None
        
        agent_dict = self._metadata_to_dict(metadata)
        
        # 添加可用性信息
        current_tier = self._license_manager.tier
        tier_order = [LicenseTier.FREE, LicenseTier.BASIC, LicenseTier.PRO, LicenseTier.ENTERPRISE]
        current_index = tier_order.index(current_tier)
        required_index = tier_order.index(metadata.license_tier)
        
        agent_dict["is_available"] = current_index >= required_index
        agent_dict["is_implemented"] = self._registry.is_registered(agent_id)
        
        return agent_dict
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """
        获取所有类别
        
        Returns:
            类别列表
        """
        categories = []
        for cat in AgentCategory:
            count = len(self._registry.list_by_category(cat))
            categories.append({
                "id": cat.value,
                "name": self._get_category_name(cat),
                "count": count,
            })
        return categories
    
    def _metadata_to_dict(self, metadata: AgentMetadata) -> Dict[str, Any]:
        """将元数据转换为字典"""
        # 处理枚举值：可能是枚举类型也可能是字符串（use_enum_values=True）
        category = metadata.category.value if hasattr(metadata.category, 'value') else metadata.category
        license_tier = metadata.license_tier.value if hasattr(metadata.license_tier, 'value') else metadata.license_tier

        return {
            "id": metadata.id,
            "name": metadata.name,
            "description": metadata.description,
            "category": category,
            "license_tier": license_tier,
            "inputs": metadata.inputs,
            "outputs": metadata.outputs,
            "icon": metadata.icon,
            "color": metadata.color,
            "tags": metadata.tags,
        }
    
    def _get_category_name(self, category: AgentCategory) -> str:
        """获取类别的中文名称"""
        names = {
            AgentCategory.ANALYST: "分析师",
            AgentCategory.RESEARCHER: "研究员",
            AgentCategory.TRADER: "交易员",
            AgentCategory.RISK: "风险管理",
            AgentCategory.MANAGER: "管理者",
        }
        return names.get(category, category.value)

