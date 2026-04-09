from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]

VALIDATORS: List[Tuple[str, Path]] = [
    ("project_memory_l4", ROOT / "scripts" / "validate_project_memory_l4_loop.py"),
    ("agent_builder_memory", ROOT / "scripts" / "validate_agent_builder_project_memory_loop.py"),
    ("prompt_template_project_memory", ROOT / "scripts" / "validate_agent_workshop_prompt_template_project_memory_loop.py"),
    ("production_review_project_memory", ROOT / "scripts" / "validate_agent_workshop_production_review_project_memory_loop.py"),
    ("agent_workshop_l6_forward_consumption", ROOT / "scripts" / "validate_agent_workshop_l6_forward_consumption_loop.py"),
    ("agent_workshop_governance_l4_l6", ROOT / "scripts" / "validate_agent_workshop_governance_l4_l6_loop.py"),
]


def _select_validators(args: argparse.Namespace) -> List[Tuple[str, Path]]:
    if args.only:
        return [item for item in VALIDATORS if item[0] == args.only]
    return VALIDATORS


def _build_command(script_path: Path) -> Sequence[str]:
    return [sys.executable, str(script_path)]


def _extract_validator_summary(stdout: str) -> Dict[str, Any] | None:
    lines = [line.strip() for line in str(stdout or "").splitlines() if line.strip()]
    if not lines:
        return None

    candidate = lines[-1]
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(candidate)
        except (ValueError, SyntaxError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _build_observation_summary(observation_logs: Any) -> Dict[str, Any] | None:
    if not isinstance(observation_logs, list) or not observation_logs:
        return None

    normalized_logs = [
        item.get("result", item)
        for item in observation_logs
        if isinstance(item, dict)
    ]
    statuses = [str(item.get("status") or "") for item in normalized_logs if isinstance(item, dict)]
    stages = [str(item.get("source_stage") or "") for item in normalized_logs if isinstance(item, dict)]
    stage_breakdown: Dict[str, Dict[str, Any]] = {}
    for item in normalized_logs:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("source_stage") or "").strip()
        status = str(item.get("status") or "").strip()
        if not stage:
            continue
        entry = stage_breakdown.setdefault(stage, {
            "count": 0,
            "hit_count": 0,
            "miss_count": 0,
            "error_count": 0,
            "statuses": [],
        })
        entry["count"] += 1
        if status == "hit":
            entry["hit_count"] += 1
        elif status == "miss":
            entry["miss_count"] += 1
        elif status == "error":
            entry["error_count"] += 1
        if status and status not in entry["statuses"]:
            entry["statuses"].append(status)

    return {
        "count": len(observation_logs),
        "stages": sorted({stage for stage in stages if stage}),
        "statuses": sorted({status for status in statuses if status}),
        "hit_count": sum(1 for status in statuses if status == "hit"),
        "miss_count": sum(1 for status in statuses if status == "miss"),
        "error_count": sum(1 for status in statuses if status == "error"),
        "stage_breakdown": {
            stage: {
                "count": entry["count"],
                "hit_count": entry["hit_count"],
                "miss_count": entry["miss_count"],
                "error_count": entry["error_count"],
                "statuses": sorted(entry["statuses"]),
            }
            for stage, entry in sorted(stage_breakdown.items())
        },
    }


def _build_recall_summary(summary: Dict[str, Any]) -> Dict[str, Any] | None:
    recall_calls = summary.get("lesson_recall_calls")
    if isinstance(recall_calls, list) and recall_calls:
        return {
            "count": len(recall_calls),
            "metadata_filters": [call.get("metadata_filters", {}) for call in recall_calls],
            "user_ids": sorted({str(call.get("user_id") or "") for call in recall_calls if str(call.get("user_id") or "").strip()}),
        }

    recall_kwargs = summary.get("lesson_recall_kwargs")
    if isinstance(recall_kwargs, dict) and recall_kwargs:
        return {
            "count": 1,
            "metadata_filters": [recall_kwargs.get("metadata_filters", {})],
            "user_ids": [str(recall_kwargs.get("user_id") or "")] if str(recall_kwargs.get("user_id") or "").strip() else [],
        }

    return None


def _build_validator_details(stdout: str) -> Dict[str, Any] | None:
    summary = _extract_validator_summary(stdout)
    if not summary:
        return None

    details: Dict[str, Any] = {}
    checks = summary.get("checks")
    if isinstance(checks, dict):
        details["checks"] = checks
        details["failed_checks"] = [name for name, ok in checks.items() if not ok]

    observation_summary = _build_observation_summary(summary.get("observation_logs"))
    if observation_summary is not None:
        details["observation_summary"] = observation_summary

    recall_summary = _build_recall_summary(summary)
    if recall_summary is not None:
        details["recall_summary"] = recall_summary

    return details or None


def _build_observation_aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    aggregate = {
        "validator_count": 0,
        "validators": [],
        "total_count": 0,
        "hit_count": 0,
        "miss_count": 0,
        "error_count": 0,
        "stages": {},
        "stage_ranking": [],
    }

    for result in results:
        details = result.get("details")
        if not isinstance(details, dict):
            continue
        observation_summary = details.get("observation_summary")
        if not isinstance(observation_summary, dict):
            continue

        validator_name = str(result.get("name") or "")
        aggregate["validator_count"] += 1
        if validator_name:
            aggregate["validators"].append(validator_name)

        aggregate["total_count"] += int(observation_summary.get("count") or 0)
        aggregate["hit_count"] += int(observation_summary.get("hit_count") or 0)
        aggregate["miss_count"] += int(observation_summary.get("miss_count") or 0)
        aggregate["error_count"] += int(observation_summary.get("error_count") or 0)

        stage_breakdown = observation_summary.get("stage_breakdown") or {}
        for stage, stage_summary in stage_breakdown.items():
            stage_key = str(stage or "").strip()
            if not stage_key:
                continue
            stage_entry = aggregate["stages"].setdefault(stage_key, {
                "count": 0,
                "hit_count": 0,
                "miss_count": 0,
                "error_count": 0,
                "validator_count": 0,
                "validators": [],
                "statuses": [],
            })
            stage_entry["count"] += int(stage_summary.get("count") or 0)
            stage_entry["hit_count"] += int(stage_summary.get("hit_count") or 0)
            stage_entry["miss_count"] += int(stage_summary.get("miss_count") or 0)
            stage_entry["error_count"] += int(stage_summary.get("error_count") or 0)
            stage_entry["validator_count"] += 1
            if validator_name and validator_name not in stage_entry["validators"]:
                stage_entry["validators"].append(validator_name)
            stage_entry["statuses"] = sorted({
                *stage_entry["statuses"],
                *(str(status or "") for status in (stage_summary.get("statuses") or []) if str(status or "").strip()),
            })

    aggregate["validators"] = sorted(set(aggregate["validators"]))
    aggregate["stages"] = {
        stage: {
            "count": entry["count"],
            "hit_count": entry["hit_count"],
            "miss_count": entry["miss_count"],
            "error_count": entry["error_count"],
            "validator_count": entry["validator_count"],
            "validators": sorted(entry["validators"]),
            "statuses": entry["statuses"],
        }
        for stage, entry in sorted(aggregate["stages"].items())
    }
    aggregate["stage_ranking"] = [
        {
            "stage": stage,
            **entry,
        }
        for stage, entry in sorted(
            aggregate["stages"].items(),
            key=lambda item: (
                -int(item[1].get("miss_count") or 0),
                -int(item[1].get("error_count") or 0),
                -int(item[1].get("count") or 0),
                item[0],
            ),
        )
    ]
    return aggregate


def _build_summary(selected: List[Tuple[str, Path]], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    failures = [item["name"] for item in results if not item["ok"]]
    return {
        "ok": not failures,
        "python": sys.executable,
        "root": str(ROOT),
        "selected": [name for name, _path in selected],
        "failures": failures,
        "validators": results,
        "observation_aggregate": _build_observation_aggregate(results),
    }


def _run_validators(selected: List[Tuple[str, Path]], *, emit_logs: bool) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []

    if emit_logs:
        print("=" * 72)
        print("Governance Validation Suite")
        print(f"Python: {sys.executable}")
        print(f"Root:   {ROOT}")
        print("=" * 72)

    for name, script_path in selected:
        command = list(_build_command(script_path))
        if emit_logs:
            print(f"\n[RUN] {name}: {' '.join(command)}")

        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        stdout = str(completed.stdout or "")
        stderr = str(completed.stderr or "")
        if emit_logs and stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if emit_logs and stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)

        details = _build_validator_details(stdout)

        result = {
            "name": name,
            "script": script_path.relative_to(ROOT).as_posix(),
            "command": command,
            "returncode": int(completed.returncode),
            "ok": completed.returncode == 0,
            "status": "passed" if completed.returncode == 0 else "failed",
        }
        if details is not None:
            result["details"] = details
        results.append(result)

        if emit_logs:
            if completed.returncode == 0:
                print(f"[PASS] {name}")
            else:
                print(f"[FAIL] {name} exit={completed.returncode}")

    summary = _build_summary(selected, results)
    if emit_logs:
        print("\n" + "=" * 72)
        if summary["failures"]:
            print("Governance validation failed:", ", ".join(summary["failures"]))
        else:
            print("All governance validations passed")
        print("=" * 72)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="运行记忆与治理回归校验脚本")
    parser.add_argument(
        "--only",
        choices=[name for name, _path in VALIDATORS],
        default=None,
        help="只运行某一类治理校验",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 形式输出汇总结果（不打印文本日志）",
    )
    parser.add_argument(
        "--output",
        default="",
        help="将结构化汇总结果写入指定 JSON 文件",
    )
    args = parser.parse_args()

    selected = _select_validators(args)
    summary = _run_validators(selected, emit_logs=not args.json)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())