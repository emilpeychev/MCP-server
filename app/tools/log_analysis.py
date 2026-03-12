def analyze_log(log_text: str) -> dict:
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

    return {
        "result": f"Detected {log_type} log patterns with {len(signals)} signals.",
        "files": [],
        "data": {"log_type": log_type, "signals": signals, "suggestions": suggestions},
    }