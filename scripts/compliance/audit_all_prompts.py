"""Audit prompts for compliance risks.

Scans:
1) Mongo export JSON (install/database_export_config_*.json) -> data.prompt_templates
2) Hardcoded prompts in repo files (heuristic: scan .py/.md/.ts strings too)

Outputs JSON + a small Markdown summary under exports/compliance_audit/.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_EXPORT = "install/database_export_config_2026-01-28.json"

# Keywords we want to eliminate from *prompt requirements*.
# Note: disclaimers are stripped before scanning to avoid false positives.
TERMS = [
    "目标价", "目标价位", "目标价格", "target_price",
    "买入", "卖出", "持有", "加仓", "减仓", "清仓", "建仓",
    "操作建议", "交易建议", "投资建议",
    "仓位", "仓位比例", "position_ratio", "action_ratio",
    "止损", "止盈", "stop_loss", "take_profit", "stop_loss_price", "take_profit_price",
    "交易指令", "trading_instruction", "trading_plan",
]

DISCLAIMER_MARKERS = ["免责声明", "**免责声明**", "重要提示"]

# Avoid scanning huge/unrelated directories (venv, vendor bundles, build outputs)
EXCLUDE_DIR_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "vendors",
    "vendor",
    "release",
    "dist",
    "build",
    "node_modules",
    "__pycache__",
}

DEFAULT_SCAN_ROOTS = ["core", "app", "tradingagents", "scripts", "docs"]


def _strip_disclaimer(text: str) -> str:
    if not text:
        return ""
    cut = len(text)
    for m in DISCLAIMER_MARKERS:
        idx = text.find(m)
        if idx != -1:
            cut = min(cut, idx)
    return text[:cut]


def _find_terms(text: str) -> List[str]:
    text = _strip_disclaimer(text)
    found: List[str] = []
    lower = text.lower()
    for term in TERMS:
        if term.lower() in lower:
            found.append(term)
    return sorted(set(found))


def load_prompt_templates(export_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(export_path.read_text(encoding="utf-8"))
    return data.get("data", {}).get("prompt_templates", []) or []


def audit_templates(templates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    by_agent: Dict[str, int] = {}
    bad_count = 0

    for t in templates:
        content = t.get("content") or {}
        fields = ["system_prompt", "user_prompt", "tool_guidance", "analysis_requirements", "output_format", "constraints"]
        field_hits: Dict[str, List[str]] = {}
        for f in fields:
            hits = _find_terms(str(content.get(f) or ""))
            if hits:
                field_hits[f] = hits
        key = f"{t.get('agent_type')}/{t.get('agent_name')}"
        by_agent[key] = by_agent.get(key, 0) + 1
        if field_hits:
            bad_count += 1
        results.append({
            "_id": t.get("_id"),
            "agent_type": t.get("agent_type"),
            "agent_name": t.get("agent_name"),
            "template_name": t.get("template_name"),
            "preference_type": t.get("preference_type"),
            "is_system": t.get("is_system"),
            "status": t.get("status"),
            "field_hits": field_hits,
        })

    summary = {
        "total_templates": len(templates),
        "templates_with_hits": bad_count,
        "unique_agents": len(by_agent),
        "agent_template_counts": dict(sorted(by_agent.items())),
    }
    return results, summary


def audit_repo_files(scan_roots: List[Path], include_globs: List[str]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    patterns = [(term, re.compile(re.escape(term), re.IGNORECASE)) for term in TERMS]

    for root in scan_roots:
        if not root.exists():
            continue
        for glob in include_globs:
            for p in root.rglob(glob):
                # Skip excluded directories anywhere in the path
                if any(part in EXCLUDE_DIR_PARTS for part in p.parts):
                    continue
                try:
                    # Skip very large files (likely generated bundles)
                    if p.stat().st_size > 2_000_000:
                        continue
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                found_terms = [term for term, pat in patterns if pat.search(text)]
                if found_terms:
                    hits.append({"path": str(p).replace("\\", "/"), "terms": sorted(set(found_terms))})

    return sorted(hits, key=lambda x: x["path"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default=DEFAULT_EXPORT, help="Mongo export JSON path")
    ap.add_argument("--out", default="exports/compliance_audit", help="Output directory")
    ap.add_argument("--repo", default=".", help="Repo root")
    ap.add_argument(
        "--scan-roots",
        nargs="*",
        default=DEFAULT_SCAN_ROOTS,
        help="Top-level directories to scan for hardcoded prompts",
    )
    args = ap.parse_args()

    export_path = Path(args.export)
    out_dir = Path(args.out)
    repo_root = Path(args.repo)
    out_dir.mkdir(parents=True, exist_ok=True)

    templates = load_prompt_templates(export_path)
    template_audit, template_summary = audit_templates(templates)
    (out_dir / "prompt_templates_audit.json").write_text(json.dumps({
        "export": str(export_path),
        "summary": template_summary,
        "items": template_audit,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    scan_roots = [repo_root / d for d in (args.scan_roots or [])]
    repo_hits = audit_repo_files(scan_roots, include_globs=["*.py", "*.md", "*.ts"])  # broad but cheap
    (out_dir / "repo_terms_hitlist.json").write_text(json.dumps({
        "terms": TERMS,
        "items": repo_hits,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Prompt Compliance Audit (auto)",
        "",
        f"- Export: `{export_path.as_posix()}`",
        f"- Total templates: **{template_summary['total_templates']}**",
        f"- Templates with hit terms (excluding disclaimers): **{template_summary['templates_with_hits']}**",
        f"- Repo files hitlist entries: **{len(repo_hits)}**",
        "",
        "## Next", "- Review `prompt_templates_audit.json` and decide which terms should be fully removed vs reworded.",
    ]
    (out_dir / "audit_summary.md").write_text("\n".join(md), encoding="utf-8")

    print(f"✅ Wrote: {out_dir / 'prompt_templates_audit.json'}")
    print(f"✅ Wrote: {out_dir / 'repo_terms_hitlist.json'}")
    print(f"✅ Wrote: {out_dir / 'audit_summary.md'}")


if __name__ == "__main__":
    main()

