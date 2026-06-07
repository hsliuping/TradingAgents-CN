import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "codex_agent_bridge.py"


def load_bridge_module():
    spec = importlib.util.spec_from_file_location("codex_agent_bridge", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_codex_command_uses_readonly_exec_and_output_file(tmp_path):
    bridge = load_bridge_module()
    config = bridge.BridgeConfig(
        codex_binary="/usr/local/bin/codex",
        workspace="/repo",
        model="gpt-5.5",
        sandbox="read-only",
    )

    command = bridge.build_codex_command(config, str(tmp_path / "last.txt"))

    assert command[:2] == ["/usr/local/bin/codex", "exec"]
    assert "--cd" in command
    assert "/repo" in command
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--ephemeral" in command
    assert "--output-last-message" in command
    assert command[-1] == "-"
    assert "gpt-5.5" in command


def test_run_codex_agent_returns_last_message_from_output_file(tmp_path):
    bridge = load_bridge_module()
    config = bridge.BridgeConfig(
        codex_binary="codex",
        workspace=str(tmp_path),
        timeout=5,
    )

    def fake_runner(command, **kwargs):
        output_path = command[command.index("--output-last-message") + 1]
        Path(output_path).write_text("## Codex 分析\n建议持有。", encoding="utf-8")
        assert "股票代码" in kwargs["input"]
        return SimpleNamespace(returncode=0, stdout="event log", stderr="")

    result = bridge.run_codex_agent(
        {"prompt": "请分析股票", "context": {"stock_code": "000001"}},
        config=config,
        runner=fake_runner,
    )

    assert result["content"] == "## Codex 分析\n建议持有。"
    assert result["agent_engine"] == "codex"
    assert result["model_info"].startswith("Codex CLI")


def test_run_codex_agent_raises_on_command_failure(tmp_path):
    bridge = load_bridge_module()
    config = bridge.BridgeConfig(codex_binary="codex", workspace=str(tmp_path))

    def fake_runner(command, **kwargs):
        return SimpleNamespace(returncode=2, stdout="", stderr="bad things")

    with pytest.raises(bridge.CodexBridgeError, match="bad things"):
        bridge.run_codex_agent(
            {"prompt": "请分析股票", "context": {"stock_code": "000001"}},
            config=config,
            runner=fake_runner,
        )
