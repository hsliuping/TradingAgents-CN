import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "run_governance_validations.py"

spec = importlib.util.spec_from_file_location("run_governance_validations", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_run_governance_validations_writes_structured_output(monkeypatch, tmp_path):
    output_path = tmp_path / "governance-summary.json"
    calls = []
    validator_summary = {
        "ok": True,
        "checks": {
            "worker_completed": True,
            "project_memory_injected": True,
            "historical_lessons_injected": True,
            "runtime_observation_logged": True,
        },
        "lesson_recall_kwargs": {
            "metadata_filters": {"spec_id": "spec_valuation_candidate_v1"},
            "user_id": "user_001",
        },
        "observation_logs": [
            {"source_stage": "runtime_governance", "status": "hit"},
        ],
    }

    def _fake_run(command, cwd=None, capture_output=None, text=None, encoding=None, errors=None):
        calls.append({
            "command": command,
            "cwd": cwd,
            "capture_output": capture_output,
            "text": text,
            "encoding": encoding,
            "errors": errors,
        })
        return subprocess.CompletedProcess(command, 0, stdout=f"[PASS] validator\n{validator_summary!r}\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", [
        "run_governance_validations.py",
        "--only",
        "agent_workshop_governance_l4_l6",
        "--output",
        str(output_path),
    ])

    exit_code = module.main()

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["cwd"] == module.ROOT
    assert calls[0]["capture_output"] is True
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["ok"] is True
    assert summary["failures"] == []
    assert summary["selected"] == ["agent_workshop_governance_l4_l6"]
    assert summary["observation_aggregate"] == {
        "validator_count": 1,
        "validators": ["agent_workshop_governance_l4_l6"],
        "total_count": 1,
        "hit_count": 1,
        "miss_count": 0,
        "error_count": 0,
        "stages": {
            "runtime_governance": {
                "count": 1,
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 1,
                "validators": ["agent_workshop_governance_l4_l6"],
                "statuses": ["hit"],
            },
        },
        "stage_ranking": [{
            "stage": "runtime_governance",
            "count": 1,
            "hit_count": 1,
            "miss_count": 0,
            "error_count": 0,
            "validator_count": 1,
            "validators": ["agent_workshop_governance_l4_l6"],
            "statuses": ["hit"],
        }],
    }
    assert summary["validators"] == [{
        "name": "agent_workshop_governance_l4_l6",
        "script": "scripts/validate_agent_workshop_governance_l4_l6_loop.py",
        "command": [sys.executable, str(ROOT_DIR / "scripts" / "validate_agent_workshop_governance_l4_l6_loop.py")],
        "returncode": 0,
        "ok": True,
        "status": "passed",
        "details": {
            "checks": {
                "worker_completed": True,
                "project_memory_injected": True,
                "historical_lessons_injected": True,
                "runtime_observation_logged": True,
            },
            "failed_checks": [],
            "observation_summary": {
                "count": 1,
                "stages": ["runtime_governance"],
                "statuses": ["hit"],
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "stage_breakdown": {
                    "runtime_governance": {
                        "count": 1,
                        "hit_count": 1,
                        "miss_count": 0,
                        "error_count": 0,
                        "statuses": ["hit"],
                    },
                },
            },
            "recall_summary": {
                "count": 1,
                "metadata_filters": [{"spec_id": "spec_valuation_candidate_v1"}],
                "user_ids": ["user_001"],
            },
        },
    }]


def test_run_governance_validations_json_stdout(monkeypatch, capsys):
    def _fake_run(command, cwd=None, capture_output=None, text=None, encoding=None, errors=None):
        del cwd, capture_output, text, encoding, errors
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="boom")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", [
        "run_governance_validations.py",
        "--only",
        "agent_workshop_governance_l4_l6",
        "--json",
    ])

    exit_code = module.main()

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["failures"] == ["agent_workshop_governance_l4_l6"]
    assert payload["observation_aggregate"] == {
        "validator_count": 0,
        "validators": [],
        "total_count": 0,
        "hit_count": 0,
        "miss_count": 0,
        "error_count": 0,
        "stages": {},
        "stage_ranking": [],
    }
    assert payload["validators"][0]["status"] == "failed"


def test_run_governance_validations_supports_agent_workshop_l6_forward_consumption(monkeypatch, tmp_path):
    output_path = tmp_path / "governance-forward-consumption.json"
    calls = []
    validator_summary = {
        "ok": True,
        "checks": {
            "three_stage_observation_logs": True,
            "all_observation_stages_present": True,
            "all_observations_hit": True,
        },
        "lesson_recall_calls": [
            {"metadata_filters": {"spec_id": "spec_valuation_candidate_v1"}, "user_id": "user_001"},
            {"metadata_filters": {"spec_id": "spec_valuation_candidate_v1"}, "user_id": "user_001"},
            {"metadata_filters": {"spec_id": "spec_valuation_candidate_v1"}, "user_id": "user_001"},
        ],
        "observation_logs": [
            {"result": {"source_stage": "requirement_clarification", "status": "hit"}},
            {"result": {"source_stage": "gap_analysis", "status": "hit"}},
            {"result": {"source_stage": "build_version", "status": "hit"}},
        ],
    }

    def _fake_run(command, cwd=None, capture_output=None, text=None, encoding=None, errors=None):
        calls.append({
            "command": command,
            "cwd": cwd,
            "capture_output": capture_output,
            "text": text,
            "encoding": encoding,
            "errors": errors,
        })
        return subprocess.CompletedProcess(command, 0, stdout=f"[PASS] validator\n{validator_summary!r}\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", [
        "run_governance_validations.py",
        "--only",
        "agent_workshop_l6_forward_consumption",
        "--output",
        str(output_path),
    ])

    exit_code = module.main()

    assert exit_code == 0
    assert len(calls) == 1
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["selected"] == ["agent_workshop_l6_forward_consumption"]
    assert summary["observation_aggregate"] == {
        "validator_count": 1,
        "validators": ["agent_workshop_l6_forward_consumption"],
        "total_count": 3,
        "hit_count": 3,
        "miss_count": 0,
        "error_count": 0,
        "stages": {
            "build_version": {
                "count": 1,
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 1,
                "validators": ["agent_workshop_l6_forward_consumption"],
                "statuses": ["hit"],
            },
            "gap_analysis": {
                "count": 1,
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 1,
                "validators": ["agent_workshop_l6_forward_consumption"],
                "statuses": ["hit"],
            },
            "requirement_clarification": {
                "count": 1,
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 1,
                "validators": ["agent_workshop_l6_forward_consumption"],
                "statuses": ["hit"],
            },
        },
        "stage_ranking": [
            {
                "stage": "build_version",
                "count": 1,
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 1,
                "validators": ["agent_workshop_l6_forward_consumption"],
                "statuses": ["hit"],
            },
            {
                "stage": "gap_analysis",
                "count": 1,
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 1,
                "validators": ["agent_workshop_l6_forward_consumption"],
                "statuses": ["hit"],
            },
            {
                "stage": "requirement_clarification",
                "count": 1,
                "hit_count": 1,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 1,
                "validators": ["agent_workshop_l6_forward_consumption"],
                "statuses": ["hit"],
            },
        ],
    }
    assert summary["validators"] == [{
        "name": "agent_workshop_l6_forward_consumption",
        "script": "scripts/validate_agent_workshop_l6_forward_consumption_loop.py",
        "command": [sys.executable, str(ROOT_DIR / "scripts" / "validate_agent_workshop_l6_forward_consumption_loop.py")],
        "returncode": 0,
        "ok": True,
        "status": "passed",
        "details": {
            "checks": {
                "three_stage_observation_logs": True,
                "all_observation_stages_present": True,
                "all_observations_hit": True,
            },
            "failed_checks": [],
            "observation_summary": {
                "count": 3,
                "stages": ["build_version", "gap_analysis", "requirement_clarification"],
                "statuses": ["hit"],
                "hit_count": 3,
                "miss_count": 0,
                "error_count": 0,
                "stage_breakdown": {
                    "build_version": {
                        "count": 1,
                        "hit_count": 1,
                        "miss_count": 0,
                        "error_count": 0,
                        "statuses": ["hit"],
                    },
                    "gap_analysis": {
                        "count": 1,
                        "hit_count": 1,
                        "miss_count": 0,
                        "error_count": 0,
                        "statuses": ["hit"],
                    },
                    "requirement_clarification": {
                        "count": 1,
                        "hit_count": 1,
                        "miss_count": 0,
                        "error_count": 0,
                        "statuses": ["hit"],
                    },
                },
            },
            "recall_summary": {
                "count": 3,
                "metadata_filters": [
                    {"spec_id": "spec_valuation_candidate_v1"},
                    {"spec_id": "spec_valuation_candidate_v1"},
                    {"spec_id": "spec_valuation_candidate_v1"},
                ],
                "user_ids": ["user_001"],
            },
        },
    }]