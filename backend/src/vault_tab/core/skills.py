"""Skill YAML loader and prompt templating."""

import time
from pathlib import Path
from string import Template
from typing import Any

import yaml


class Skill:
    def __init__(self, data: dict[str, Any]):
        self.id: str = data["id"]
        self.label: str = data.get("label", self.id.upper().replace("-", " "))
        self.description: str = data.get("description", "")
        self.prompt_template: str = data.get("prompt_template", "")
        self.context_files: list[str] = data.get("context_files", [])
        output = data.get("output", {})
        self.output_path: str = output.get("path", "")
        self.output_mode: str = output.get("mode", "create")
        self.tags: list[str] = data.get("tags", [])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "context_files": self.context_files,
            "output_path": self.output_path,
            "output_mode": self.output_mode,
            "tags": self.tags,
        }

    def build_prompt(self, context_files: list[str], input_params: str = "") -> str:
        now = time.strftime("%Y-%m-%d")
        now_time = time.strftime("%H:%M")
        context_text = "\n".join(context_files)
        template = Template(self.prompt_template)
        return template.safe_substitute(
            date=now,
            time=now_time,
            context=context_text,
            input_params=input_params,
        )


class SkillLoader:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root.resolve()
        self.skills_dir = vault_root / "90-system" / "skills"

    def load_all(self) -> list[Skill]:
        if not self.skills_dir.exists():
            return []
        skills = []
        for yaml_file in self.skills_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if data and isinstance(data, dict) and "id" in data:
                    skills.append(Skill(data))
            except Exception:
                continue
        for yaml_file in self.skills_dir.glob("*.yml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if data and isinstance(data, dict) and "id" in data:
                    skills.append(Skill(data))
            except Exception:
                continue
        return skills

    def resolve_context_files(self, skill: Skill) -> list[str]:
        contents = []
        now = time.strftime("%Y-%m-%d")
        for glob_pattern in skill.context_files:
            pattern = glob_pattern.replace("{{date}}", now)
            for matched in self.vault_root.glob(pattern):
                try:
                    text = matched.read_text(encoding="utf-8", errors="replace")
                    rel = str(matched.relative_to(self.vault_root))
                    contents.append(f"--- {rel} ---\n{text}")
                except (OSError, UnicodeDecodeError):
                    continue
        return contents
