import json
import os
import re
import shutil
from pathlib import Path

BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillsLoader:
    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        skills: list[dict[str, str]] = []
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skills.append({"name": skill_dir.name, "path": str(skill_dir / "SKILL.md"), "source": "workspace"})
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists() and not any(item["name"] == skill_dir.name for item in skills):
                    skills.append({"name": skill_dir.name, "path": str(skill_dir / "SKILL.md"), "source": "builtin"})
        return [item for item in skills if self._check_requirements(self._get_skill_meta(item["name"]))] if filter_unavailable else skills

    def load_skill(self, name: str) -> str | None:
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")
        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")
        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        parts: list[str] = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                parts.append(f"### Skill: {name}\n\n{self._strip_frontmatter(content)}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skill_briefs(self, skill_names: list[str]) -> str:
        if not skill_names:
            return ""
        lines: list[str] = []
        all_skills = {item["name"]: item for item in self.list_skills(filter_unavailable=False)}
        for name in skill_names:
            item = all_skills.get(name)
            if not item:
                continue
            description = self._get_skill_description(name)
            lines.append(f"- {name}: {description} ({item['path']})")
        return "\n".join(lines)

    def build_skills_summary(self, excluded_names: list[str] | None = None) -> str:
        excluded = {name for name in (excluded_names or []) if name}
        all_skills = [item for item in self.list_skills(filter_unavailable=False) if item["name"] not in excluded]
        if not all_skills:
            return ""
        def escape_xml(value: str) -> str:
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines = ["<skills>"]
        for item in all_skills:
            name = escape_xml(item["name"])
            desc = escape_xml(self._get_skill_description(item["name"]))
            skill_meta = self._get_skill_meta(item["name"])
            available = self._check_requirements(skill_meta)
            lines.append(f"  <skill available=\"{str(available).lower()}\">")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{item['path']}</location>")
            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")
            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def get_always_skills(self) -> list[str]:
        result: list[str] = []
        for item in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(item["name"]) or {}
            skill_meta = self._parse_nanobot_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(item["name"])
        return result

    def get_skill_metadata(self, name: str) -> dict | None:
        content = self.load_skill(name)
        if not content or not content.startswith("---"):
            return None
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None
        metadata: dict[str, str] = {}
        for line in match.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"\'')
        return metadata

    def _strip_frontmatter(self, content: str) -> str:
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def _parse_nanobot_metadata(self, raw: str) -> dict:
        try:
            data = json.loads(raw)
            return data.get("nanobot", data.get("openclaw", {})) if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _check_requirements(self, skill_meta: dict) -> bool:
        requires = skill_meta.get("requires", {})
        for binary in requires.get("bins", []):
            if not shutil.which(binary):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True

    def _get_skill_meta(self, name: str) -> dict:
        meta = self.get_skill_metadata(name) or {}
        return self._parse_nanobot_metadata(meta.get("metadata", ""))

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        missing: list[str] = []
        requires = skill_meta.get("requires", {})
        for binary in requires.get("bins", []):
            if not shutil.which(binary):
                missing.append(f"CLI: {binary}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)

    def _get_skill_description(self, name: str) -> str:
        meta = self.get_skill_metadata(name)
        return meta.get("description", name) if meta else name