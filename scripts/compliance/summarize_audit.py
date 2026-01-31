"""Summarize outputs of audit_all_prompts.py into a human-readable Markdown.

Reads:
- exports/compliance_audit/prompt_templates_audit.json
- exports/compliance_audit/repo_terms_hitlist.json

Writes:
- exports/compliance_audit/top_findings.md
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    base = Path("exports/compliance_audit")
    tmpl_path = base / "prompt_templates_audit.json"
    repo_path = base / "repo_terms_hitlist.json"

    tmpl = _load_json(tmpl_path)
    repo = _load_json(repo_path)

    items: List[Dict[str, Any]] = tmpl.get("items") or []
    hit_items = [i for i in items if i.get("field_hits")]

    term_counter = Counter()
    agent_counter = Counter()
    for it in hit_items:
        agent = f"{it.get('agent_type')}/{it.get('agent_name')}"
        agent_counter[agent] += 1
        for hits in (it.get("field_hits") or {}).values():
            term_counter.update(hits)

    # Repo hits: focus on code paths first
    repo_items: List[Dict[str, Any]] = repo.get("items") or []
    code_repo_items = [
        r
        for r in repo_items
        if any(r.get("path", "").startswith(prefix) for prefix in ("core/", "app/", "tradingagents/", "scripts/"))
    ]

    def hit_count(it: Dict[str, Any]) -> int:
        return sum(len(v) for v in (it.get("field_hits") or {}).values())

    top_templates = sorted(hit_items, key=hit_count, reverse=True)[:30]

    lines: List[str] = []
    lines += [
        "# Prompt Compliance Audit - Top Findings",
        "",
        f"- Total templates: **{tmpl.get('summary', {}).get('total_templates')}**",
        f"- Templates with hit terms: **{tmpl.get('summary', {}).get('templates_with_hits')}**",
        f"- Repo hitlist entries (all): **{len(repo_items)}**",
        f"- Repo hitlist entries (code-only): **{len(code_repo_items)}**",
        "",
        "## Most common hit terms (templates)",
    ]

    for term, cnt in term_counter.most_common(20):
        lines.append(f"- `{term}`: {cnt}")

    lines += ["", "## Agents with most flagged templates (top 20)"]
    for agent, cnt in agent_counter.most_common(20):
        lines.append(f"- `{agent}`: {cnt}")

    lines += ["", "## Top flagged templates (top 30)", "(Sorted by total hit terms across template fields)", ""]
    for it in top_templates:
        agent = f"{it.get('agent_type')}/{it.get('agent_name')}"
        lines.append(
            f"- **{agent}** | `{it.get('template_name')}` | pref=`{it.get('preference_type')}` | system={it.get('is_system')} | hits={hit_count(it)}"
        )

    lines += ["", "## Code files with hit terms (sample, first 50)"]
    for r in code_repo_items[:50]:
        lines.append(f"- `{r.get('path')}`: {', '.join(r.get('terms') or [])}")

    out_path = base / "top_findings.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Wrote: {out_path}")


if __name__ == "__main__":
    main()

