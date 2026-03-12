from __future__ import annotations

from pathlib import Path

import yaml

from ..retrieval import get_index_stats


def inspect_argocd_applications(app_name: str | None = None) -> dict:
    repo_path = Path(get_index_stats()["repo_path"])
    applications = []
    files = []

    for path in _iter_yaml_files(repo_path):
        content = path.read_text(encoding="utf-8", errors="ignore")
        try:
            documents = [doc for doc in yaml.safe_load_all(content) if isinstance(doc, dict)]
        except yaml.YAMLError:
            continue
        for doc in documents:
            if doc.get("kind") != "Application":
                continue
            metadata = doc.get("metadata", {})
            name = metadata.get("name", "unnamed")
            if app_name and name != app_name:
                continue
            spec = doc.get("spec", {})
            findings = _application_findings(name, spec)
            relative_path = str(path.relative_to(repo_path))
            files.append(relative_path)
            applications.append(
                {
                    "name": name,
                    "project": spec.get("project"),
                    "source_path": (spec.get("source") or {}).get("path"),
                    "repo_url": (spec.get("source") or {}).get("repoURL"),
                    "destination_namespace": (spec.get("destination") or {}).get("namespace"),
                    "automated_sync": bool(((spec.get("syncPolicy") or {}).get("automated")) is not None),
                    "findings": findings,
                    "file": relative_path,
                }
            )

    result = f"Inspected {len(applications)} ArgoCD applications."
    return {"result": result, "files": files, "data": {"applications": applications}}


def _application_findings(name: str, spec: dict) -> list[dict]:
    findings = []
    source = spec.get("source") or {}
    destination = spec.get("destination") or {}
    sync_policy = spec.get("syncPolicy") or {}

    if not source.get("repoURL"):
        findings.append({"severity": "error", "message": f"Application {name} is missing source.repoURL."})
    if not source.get("path") and not source.get("chart"):
        findings.append({"severity": "error", "message": f"Application {name} has neither source.path nor source.chart."})
    if not destination.get("server") and not destination.get("name"):
        findings.append({"severity": "warning", "message": f"Application {name} does not declare destination.server or destination.name."})
    if not destination.get("namespace"):
        findings.append({"severity": "warning", "message": f"Application {name} has no destination namespace."})
    if sync_policy.get("automated") and not sync_policy.get("syncOptions"):
        findings.append({"severity": "info", "message": f"Application {name} enables automated sync without explicit syncOptions."})
    return findings


def _iter_yaml_files(repo_path: Path):
    if not repo_path.exists():
        return []
    files = []
    for path in repo_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml"} and ".git" not in path.parts:
            files.append(path)
    return files