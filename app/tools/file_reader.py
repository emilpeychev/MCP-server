from __future__ import annotations

from pathlib import Path

from ..retrieval import get_index_stats

DEFAULT_MAX_LINES = 40
DEFAULT_MAX_CHARS = 2500


def read_file_slice(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict:
    """Read a small slice of a file from the indexed repo."""
    repo_path = Path(get_index_stats()["repo_path"]).resolve()
    full_path = (repo_path / path).resolve()

    if not str(full_path).startswith(str(repo_path)):
        return {"result": "Path outside repository.", "files": [], "data": {}}

    if not full_path.is_file():
        return {"result": f"File not found: {path}", "files": [], "data": {}}

    content = full_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    total_lines = len(lines)

    start = max(1, start_line)
    end = min(total_lines, end_line if end_line is not None else start + DEFAULT_MAX_LINES - 1)

    selected = lines[start - 1 : end]
    text = "\n".join(selected)

    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated at max_chars]"

    return {
        "result": f"{path} lines {start}-{end} of {total_lines}.",
        "files": [path],
        "data": {
            "path": path,
            "start_line": start,
            "end_line": end,
            "total_lines": total_lines,
            "content": text,
        },
    }
