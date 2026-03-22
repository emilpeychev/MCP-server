from __future__ import annotations

from pathlib import Path

import yaml

from ..retrieval import get_index_stats
from . import iter_yaml_files


def inspect_gateway_routes(hostname: str | None = None) -> dict:
    repo_path = Path(get_index_stats()["repo_path"])
    gateways = {}
    routes = []
    files = set()

    for path in iter_yaml_files(repo_path):
        content = path.read_text(encoding="utf-8", errors="ignore")
        try:
            documents = [doc for doc in yaml.safe_load_all(content) if isinstance(doc, dict)]
        except yaml.YAMLError:
            continue
        relative_path = str(path.relative_to(repo_path))
        for doc in documents:
            kind = doc.get("kind")
            metadata = doc.get("metadata", {})
            spec = doc.get("spec") or {}
            if kind == "Gateway":
                gateway_name = metadata.get("name", "unnamed")
                gateways[gateway_name] = {
                    "listeners": spec.get("listeners", []),
                    "file": relative_path,
                }
                files.add(relative_path)
            if kind == "HTTPRoute":
                route = _build_route(metadata, spec, relative_path)
                if hostname and hostname not in route["hostnames"]:
                    continue
                routes.append(route)
                files.add(relative_path)

    findings = []
    for route in routes:
        findings.extend(_route_findings(route, gateways))

    result = f"Inspected {len(routes)} HTTPRoutes and {len(gateways)} Gateways."
    return {
        "result": result,
        "files": sorted(files),
        "data": {"routes": routes, "gateways": gateways, "findings": findings},
    }


def _build_route(metadata: dict, spec: dict, relative_path: str) -> dict:
    matches = []
    for rule in spec.get("rules", []):
        for match in rule.get("matches", []):
            path_info = match.get("path") or {}
            matches.append({"type": path_info.get("type"), "value": path_info.get("value")})
    return {
        "name": metadata.get("name", "unnamed"),
        "hostnames": spec.get("hostnames", []),
        "parent_refs": [ref.get("name") for ref in spec.get("parentRefs", []) if ref.get("name")],
        "matches": matches,
        "file": relative_path,
    }


def _route_findings(route: dict, gateways: dict) -> list[dict]:
    findings = []
    if not route["parent_refs"]:
        findings.append({"severity": "error", "message": f"HTTPRoute {route['name']} is missing parentRefs."})
    if not route["hostnames"]:
        findings.append({"severity": "warning", "message": f"HTTPRoute {route['name']} has no hostnames."})
    for match in route["matches"]:
        if match.get("value") in {"/", "/*"}:
            findings.append({"severity": "warning", "message": f"HTTPRoute {route['name']} uses catch-all path {match.get('value')}."})
    for parent_ref in route["parent_refs"]:
        if parent_ref not in gateways:
            findings.append({"severity": "warning", "message": f"HTTPRoute {route['name']} references missing Gateway {parent_ref}."})
    return findings