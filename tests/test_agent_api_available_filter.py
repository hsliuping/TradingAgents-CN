from core.agents.config import AgentCategory, AgentMetadata, LicenseTier
from core.api.agent_api import AgentAPI


class _StubRegistry:
    def __init__(self, items):
        self._items = items

    def list_all(self):
        return list(self._items)

    def list_by_category(self, category):
        category_value = category.value if hasattr(category, 'value') else category
        return [
            item for item in self._items
            if (item.category.value if hasattr(item.category, 'value') else item.category) == category_value
        ]


def test_list_available_for_tier_excludes_unmaintained_agents() -> None:
    legacy_agent = AgentMetadata(
        id="market_analyst",
        name="市场分析师",
        description="legacy",
        category=AgentCategory.ANALYST,
        version="1.0.0",
        license_tier=LicenseTier.FREE,
    )
    free_v2_agent = AgentMetadata(
        id="market_analyst_v2",
        name="市场分析师 v2.0",
        description="maintained free",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
    )
    pro_v2_agent = AgentMetadata(
        id="sector_analyst_v2",
        name="板块分析师 v2.0",
        description="maintained pro",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.PRO,
    )

    api = AgentAPI.__new__(AgentAPI)
    api._registry = _StubRegistry([legacy_agent, free_v2_agent, pro_v2_agent])

    agents = api.list_available_for_tier("free")
    agent_ids = [agent["id"] for agent in agents]

    assert agent_ids == ["market_analyst_v2", "sector_analyst_v2"]
    assert all(agent["maintenance_status"] == "maintained" for agent in agents)

    free_agent = next(agent for agent in agents if agent["id"] == "market_analyst_v2")
    pro_agent = next(agent for agent in agents if agent["id"] == "sector_analyst_v2")

    assert free_agent["is_available"] is True
    assert "locked_reason" not in free_agent
    assert pro_agent["is_available"] is False
    assert pro_agent["locked_reason"] == "需要高级学员权限"


def test_get_categories_counts_only_maintained_agents() -> None:
    legacy_agent = AgentMetadata(
        id="market_analyst",
        name="市场分析师",
        description="legacy",
        category=AgentCategory.ANALYST,
        version="1.0.0",
        license_tier=LicenseTier.FREE,
    )
    maintained_analyst = AgentMetadata(
        id="market_analyst_v2",
        name="市场分析师 v2.0",
        description="maintained",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
    )
    maintained_manager = AgentMetadata(
        id="research_manager_v2",
        name="研究经理 v2.0",
        description="maintained",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
    )

    api = AgentAPI.__new__(AgentAPI)
    api._registry = _StubRegistry([legacy_agent, maintained_analyst, maintained_manager])

    categories = {item["id"]: item["count"] for item in api.get_categories()}

    assert categories["analyst"] == 1
    assert categories["manager"] == 1