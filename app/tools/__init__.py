from __future__ import annotations

from pathlib import Path

from ..retrieval import IGNORED_PARTS


def iter_yaml_files(repo_path: Path) -> list[Path]:
    """Shared helper to iterate YAML files in a repo, skipping ignored directories."""
    if not repo_path.exists():
        return []
    return [
        path
        for path in repo_path.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".yaml", ".yml"}
        and not any(part in IGNORED_PARTS for part in path.parts)
    ]