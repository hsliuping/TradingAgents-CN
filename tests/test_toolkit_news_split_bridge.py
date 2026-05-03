def test_toolkit_exposes_split_news_tools_for_legacy_workflow():
    from tradingagents.agents.utils.agent_utils import Toolkit

    toolkit = Toolkit()

    assert hasattr(toolkit, "get_stock_news_headlines_unified")
    assert hasattr(toolkit, "get_stock_news_details_unified")
    assert hasattr(toolkit.get_stock_news_headlines_unified, "invoke")
    assert hasattr(toolkit.get_stock_news_details_unified, "invoke")