class _FakeToolAgentBindingsCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, query, sort=None):
        agent_id = query.get("agent_id")
        docs = [
            doc
            for doc in self._docs
            if doc.get("agent_id") == agent_id and doc.get("is_active", True) is not False
        ]
        if sort:
            for field_name, direction in reversed(sort):
                docs.sort(key=lambda item: item.get(field_name, 0), reverse=direction < 0)
        return docs


class _FakeDb:
    def __init__(self, docs):
        self.tool_agent_bindings = _FakeToolAgentBindingsCollection(docs)


def test_binding_manager_rewrites_news_analyst_v2_legacy_bindings():
    from core.config.binding_manager import BindingManager

    manager = BindingManager()
    manager.set_database(
        _FakeDb(
            [
                {"agent_id": "news_analyst_v2", "tool_id": "get_weather", "priority": 200},
                {"agent_id": "news_analyst_v2", "tool_id": "get_stock_news_unified", "priority": 100},
            ]
        )
    )

    try:
        tools = manager.get_tools_for_agent("news_analyst_v2")
    finally:
        manager.set_database(None)

    assert tools == [
        "get_stock_news_headlines_unified",
        "get_stock_news_details_unified",
    ]


def test_binding_manager_preserves_valid_extra_tools_while_migrating_news_bindings():
    from core.config.binding_manager import BindingManager

    manager = BindingManager()
    manager.set_database(
        _FakeDb(
            [
                {"agent_id": "news_analyst_v2", "tool_id": "get_stock_news_headlines_unified", "priority": 300},
                {"agent_id": "news_analyst_v2", "tool_id": "get_stock_news_unified", "priority": 100},
            ]
        )
    )

    try:
        tools = manager.get_tools_for_agent("news_analyst_v2")
    finally:
        manager.set_database(None)

    assert tools == [
        "get_stock_news_headlines_unified",
        "get_stock_news_details_unified",
    ]