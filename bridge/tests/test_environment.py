"""Smoke tests for Phase 0 environment scaffolding."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_requirements_lists_anthropic_and_pyyaml():
    text = (REPO_ROOT / "bridge" / "requirements.txt").read_text(encoding="utf-8")
    assert "anthropic>=0.39.0" in text
    assert "pyyaml>=6.0" in text
    assert "pytest-asyncio" in text


def test_anthropic_template_exists():
    tpl = REPO_ROOT / "templates" / "anthropic.yaml.template"
    assert tpl.exists(), "templates/anthropic.yaml.template must exist"
    assert "api_key:" in tpl.read_text(encoding="utf-8")


def test_gitignore_blocks_project_anthropic_yaml():
    gi = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "config/anthropic.yaml" in gi
