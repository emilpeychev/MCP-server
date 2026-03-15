DEFAULT_MAX_CHARS = 3000


def compress_logs(log_text: str, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    """Compress raw logs into structured signals and suggestions. Returns a short summary, not raw logs."""
    lowered = log_text.lower()
    signals = []
    suggestions = []
    log_type = "generic"

    if "argocd" in lowered or "comparisonerror" in lowered or "sync failed" in lowered:
        log_type = "argocd"
        signals.append("ArgoCD sync or comparison failure markers detected.")
        suggestions.append("Check Application status, repo revision, and manifest generation errors.")
    if "tekton" in lowered or "taskrun" in lowered or "pipelinerun" in lowered:
        log_type = "tekton"
        signals.append("Tekton pipeline failure markers detected.")
        suggestions.append("Inspect TaskRun step logs, workspace bindings, and image pull permissions.")
    if "crashloopbackoff" in lowered or "back-off restarting failed container" in lowered:
        signals.append("Container restart loop detected.")
        suggestions.append("Check previous container logs, probes, and runtime configuration.")
    if "imagepullbackoff" in lowered or "errimagepull" in lowered:
        signals.append("Image pull failure detected.")
        suggestions.append("Verify image reference, registry credentials, and network reachability.")
    if "forbidden" in lowered and "serviceaccount" in lowered:
        signals.append("RBAC denial detected.")
        suggestions.append("Review RoleBinding or ClusterRoleBinding for the referenced service account.")

    if not signals:
        signals.append("No specific platform failure signature matched.")
        suggestions.append("Review the first error event and correlate with recent rollout or GitOps changes.")

    # Extract a compressed excerpt of the most relevant lines
    excerpt = _extract_key_lines(log_text, max_chars)

    return {
        "result": f"Detected {log_type} log patterns with {len(signals)} signal(s).",
        "files": [],
        "data": {
            "log_type": log_type,
            "signals": signals,
            "suggestions": suggestions,
            "excerpt": excerpt,
        },
    }


def _extract_key_lines(log_text: str, max_chars: int) -> str:
    """Pick the most informative lines from the log, staying under max_chars."""
    error_keywords = {"error", "fail", "fatal", "exception", "denied", "crash", "timeout", "refused"}
    lines = log_text.splitlines()

    key_lines = [line for line in lines if any(kw in line.lower() for kw in error_keywords)]

    if not key_lines:
        key_lines = lines[:20]

    result = "\n".join(key_lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [truncated]"
    return result


def analyze_log(log_text: str) -> dict:
    """Legacy alias for compress_logs."""
    return compress_logs(log_text)