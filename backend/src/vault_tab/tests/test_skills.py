"""Skills tests — load from YAML, prompt templating with context files."""

import tempfile
from pathlib import Path

import pytest

from src.vault_tab.core.skills import Skill, SkillLoader


DEMO_VAULT = Path("/tmp/vibeflow/agent/demo-vault")


class TestSkillLoader:
    def test_load_all_demo_skills(self):
        loader = SkillLoader(DEMO_VAULT)
        skills = loader.load_all()
        ids = {s.id for s in skills}
        assert len(skills) >= 4
        assert "plan-today" in ids
        assert "inbox-brief" in ids
        assert "wk-review" in ids
        assert "vault-clean" in ids

    def test_load_empty_dir(self, tmp_path: Path):
        root = tmp_path / "vault"
        root.mkdir()
        (root / "90-system" / "skills").mkdir(parents=True)
        loader = SkillLoader(root)
        assert loader.load_all() == []

    def test_load_missing_skills_dir(self, tmp_path: Path):
        root = tmp_path / "vault"
        (root / "90-system").mkdir(parents=True)
        loader = SkillLoader(root)
        assert loader.load_all() == []

    def test_load_skips_invalid_yaml(self, tmp_path: Path):
        root = tmp_path / "vault"
        skills_dir = root / "90-system" / "skills"
        skills_dir.mkdir(parents=True)
        # Write invalid YAML
        (skills_dir / "bad.yaml").write_text("{{invalid yaml}}")
        # Write valid YAML
        (skills_dir / "good.yaml").write_text("id: good-skill\ndescription: Works\n")
        loader = SkillLoader(root)
        skills = loader.load_all()
        assert len(skills) == 1
        assert skills[0].id == "good-skill"

    def test_load_skips_yaml_without_id(self, tmp_path: Path):
        root = tmp_path / "vault"
        skills_dir = root / "90-system" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "no-id.yaml").write_text("description: no id field\n")
        loader = SkillLoader(root)
        assert loader.load_all() == []

    def test_load_yml_extension(self, tmp_path: Path):
        root = tmp_path / "vault"
        skills_dir = root / "90-system" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "test.yml").write_text("id: yml-skill\n")
        loader = SkillLoader(root)
        skills = loader.load_all()
        assert any(s.id == "yml-skill" for s in skills)


class TestSkill:
    def test_from_dict(self):
        data = {
            "id": "test",
            "label": "Test Skill",
            "description": "A test skill",
            "prompt_template": "Hello $date",
            "context_files": ["test.md"],
            "output": {"path": "out.md", "mode": "create"},
            "tags": ["test"],
        }
        skill = Skill(data)
        assert skill.id == "test"
        assert skill.label == "Test Skill"
        assert skill.output_path == "out.md"
        assert skill.output_mode == "create"

    def test_default_label_from_id(self):
        data = {"id": "my-skill"}
        skill = Skill(data)
        assert skill.label == "MY SKILL"

    def test_to_dict(self):
        data = {
            "id": "test",
            "labels": "Test",
            "context_files": ["a.md"],
            "output": {"path": "b.md", "mode": "overwrite"},
            "tags": ["x"],
        }
        skill = Skill(data)
        d = skill.to_dict()
        assert d["id"] == "test"
        assert d["output_path"] == "b.md"
        assert d["output_mode"] == "overwrite"

    def test_build_prompt_substitutes_date(self):
        data = {
            "id": "test",
            "prompt_template": "Today is $date and time is $time\nContext:\n$context\nInput: $input_params\n",
        }
        skill = Skill(data)
        prompt = skill.build_prompt(["line 1", "line 2"], "my input")
        assert "2026" in prompt  # current year
        assert "line 1" in prompt
        assert "line 2" in prompt
        assert "my input" in prompt

    def test_build_prompt_unsafe_vars(self):
        """Template.substitute would fail on undefined vars; safe_substitute ignores them."""
        data = {
            "id": "test",
            "prompt_template": "Hello $date, $unknown_var",
        }
        skill = Skill(data)
        prompt = skill.build_prompt([], "")
        # safe_substitute leaves $unknown_var as-is
        assert "$unknown_var" in prompt


class TestResolveContextFiles:
    def test_resolve_context_from_demo_vault(self):
        loader = SkillLoader(DEMO_VAULT)
        skills = loader.load_all()
        plan_skill = next(s for s in skills if s.id == "plan-today")
        contents = loader.resolve_context_files(plan_skill)
        # Should at least find the daily note
        assert any("2026-07-03" in c for c in contents)

    def test_resolve_nonexistent_pattern(self, tmp_path: Path):
        root = tmp_path / "vault"
        root.mkdir()
        (root / "90-system" / "skills").mkdir(parents=True)
        data = {"id": "test", "context_files": ["nonexistent/*.md"]}
        skill = Skill(data)
        loader = SkillLoader(root)
        contents = loader.resolve_context_files(skill)
        assert contents == []
