from langchain_core.tools import StructuredTool

from core.agents.base import BaseAgent
from core.agents.config import AgentCategory, AgentConfig, AgentInput, AgentMetadata, AgentOutput, LicenseTier


class _DummyAgent(BaseAgent):
    metadata = AgentMetadata(
        id="dummy_agent",
        name="Dummy Agent",
        description="test agent",
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.FREE,
        inputs=[AgentInput(name="ticker", type="string", description="ticker")],
        outputs=[AgentOutput(name="report", type="string", description="report")],
        tools=[],
        default_tools=[],
    )

    def analyze(self, *args, **kwargs):
        raise NotImplementedError()

    def execute(self, state):
        return state


def test_execute_tool_calls_unwraps_nested_kwargs_for_langchain_tool():
    received = {}

    def analyze_a_share_dupont(symbol: str, periods: int = 8) -> str:
        received["symbol"] = symbol
        received["periods"] = periods
        return f"symbol={symbol},periods={periods}"

    agent = _DummyAgent(config=AgentConfig(), llm=None, tool_ids=None)
    agent._langchain_tools = [
        StructuredTool.from_function(
            func=analyze_a_share_dupont,
            name="analyze_a_share_dupont",
            description="dupont",
        )
    ]

    messages = agent._execute_tool_calls([
        {
            "id": "call-1",
            "name": "analyze_a_share_dupont",
            "args": {
                "kwargs": {
                    "symbol": "600519.SH",
                    "periods": 4,
                }
            },
        }
    ])

    assert len(messages) == 1
    assert received == {"symbol": "600519", "periods": 4}
    assert messages[0].content == "symbol=600519,periods=4"