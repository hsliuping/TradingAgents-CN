import pytest
from tradingagents.tools.mcp import MCPServerConfig

def test_mcp_config_import():
    """Test that MCPServerConfig can be imported."""
    assert MCPServerConfig is not None

def test_basic_math():
    """Basic sanity check."""
    assert 1 + 1 == 2
