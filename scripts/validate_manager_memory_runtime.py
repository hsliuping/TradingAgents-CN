"""Validate manager runtime memory read/write flow against mem0 using isolated samples."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.agents.adapters.research_manager_v2 import ResearchManagerV2
from core.agents.adapters.risk_manager_v2 import RiskManagerV2
from core.memory.memory_manager import MemoryManager
from core.memory.service import get_memory_service


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate manager runtime memory read/write flow in mem0-only mode."
    )
    parser.add_argument(
        "--mode",
        choices=["mem0-only"],
        default="mem0-only",
        help="Legacy fallback has been retired; validation always runs in mem0-only mode.",
    )
    return parser.parse_args()


def _configure_runtime_mode(mode: str, validation_user: str) -> Dict[str, str]:
    normalized_mode = str(mode or "mem0-only").strip().lower()
    if normalized_mode != "mem0-only":
        raise ValueError(f"unsupported validation mode: {mode}")

    updates = {
        "MEM0_COMPAT_USER_ID": validation_user,
        "MEMORY_USE_MEM0_COMPAT": "true",
        "MEM0_FORCE_PRIMARY": "true",
    }

    os.environ.update(updates)
    return updates


class _FakeEmbeddingManager:
    def get_embedding_dimension(self) -> int:
        return 1024

    def get_embedding(self, content: str):
        del content
        return [0.0] * 8, "validation"


class _RecordingLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls: List[List[Any]] = []

    def invoke(self, messages):
        self.calls.append(list(messages))

        class _Response:
            def __init__(self, content: str):
                self.content = content

        return _Response(self.response_text)


class _FallbackResearchManager(ResearchManagerV2):
    def _get_prompt_from_template(self, *args, **kwargs):
        del args, kwargs
        return None


class _FallbackRiskManager(RiskManagerV2):
    def _get_prompt_from_template(self, *args, **kwargs):
        del args, kwargs
        return None


def _get_human_prompt(messages: List[Any]) -> str:
    for message in messages:
        if getattr(message, "type", "") == "human":
            return str(getattr(message, "content", ""))
    return ""


async def _cleanup_validation_user(user_id: str) -> int:
    service = get_memory_service()
    return await service.delete_all_user_memories(user_id)


async def _health_check() -> Dict[str, Any]:
    service = get_memory_service()
    return await service.health_check()


def _run_research_manager_validation(memory_manager: MemoryManager, marker: str) -> Dict[str, Any]:
    memory = memory_manager.get_agent_memory("research_manager_v2")
    first_llm = _RecordingLLM(
        f"研究经理历史样本 {marker} bull_report 看涨理由 bear_report 看跌理由"
    )
    second_llm = _RecordingLLM("研究经理第二次执行")

    first_agent = _FallbackResearchManager(llm=first_llm, memory=memory)
    second_agent = _FallbackResearchManager(llm=second_llm, memory=memory)

    state = {
        "ticker": "300750",
        "analysis_date": "2026-04-08",
        "bull_report": "看涨理由",
        "bear_report": "看跌理由",
        "current_price": "215.30",
    }

    first_result = first_agent.execute(dict(state))
    second_result = second_agent.execute(dict(state))
    second_prompt = _get_human_prompt(second_llm.calls[-1]) if second_llm.calls else ""

    return {
        "first_result": first_result,
        "second_result": second_result,
        "second_prompt": second_prompt,
        "history_hit": marker in second_prompt and "历史管理经验" in second_prompt,
    }


def _run_risk_manager_validation(memory_manager: MemoryManager, marker: str) -> Dict[str, Any]:
    memory = memory_manager.get_agent_memory("risk_manager_v2")
    first_llm = _RecordingLLM(
        f"风险经理历史样本 {marker} investment_plan 投资计划 risky_opinion 激进 safe_opinion 保守 neutral_opinion 中性"
    )
    second_llm = _RecordingLLM("风险经理第二次执行")

    first_agent = _FallbackRiskManager(llm=first_llm, memory=memory)
    second_agent = _FallbackRiskManager(llm=second_llm, memory=memory)

    state = {
        "ticker": "300750",
        "analysis_date": "2026-04-08",
        "investment_plan": "投资计划",
        "risky_opinion": "激进观点",
        "safe_opinion": "保守观点",
        "neutral_opinion": "中性观点",
        "company_name": "宁德时代",
    }

    first_result = first_agent.execute(dict(state))
    second_result = second_agent.execute(dict(state))
    second_prompt = _get_human_prompt(second_llm.calls[-1]) if second_llm.calls else ""

    return {
        "first_result": first_result,
        "second_result": second_result,
        "second_prompt": second_prompt,
        "history_hit": marker in second_prompt and "历史管理经验" in second_prompt,
    }


def main() -> int:
    args = _parse_args()
    validation_user = f"manager_runtime_validation_{uuid.uuid4().hex[:8]}"
    marker = f"MANAGER_RUNTIME_VALIDATE_{uuid.uuid4().hex[:8]}"
    env_updates = _configure_runtime_mode(args.mode, validation_user)

    health = asyncio.run(_health_check())
    if not health.get("ok"):
        print("[FAIL] mem0 health check failed")
        print(health)
        return 1

    memory_manager = MemoryManager(_FakeEmbeddingManager())

    try:
        research = _run_research_manager_validation(memory_manager, marker)
        risk = _run_risk_manager_validation(memory_manager, marker)

        print("[INFO] mode=", args.mode)
        print("[INFO] env_updates=", env_updates)
        print("[INFO] validation_user=", validation_user)
        print("[INFO] marker=", marker)
        print("[INFO] research_history_hit=", research["history_hit"])
        print("[INFO] risk_history_hit=", risk["history_hit"])
        print("[INFO] research_prompt_contains_marker=", marker in research["second_prompt"])
        print("[INFO] risk_prompt_contains_marker=", marker in risk["second_prompt"])

        if not research["history_hit"] or not risk["history_hit"]:
            print("[FAIL] manager runtime memory recall did not appear in prompts")
            print("[DEBUG] research_prompt=", research["second_prompt"])
            print("[DEBUG] risk_prompt=", risk["second_prompt"])
            return 2

        print("[PASS] research_manager_v2 and risk_manager_v2 runtime prompts include recalled manager history")
        return 0
    finally:
        deleted = asyncio.run(_cleanup_validation_user(validation_user))
        print("[INFO] cleaned_validation_memories=", deleted)


if __name__ == "__main__":
    raise SystemExit(main())