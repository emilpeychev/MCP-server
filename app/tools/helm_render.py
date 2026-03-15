import shutil
import subprocess
from pathlib import Path

DEFAULT_MAX_CHARS = 4000


def render_helm(chart_path: str, values_file: str | None = None, summary_only: bool = True, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    """Render a Helm chart. Returns a summary by default; set summary_only=False for full output."""
    if shutil.which("helm") is None:
        return {"result": "Helm CLI is not installed.", "files": [], "data": {"rendered": "", "errors": ["helm not found"]}}

    resolved_chart = Path(chart_path)
    if not resolved_chart.exists():
        return {"result": f"Chart path {chart_path} does not exist.", "files": [], "data": {"rendered": "", "errors": ["chart path missing"]}}

    command = ["helm", "template", resolved_chart.as_posix()]
    referenced_files = [resolved_chart.as_posix()]
    if values_file:
        command.extend(["-f", values_file])
        referenced_files.append(values_file)

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return {
            "result": "Helm render failed.",
            "files": referenced_files,
            "data": {"rendered": "", "errors": [completed.stderr.strip() or "helm template failed"]},
        }

    rendered = completed.stdout

    if summary_only:
        summary = _summarize_rendered(rendered, max_chars)
        return {
            "result": f"Helm chart rendered successfully. {summary['object_count']} objects produced.",
            "files": referenced_files,
            "data": {
                "objects": summary["objects"],
                "object_count": summary["object_count"],
                "total_chars": len(rendered),
                "preview": summary["preview"],
                "errors": [],
            },
        }

    output = rendered
    if len(output) > max_chars:
        output = output[:max_chars] + "\n... [truncated at max_chars]"

    return {"result": "Helm chart rendered successfully.", "files": referenced_files, "data": {"rendered": output, "errors": []}}


def _summarize_rendered(rendered: str, max_chars: int) -> dict:
    """Extract a summary of rendered Helm objects."""
    import yaml

    objects: list[dict] = []
    try:
        for doc in yaml.safe_load_all(rendered):
            if isinstance(doc, dict) and doc.get("kind"):
                metadata = doc.get("metadata", {})
                objects.append({
                    "kind": doc["kind"],
                    "name": metadata.get("name", ""),
                    "namespace": metadata.get("namespace", ""),
                })
    except yaml.YAMLError:
        pass

    preview = rendered[:max_chars]
    if len(rendered) > max_chars:
        preview += "\n... [truncated]"

    return {"objects": objects, "object_count": len(objects), "preview": preview}