"""Core modules."""

import yaml


def parse_frontmatter_static(text: str) -> dict:
    """Extract YAML frontmatter from markdown text."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}
    try:
        parts = stripped.split("---", 2)
        if len(parts) >= 2:
            return yaml.safe_load(parts[1]) or {}
    except Exception:
        pass
    return {}
