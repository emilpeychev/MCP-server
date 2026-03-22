from __future__ import annotations

from pathlib import Path

import yaml

from ..cache import tool_cache
from ..retrieval import get_index_stats

DEFAULT_MAX_CHARS_PER_FILE = 1500
DEFAULT_TOTAL_BUDGET = 8000


def summarize_files(
    paths: list[str],
    max_chars_per_file: int = DEFAULT_MAX_CHARS_PER_FILE,
    total_budget: int = DEFAULT_TOTAL_BUDGET,
) -> dict:
    """Summarize one or more files. Returns structured overview per file, not full content."""
    cache_key = tool_cache.key("summarize_files", *sorted(paths), str(max_chars_per_file), str(total_budget))
    cached = tool_cache.get(cache_key)
    if cached is not None:
        return cached

    # Auto-adjust per-file limit if total budget would be exceeded
    if len(paths) > 0:
        max_chars_per_file = min(max_chars_per_file, total_budget // max(len(paths), 1))

    repo_path = Path(get_index_stats()["repo_path"]).resolve()
    summaries: list[dict] = []
    resolved_files: list[str] = []

    for rel_path in paths:
        full_path = (repo_path / rel_path).resolve()
        if not full_path.is_relative_to(repo_path):
            summaries.append({"path": rel_path, "error": "Path outside repository."})
            continue
        if not full_path.is_file():
            summaries.append({"path": rel_path, "error": "File not found."})
            continue

        content = full_path.read_text(encoding="utf-8", errors="ignore")
        line_count = len(content.splitlines())
        char_count = len(content)
        suffix = full_path.suffix.lower()

        summary: dict = {
            "path": rel_path,
            "lines": line_count,
            "chars": char_count,
            "type": _file_type(suffix),
        }

        if suffix in {".yaml", ".yml"}:
            summary["k8s_objects"] = _extract_k8s_summary(content)

        preview = _smart_preview(content, max_chars_per_file)
        summary["preview"] = preview

        summaries.append(summary)
        resolved_files.append(rel_path)

    result = f"Summarized {len(resolved_files)} files."
    output = {"result": result, "files": resolved_files, "data": {"summaries": summaries}}
    tool_cache.put(cache_key, output)
    return output


def _smart_preview(content: str, max_chars: int) -> str:
    """Return head + tail preview for large files, plain slice for small ones."""
    if len(content) <= max_chars:
        return content
    # 70% head, 30% tail
    head_budget = int(max_chars * 0.7)
    tail_budget = max_chars - head_budget - 30  # reserve for separator
    head = content[:head_budget]
    tail = content[-tail_budget:] if tail_budget > 0 else ""
    return f"{head}\n... [{len(content) - max_chars} chars omitted] ...\n{tail}"


def _file_type(suffix: str) -> str:
    type_map = {
        ".yaml": "yaml",
        ".yml": "yaml",
        ".tf": "terraform",
        ".py": "python",
        ".md": "markdown",
        ".json": "json",
    }
    return type_map.get(suffix, "text")


def _extract_k8s_summary(content: str) -> list[dict]:
    try:
        documents = [doc for doc in yaml.safe_load_all(content) if isinstance(doc, dict)]
    except yaml.YAMLError:
        return []
    objects = []
    for doc in documents:
        kind = doc.get("kind")
        if kind:
            metadata = doc.get("metadata", {})
            objects.append({
                "kind": kind,
                "name": metadata.get("name", ""),
                "namespace": metadata.get("namespace", ""),
            })
    return objects
