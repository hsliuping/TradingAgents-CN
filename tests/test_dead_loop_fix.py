"""Tests for dead loop risk fixes (AIT-25).

Covers:
- RISK 1: Google News pagination MAX_PAGES limit
- RISK 2: make_request raises after exhausting retries
- RISK 3: Message count safety check in conditional_logic

These tests verify the FIX is in place. They import modules only after
dependencies are available; if the import chain is broken they are skipped.
"""

import pytest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── RISK 1: Google News pagination MAX_PAGES ────────────────────────────────

class TestGoogleNewsMaxPages:
    """Verify getNewsData has a MAX_PAGES guard."""

    def test_max_pages_constant_exists(self):
        """google_news module must define a MAX_PAGES constant."""
        try:
            import tradingagents.dataflows.news.google_news as gn
        except ImportError:
            pytest.skip("Dependencies not available")

        assert hasattr(gn, "MAX_PAGES"), "google_news.py must define MAX_PAGES"
        assert isinstance(gn.MAX_PAGES, int), "MAX_PAGES must be an integer"
        assert gn.MAX_PAGES > 0, "MAX_PAGES must be positive"
        assert gn.MAX_PAGES <= 100, "MAX_PAGES should be <= 100 to prevent long hangs"

    def test_loop_uses_max_pages(self):
        """The getNewsData source must reference MAX_PAGES in its loop guard."""
        try:
            import tradingagents.dataflows.news.google_news as gn
        except ImportError:
            pytest.skip("Dependencies not available")

        import inspect
        source = inspect.getsource(gn.getNewsData)
        assert "MAX_PAGES" in source, "getNewsData must use MAX_PAGES to bound the loop"


# ─── RISK 2: make_request raises after exhausting retries ────────────────────

class TestMakeRequestRaisesOnExhaustion:
    """Verify make_request is configured to raise (not silently return) on exhaustion."""

    def test_retry_decorator_has_reraise(self):
        """make_request's retry decorator should have reraise=True so exhausted
        retries raise the last exception instead of silently returning a bad response."""
        try:
            import tradingagents.dataflows.news.google_news as gn
        except ImportError:
            pytest.skip("Dependencies not available")

        import inspect
        source = inspect.getsource(gn.make_request)
        # The @retry decorator should include reraise=True
        # We check the module source for the make_request function definition
        module_source = inspect.getsource(gn)
        # Find the retry decorator block before make_request
        make_request_idx = module_source.find("def make_request")
        if make_request_idx == -1:
            pytest.skip("Cannot find make_request in source")

        # Look at the decorator block (the ~200 chars before def make_request)
        decorator_block = module_source[max(0, make_request_idx - 500):make_request_idx]
        assert "reraise" in decorator_block, (
            "make_request's @retry decorator must include reraise=True to ensure "
            "exceptions are raised after retries are exhausted"
        )


# ─── RISK 3: Message count safety check in conditional_logic ─────────────────

class TestMessageCountSafetyCheck:
    """Verify analyst loops exit when message count exceeds a safety threshold."""

    def _make_state(self, tool_call_count=0, messages_count=5, tool_calls=True, report=""):
        """Build a minimal AgentState-like dict for testing."""
        from unittest.mock import MagicMock

        last_msg = MagicMock()
        last_msg.tool_calls = [{"name": "test_tool", "id": "tc1", "args": {}}] if tool_calls else []
        last_msg.content = "test content"

        messages = [MagicMock() for _ in range(messages_count)]

        state = {
            "messages": messages,
            "market_tool_call_count": tool_call_count,
            "sentiment_tool_call_count": tool_call_count,
            "news_tool_call_count": tool_call_count,
            "fundamentals_tool_call_count": tool_call_count,
            "market_report": report,
            "sentiment_report": report,
            "news_report": report,
            "fundamentals_report": report,
        }
        state["messages"][-1] = last_msg
        return state

    def test_market_exits_on_excessive_messages(self):
        """should_continue_market must exit when messages exceed safety threshold."""
        try:
            from tradingagents.graph.conditional_logic import ConditionalLogic
        except ImportError:
            pytest.skip("Dependencies not available")

        logic = ConditionalLogic()
        state = self._make_state(tool_call_count=0, messages_count=110, tool_calls=True)
        result = logic.should_continue_market(state)
        assert result == "Msg Clear Market", f"Expected forced exit, got {result}"

    def test_social_exits_on_excessive_messages(self):
        """should_continue_social must exit when messages exceed safety threshold."""
        try:
            from tradingagents.graph.conditional_logic import ConditionalLogic
        except ImportError:
            pytest.skip("Dependencies not available")

        logic = ConditionalLogic()
        state = self._make_state(tool_call_count=0, messages_count=110, tool_calls=True)
        result = logic.should_continue_social(state)
        assert result == "Msg Clear Social", f"Expected forced exit, got {result}"

    def test_news_exits_on_excessive_messages(self):
        """should_continue_news must exit when messages exceed safety threshold."""
        try:
            from tradingagents.graph.conditional_logic import ConditionalLogic
        except ImportError:
            pytest.skip("Dependencies not available")

        logic = ConditionalLogic()
        state = self._make_state(tool_call_count=0, messages_count=110, tool_calls=True)
        result = logic.should_continue_news(state)
        assert result == "Msg Clear News", f"Expected forced exit, got {result}"

    def test_fundamentals_exits_on_excessive_messages(self):
        """should_continue_fundamentals must exit when messages exceed safety threshold."""
        try:
            from tradingagents.graph.conditional_logic import ConditionalLogic
        except ImportError:
            pytest.skip("Dependencies not available")

        logic = ConditionalLogic()
        state = self._make_state(tool_call_count=0, messages_count=110, tool_calls=True)
        result = logic.should_continue_fundamentals(state)
        assert result == "Msg Clear Fundamentals", f"Expected forced exit, got {result}"

    def test_normal_flow_still_works(self):
        """With normal message count and tool_call_count=0, loop should continue."""
        try:
            from tradingagents.graph.conditional_logic import ConditionalLogic
        except ImportError:
            pytest.skip("Dependencies not available")

        logic = ConditionalLogic()
        state = self._make_state(tool_call_count=0, messages_count=5, tool_calls=True)
        result = logic.should_continue_market(state)
        assert result == "tools_market", f"Expected continuation, got {result}"

    def test_counter_still_works(self):
        """Existing counter-based exit must still function."""
        try:
            from tradingagents.graph.conditional_logic import ConditionalLogic
        except ImportError:
            pytest.skip("Dependencies not available")

        logic = ConditionalLogic()
        state = self._make_state(tool_call_count=300, messages_count=5, tool_calls=True)
        result = logic.should_continue_market(state)
        assert result == "Msg Clear Market", f"Expected counter-based exit, got {result}"
