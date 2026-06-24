from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..config import get_config_value
from ..retrieval import get_index_stats

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_OUTPUT_CHARS = 8000


def _repo_root() -> Path:
    stats = get_index_stats()
    return Path(stats.get("repo_path", "/repo")).resolve()


def _graphify_binary() -> str:
    return get_config_value("GRAPHIFY_BIN", "graphify")


def _graph_file(repo_root: Path) -> Path:
    return repo_root / "graphify-out" / "graph.json"


def _graph_file_relative(repo_root: Path) -> str:
    return str(_graph_file(repo_root).relative_to(repo_root))


def _trim_output(stdout: str, stderr: str, max_chars: int = DEFAULT_MAX_OUTPUT_CHARS) -> str:
    parts = []
    clean_stdout = stdout.strip()
    clean_stderr = stderr.strip()

    if clean_stdout:
        parts.append(clean_stdout)
    if clean_stderr:
        parts.append("[stderr]\n" + clean_stderr)

    if not parts:
        return ""

    merged = "\n\n".join(parts)
    if len(merged) > max_chars:
        return merged[:max_chars] + "\n... [truncated]"
    return merged


def _not_ready_result(reason: str, repo_root: Path) -> dict:
    graph_path = _graph_file(repo_root)
    graph_relative = _graph_file_relative(repo_root)
    graph_exists = graph_path.is_file()

    return {
        "result": reason,
        "files": [graph_relative] if graph_exists else [],
        "data": {
            "ok": False,
            "repo_path": str(repo_root),
            "graph_path": str(graph_path),
            "graph_exists": graph_exists,
            "graphify_bin": _graphify_binary(),
            "graphify_resolved_bin": shutil.which(_graphify_binary()),
        },
    }


def _invoke_graphify(subcommand: list[str]) -> dict:
    repo_root = _repo_root()
    graph_path = _graph_file(repo_root)
    graph_relative = _graph_file_relative(repo_root)
    graphify_bin = _graphify_binary()
    resolved_bin = shutil.which(graphify_bin)

    if resolved_bin is None:
        return _not_ready_result(
            "Graphify CLI is not available. Install graphifyy or set GRAPHIFY_BIN to a valid binary.",
            repo_root,
        )

    if not graph_path.is_file():
        return _not_ready_result(
            "Graphify graph not found at graphify-out/graph.json in the indexed repo. Build it first, then query it.",
            repo_root,
        )

    command = [resolved_bin, *subcommand]
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "result": "Graphify command timed out.",
            "files": [graph_relative],
            "data": {
                "ok": False,
                "repo_path": str(repo_root),
                "graph_path": str(graph_path),
                "graph_exists": True,
                "graphify_bin": graphify_bin,
                "graphify_resolved_bin": resolved_bin,
                "command": command,
                "exit_code": None,
                "output": "",
            },
        }

    output = _trim_output(completed.stdout, completed.stderr)
    ok = completed.returncode == 0
    return {
        "result": "Graphify command completed." if ok else "Graphify command failed.",
        "files": [graph_relative],
        "data": {
            "ok": ok,
            "repo_path": str(repo_root),
            "graph_path": str(graph_path),
            "graph_exists": True,
            "graphify_bin": graphify_bin,
            "graphify_resolved_bin": resolved_bin,
            "command": command,
            "exit_code": completed.returncode,
            "output": output,
        },
    }


def graphify_status() -> dict:
    repo_root = _repo_root()
    graph_path = _graph_file(repo_root)
    graph_relative = _graph_file_relative(repo_root)
    graphify_bin = _graphify_binary()
    resolved_bin = shutil.which(graphify_bin)
    graph_exists = graph_path.is_file()

    status_lines = []
    if resolved_bin:
        status_lines.append(f"Graphify CLI is available: {resolved_bin}")
    else:
        status_lines.append("Graphify CLI is not available on PATH.")
    if graph_exists:
        status_lines.append(f"Graph file found: {graph_relative}")
    else:
        status_lines.append(f"Graph file missing: {graph_relative}")

    return {
        "result": " ".join(status_lines),
        "files": [graph_relative] if graph_exists else [],
        "data": {
            "repo_path": str(repo_root),
            "graph_path": str(graph_path),
            "graph_exists": graph_exists,
            "graphify_bin": graphify_bin,
            "graphify_resolved_bin": resolved_bin,
        },
    }


def graphify_query(question: str, dfs: bool = False, budget: int | None = None) -> dict:
    command = ["query", question]
    if dfs:
        command.append("--dfs")
    if budget is not None:
        command.extend(["--budget", str(budget)])

    result = _invoke_graphify(command)
    if result["data"].get("ok"):
        result["result"] = "Graphify query completed."
    return result


def graphify_path(source: str, target: str) -> dict:
    result = _invoke_graphify(["path", source, target])
    if result["data"].get("ok"):
        result["result"] = "Graphify path lookup completed."
    return result


def graphify_explain(node: str) -> dict:
    result = _invoke_graphify(["explain", node])
    if result["data"].get("ok"):
        result["result"] = "Graphify explain completed."
    return result