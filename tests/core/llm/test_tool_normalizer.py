from core.llm.models import ToolCall
from core.llm.tool_normalizer import ToolCallNormalizer


def test_execute_tool_call_unwraps_nested_kwargs_payload():
    received = {}

    def analyze_a_share_dupont(symbol: str, periods: int = 8):
        received["symbol"] = symbol
        received["periods"] = periods
        return {"symbol": symbol, "periods": periods}

    tool_call = ToolCall(
        id="call-1",
        name="analyze_a_share_dupont",
        arguments={
            "kwargs": {
                "symbol": "600519.SH",
                "periods": 4,
            }
        },
    )

    result = ToolCallNormalizer.execute_tool_call(
        tool_call,
        {"analyze_a_share_dupont": analyze_a_share_dupont},
    )

    assert result.is_error is False
    assert received == {"symbol": "600519", "periods": 4}
    assert '"symbol": "600519"' in result.content


def test_execute_tool_call_prefers_explicit_context_over_nested_kwargs():
    received = {}

    def analyze_a_share_dupont(symbol: str, periods: int = 8, request_id: str | None = None):
        received["symbol"] = symbol
        received["periods"] = periods
        received["request_id"] = request_id
        return "ok"

    tool_call = ToolCall(
        id="call-2",
        name="analyze_a_share_dupont",
        arguments={
            "kwargs": {
                "symbol": "600519",
                "periods": 2,
                "request_id": "old",
            }
        },
    )

    result = ToolCallNormalizer.execute_tool_call(
        tool_call,
        {"analyze_a_share_dupont": analyze_a_share_dupont},
        request_id="new",
    )

    assert result.is_error is False
    assert received == {"symbol": "600519", "periods": 2, "request_id": "new"}