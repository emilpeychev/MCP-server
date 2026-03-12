import shutil
import subprocess
from pathlib import Path


def render_helm(chart_path: str, values_file: str | None = None) -> dict:
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
            "data": {"rendered": completed.stdout, "errors": [completed.stderr.strip() or "helm template failed"]},
        }

    return {"result": "Helm chart rendered successfully.", "files": referenced_files, "data": {"rendered": completed.stdout, "errors": []}}