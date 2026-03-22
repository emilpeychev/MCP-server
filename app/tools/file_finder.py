from __future__ import annotations

from pathlib import Path

from ..retrieval import SUPPORTED_SUFFIXES, IGNORED_PARTS, get_index_stats


def find_related_files(path: str, max_results: int = 5) -> dict:
    """Find files related to a given file by directory proximity and name similarity."""
    repo_path = Path(get_index_stats()["repo_path"]).resolve()
    target = (repo_path / path).resolve()

    if not target.is_relative_to(repo_path):
        return {"result": "Path outside repository.", "files": [], "data": {}}

    related: list[str] = []
    seen: set[str] = set()

    # Siblings in same directory
    parent = target.parent
    if parent.exists():
        for sibling in sorted(parent.iterdir()):
            if (
                sibling.is_file()
                and sibling != target
                and sibling.suffix.lower() in SUPPORTED_SUFFIXES
                and not any(part in IGNORED_PARTS for part in sibling.parts)
            ):
                rel = str(sibling.relative_to(repo_path))
                if rel not in seen:
                    seen.add(rel)
                    related.append(rel)

    # Files with similar stem elsewhere
    stem = target.stem.lower()
    if len(related) < max_results:
        for candidate in repo_path.rglob("*"):
            if (
                candidate.is_file()
                and candidate != target
                and candidate.suffix.lower() in SUPPORTED_SUFFIXES
                and not any(part in IGNORED_PARTS for part in candidate.parts)
                and stem in candidate.stem.lower()
            ):
                rel = str(candidate.relative_to(repo_path))
                if rel not in seen:
                    seen.add(rel)
                    related.append(rel)
            if len(related) >= max_results:
                break

    related = related[:max_results]
    return {
        "result": f"Found {len(related)} files related to {path}.",
        "files": related,
        "data": {"anchor": path, "related": related},
    }
