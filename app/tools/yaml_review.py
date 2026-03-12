from collections import Counter

import yaml


def review_yaml(yaml_content: str) -> dict:
    try:
        documents = [doc for doc in yaml.safe_load_all(yaml_content) if isinstance(doc, dict)]
    except yaml.YAMLError as exc:
        return {
            "result": "Unable to parse YAML content.",
            "files": [],
            "data": {"findings": [{"severity": "error", "message": str(exc), "kind": "yaml-parse"}], "documents": 0},
        }
    findings = []
    hostnames = []

    for doc in documents:
        kind = doc.get("kind", "Unknown")
        metadata = doc.get("metadata", {})
        name = metadata.get("name", "unnamed")
        spec = doc.get("spec", {})

        hostnames.extend(_extract_hostnames(kind, spec))
        findings.extend(_load_balancer_checks(kind, name, spec))
        findings.extend(_gateway_checks(kind, name, spec))

    duplicates = [hostname for hostname, count in Counter(hostnames).items() if count > 1]
    for hostname in duplicates:
        findings.append(
            {
                "severity": "warning",
                "message": f"Duplicate hostname wiring detected for {hostname}.",
                "kind": "hostname",
            }
        )

    summary = f"Detected {len(findings)} YAML review findings across {len(documents)} documents."
    return {"result": summary, "files": [], "data": {"findings": findings, "documents": len(documents)}}


def _extract_hostnames(kind: str, spec: dict) -> list[str]:
    if kind == "Ingress":
        return [rule.get("host") for rule in spec.get("rules", []) if rule.get("host")]
    if kind == "HTTPRoute":
        return [hostname for hostname in spec.get("hostnames", []) if hostname]
    if kind == "Gateway":
        listeners = spec.get("listeners", [])
        return [listener.get("hostname") for listener in listeners if listener.get("hostname")]
    return []


def _load_balancer_checks(kind: str, name: str, spec: dict) -> list[dict]:
    findings = []
    if kind == "Service" and spec.get("type") == "LoadBalancer":
        if spec.get("externalIPs"):
            findings.append(
                {
                    "severity": "warning",
                    "message": f"Service {name} uses LoadBalancer together with externalIPs.",
                    "kind": "service",
                }
            )
        if not spec.get("ports"):
            findings.append(
                {
                    "severity": "error",
                    "message": f"Service {name} is type LoadBalancer without any ports.",
                    "kind": "service",
                }
            )
    return findings


def _gateway_checks(kind: str, name: str, spec: dict) -> list[dict]:
    findings = []
    if kind != "HTTPRoute":
        return findings

    if not spec.get("parentRefs"):
        findings.append(
            {
                "severity": "error",
                "message": f"HTTPRoute {name} is missing parentRefs.",
                "kind": "gateway-api",
            }
        )
    if not spec.get("hostnames"):
        findings.append(
            {
                "severity": "warning",
                "message": f"HTTPRoute {name} has no hostnames and may match broadly.",
                "kind": "gateway-api",
            }
        )

    for rule in spec.get("rules", []):
        for match in rule.get("matches", []):
            path = (match.get("path") or {}).get("value")
            if path in {"/", "/*"}:
                findings.append(
                    {
                        "severity": "warning",
                        "message": f"HTTPRoute {name} contains a catch-all path match {path}.",
                        "kind": "gateway-api",
                    }
                )
    return findings