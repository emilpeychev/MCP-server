"""Problem classifier — detects likely issue type from a question or log snippet.

Returns a ranked list of (pattern, confidence, signals) tuples.
Pure pattern matching, no ML, no LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

PATTERNS: dict[str, dict] = {
    "argocd_out_of_sync": {
        "keywords": ["out of sync", "outofsync", "sync failed", "comparisonerror", "argocd", "sync error", "app degraded"],
        "signals": ["ArgoCD sync failure or comparison error"],
    },
    "crashloop_backoff": {
        "keywords": ["crashloopbackoff", "crash loop", "back-off restarting", "container restart", "exit code 1", "exit code 137", "oomkilled"],
        "signals": ["Container restart loop detected"],
    },
    "image_pull_backoff": {
        "keywords": ["imagepullbackoff", "errimagepull", "image pull", "pull access denied", "manifest unknown", "repository does not exist"],
        "signals": ["Image pull failure"],
    },
    "service_unreachable": {
        "keywords": ["connection refused", "no endpoints", "service unreachable", "service has no endpoints", "upstream connect error", "dial tcp"],
        "signals": ["Service connectivity failure"],
    },
    "ingress_routing_failure": {
        "keywords": ["ingress", "404 not found", "backend not found", "default backend", "no matching rule", "host not found"],
        "signals": ["Ingress routing mismatch"],
    },
    "gateway_backend_failure": {
        "keywords": ["httproute", "gateway", "parentref", "backendref", "no matching parent", "backendrefinvalid", "refnotpermitted"],
        "signals": ["Gateway API backend or ref failure"],
    },
    "probe_failure": {
        "keywords": ["liveness probe failed", "readiness probe failed", "startup probe failed", "unhealthy", "probe failed"],
        "signals": ["Health probe failure"],
    },
    "helm_values_mismatch": {
        "keywords": ["helm", "values", "override", "template error", "render error", "nil pointer", "values.yaml"],
        "signals": ["Helm values or template mismatch"],
    },
    "namespace_mismatch": {
        "keywords": ["namespace", "not found in namespace", "namespaceselector", "namespace mismatch", "wrong namespace"],
        "signals": ["Namespace mismatch"],
    },
    "port_mismatch": {
        "keywords": ["port", "targetport", "containerport", "port mismatch", "connection refused", "wrong port"],
        "signals": ["Port configuration mismatch"],
    },
    "rbac_denial": {
        "keywords": ["forbidden", "rbac", "serviceaccount", "cannot list", "cannot get", "clusterrolebinding", "rolebinding", "unauthorized"],
        "signals": ["RBAC permission denial"],
    },
}


@dataclass
class Classification:
    pattern: str
    confidence: float
    signals: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)


def classify(text: str, top_n: int = 3) -> list[Classification]:
    """Classify the input text against known problem patterns.

    Returns up to *top_n* matches sorted by confidence (descending).
    """
    lowered = text.lower()
    results: list[Classification] = []

    for pattern_name, definition in PATTERNS.items():
        matched = [kw for kw in definition["keywords"] if kw in lowered]
        if not matched:
            continue
        # confidence = fraction of keywords matched, capped at 1.0
        confidence = round(min(len(matched) / max(len(definition["keywords"]) * 0.4, 1), 1.0), 2)
        results.append(Classification(
            pattern=pattern_name,
            confidence=confidence,
            signals=definition["signals"],
            matched_keywords=matched,
        ))

    results.sort(key=lambda c: c.confidence, reverse=True)
    return results[:top_n]


def classify_to_dict(text: str, top_n: int = 3) -> dict:
    """Classify and return MCP-friendly dict."""
    classifications = classify(text, top_n)
    if not classifications:
        return {
            "result": "No known problem pattern detected.",
            "files": [],
            "data": {"classifications": [], "top_pattern": None},
        }
    top = classifications[0]
    return {
        "result": f"Detected pattern: {top.pattern} (confidence: {top.confidence})",
        "files": [],
        "data": {
            "classifications": [
                {
                    "pattern": c.pattern,
                    "confidence": c.confidence,
                    "signals": c.signals,
                    "matched_keywords": c.matched_keywords,
                }
                for c in classifications
            ],
            "top_pattern": top.pattern,
        },
    }
