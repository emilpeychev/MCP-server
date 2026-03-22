from __future__ import annotations

from pathlib import Path

import yaml

from ..retrieval import IGNORED_PARTS, get_index_stats
from . import iter_yaml_files


def find_k8s_objects(
    kind: str | None = None,
    name: str | None = None,
    namespace: str | None = None,
    max_results: int = 10,
) -> dict:
    """Find Kubernetes objects by kind, name, or namespace. Returns metadata only, not full content."""
    repo_path = Path(get_index_stats()["repo_path"]).resolve()
    objects: list[dict] = []
    files: set[str] = set()

    for file_path in iter_yaml_files(repo_path):
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        try:
            documents = [doc for doc in yaml.safe_load_all(content) if isinstance(doc, dict)]
        except yaml.YAMLError:
            continue

        relative = str(file_path.relative_to(repo_path))
        for doc in documents:
            obj_kind = doc.get("kind")
            if not obj_kind:
                continue

            metadata = doc.get("metadata", {})
            obj_name = metadata.get("name", "")
            obj_namespace = metadata.get("namespace", "")

            if kind and obj_kind.lower() != kind.lower():
                continue
            if name and name.lower() not in obj_name.lower():
                continue
            if namespace and obj_namespace.lower() != namespace.lower():
                continue

            objects.append({
                "kind": obj_kind,
                "name": obj_name,
                "namespace": obj_namespace,
                "file": relative,
            })
            files.add(relative)

            if len(objects) >= max_results:
                break
        if len(objects) >= max_results:
            break

    return {
        "result": f"Found {len(objects)} Kubernetes objects.",
        "files": sorted(files),
        "data": {"objects": objects},
    }
