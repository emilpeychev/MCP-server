"""Troubleshooting playbooks — per-pattern definitions of what to check and in what order.

Each playbook defines:
- steps: ordered list of checks with tool name and arguments template
- common_root_causes: likely causes to present if evidence matches
- stop_conditions: when to stop investigating
- missing_evidence: what to flag if not found
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlaybookStep:
    description: str
    tool: str
    args_hint: dict = field(default_factory=dict)
    # If True, this step requires cluster access (stub for now)
    requires_cluster: bool = False


@dataclass(frozen=True)
class Playbook:
    pattern: str
    steps: list[PlaybookStep]
    common_root_causes: list[str]
    stop_conditions: list[str]
    missing_evidence: list[str]
    key_resources: list[str]


# ---------------------------------------------------------------------------
# Playbook library
# ---------------------------------------------------------------------------

PLAYBOOKS: dict[str, Playbook] = {
    "crashloop_backoff": Playbook(
        pattern="crashloop_backoff",
        steps=[
            PlaybookStep("Search repo for deployment manifests", "search_repo", {"query": "Deployment containers"}),
            PlaybookStep("Find related K8s objects", "find_k8s_objects", {"kind": "Deployment"}),
            PlaybookStep("Read deployment YAML", "read_file_slice", {}),
            PlaybookStep("Review YAML for misconfigurations", "review_yaml", {}),
            PlaybookStep("Check pod restart count", "kubectl_get_pods", {}, requires_cluster=True),
            PlaybookStep("Check previous container logs", "kubectl_logs_previous", {}, requires_cluster=True),
            PlaybookStep("Check pod events", "kubectl_get_events", {}, requires_cluster=True),
            PlaybookStep("Summarize relevant files", "summarize_files", {}),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Missing or incorrect environment variable",
            "OOMKilled — memory limit too low",
            "Bad entrypoint or command",
            "Missing config map or secret reference",
            "Liveness probe misconfiguration",
            "Image tag mismatch or missing image",
        ],
        stop_conditions=["Root cause identified in logs", "Pod is running after recent fix"],
        missing_evidence=["Previous container logs", "Pod events", "Resource limits"],
        key_resources=["Deployment", "Pod", "ConfigMap", "Secret"],
    ),
    "argocd_out_of_sync": Playbook(
        pattern="argocd_out_of_sync",
        steps=[
            PlaybookStep("Inspect ArgoCD applications", "inspect_argocd", {}),
            PlaybookStep("Search repo for ArgoCD Application manifests", "search_repo", {"query": "ArgoCD Application"}),
            PlaybookStep("Search repo for OpenTofu modules affecting app infra", "search_repo", {"query": "tofu terraform module"}),
            PlaybookStep("Find Helm values files", "search_repo", {"query": "values.yaml"}),
            PlaybookStep("Validate OpenTofu configuration", "opentofu_validate", {}, requires_cluster=True),
            PlaybookStep("Generate OpenTofu plan for drift check", "opentofu_plan", {}, requires_cluster=True),
            PlaybookStep("Render Helm chart and compare", "render_helm", {}),
            PlaybookStep("Get ArgoCD app status", "argocd_get_app", {}, requires_cluster=True),
            PlaybookStep("Get ArgoCD app events", "argocd_get_app_events", {}, requires_cluster=True),
            PlaybookStep("Summarize drift", "summarize_files", {}),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Values drift between repo and rendered manifest",
            "Manual cluster edit not in Git",
            "OpenTofu-managed infra drift from expected state",
            "Helm chart version mismatch",
            "Missing annotation or label change",
            "Target revision mismatch",
        ],
        stop_conditions=["Sync status is Synced", "Diff is empty"],
        missing_evidence=["Live ArgoCD app status", "Rendered manifest diff"],
        key_resources=["Application", "Deployment", "Service"],
    ),
    "image_pull_backoff": Playbook(
        pattern="image_pull_backoff",
        steps=[
            PlaybookStep("Search repo for image references", "search_repo", {"query": "image: container registry"}),
            PlaybookStep("Find Deployments with image specs", "find_k8s_objects", {"kind": "Deployment"}),
            PlaybookStep("Read deployment YAML for image tag", "read_file_slice", {}),
            PlaybookStep("Review YAML for image issues", "review_yaml", {}),
            PlaybookStep("Check pod events for pull errors", "kubectl_get_events", {}, requires_cluster=True),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Image tag does not exist in registry",
            "Registry credentials missing or expired (imagePullSecret)",
            "Private registry not accessible from cluster",
            "Typo in image name or registry URL",
        ],
        stop_conditions=["Image pull succeeds", "Correct image found in manifests"],
        missing_evidence=["Pod events", "imagePullSecrets configuration"],
        key_resources=["Deployment", "Pod", "Secret (imagePullSecret)"],
    ),
    "service_unreachable": Playbook(
        pattern="service_unreachable",
        steps=[
            PlaybookStep("Search for Service manifests", "search_repo", {"query": "Service selector port"}),
            PlaybookStep("Find Service objects", "find_k8s_objects", {"kind": "Service"}),
            PlaybookStep("Read Service YAML", "read_file_slice", {}),
            PlaybookStep("Find matching Deployment", "find_k8s_objects", {"kind": "Deployment"}),
            PlaybookStep("Review label selectors", "review_yaml", {}),
            PlaybookStep("Check endpoints", "kubectl_get_endpoints", {}, requires_cluster=True),
            PlaybookStep("Check target pods", "kubectl_get_pods", {}, requires_cluster=True),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Label selector mismatch between Service and Deployment",
            "Target port does not match container port",
            "No pods matching service selector",
            "Pods not ready (failing probes)",
        ],
        stop_conditions=["Endpoints populated", "Service resolves to healthy pods"],
        missing_evidence=["Live endpoints", "Pod readiness status"],
        key_resources=["Service", "Endpoints", "Deployment", "Pod"],
    ),
    "ingress_routing_failure": Playbook(
        pattern="ingress_routing_failure",
        steps=[
            PlaybookStep("Search for Ingress manifests", "search_repo", {"query": "Ingress host path"}),
            PlaybookStep("Find Ingress objects", "find_k8s_objects", {"kind": "Ingress"}),
            PlaybookStep("Read Ingress YAML", "read_file_slice", {}),
            PlaybookStep("Find backend Service", "find_k8s_objects", {"kind": "Service"}),
            PlaybookStep("Review Ingress rules", "review_yaml", {}),
            PlaybookStep("Check live Ingress", "kubectl_get_ingress", {}, requires_cluster=True),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Host or path rule does not match request",
            "Backend service name or port wrong",
            "TLS secret missing",
            "Ingress class not set or wrong",
        ],
        stop_conditions=["Ingress routes to correct backend"],
        missing_evidence=["Live Ingress status", "TLS certificate"],
        key_resources=["Ingress", "Service", "Secret (TLS)"],
    ),
    "gateway_backend_failure": Playbook(
        pattern="gateway_backend_failure",
        steps=[
            PlaybookStep("Inspect Gateway routes", "inspect_gateway", {}),
            PlaybookStep("Search for HTTPRoute manifests", "search_repo", {"query": "HTTPRoute backendRef"}),
            PlaybookStep("Find Gateway objects", "find_k8s_objects", {"kind": "Gateway"}),
            PlaybookStep("Find HTTPRoute objects", "find_k8s_objects", {"kind": "HTTPRoute"}),
            PlaybookStep("Read route YAML", "read_file_slice", {}),
            PlaybookStep("Review for Gateway issues", "review_yaml", {}),
            PlaybookStep("Check live routes", "kubectl_get_httproute", {}, requires_cluster=True),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "backendRef points to non-existent Service",
            "parentRef does not match any Gateway",
            "ReferenceGrant missing for cross-namespace ref",
            "Hostname conflict across routes",
        ],
        stop_conditions=["HTTPRoute accepted by Gateway", "Backend resolved"],
        missing_evidence=["Live HTTPRoute status", "Gateway listeners"],
        key_resources=["Gateway", "HTTPRoute", "Service", "ReferenceGrant"],
    ),
    "probe_failure": Playbook(
        pattern="probe_failure",
        steps=[
            PlaybookStep("Search for probe configurations", "search_repo", {"query": "livenessProbe readinessProbe"}),
            PlaybookStep("Find Deployments", "find_k8s_objects", {"kind": "Deployment"}),
            PlaybookStep("Read deployment YAML", "read_file_slice", {}),
            PlaybookStep("Review probe settings", "review_yaml", {}),
            PlaybookStep("Check pod describe for probe events", "kubectl_describe_pod", {}, requires_cluster=True),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Probe path does not exist in the application",
            "Probe port does not match containerPort",
            "initialDelaySeconds too short",
            "Application slow to start (needs startupProbe)",
        ],
        stop_conditions=["Probes passing", "Pod becomes Ready"],
        missing_evidence=["Pod events showing probe failure details"],
        key_resources=["Deployment", "Pod"],
    ),
    "helm_values_mismatch": Playbook(
        pattern="helm_values_mismatch",
        steps=[
            PlaybookStep("Search for Helm charts", "search_repo", {"query": "Chart.yaml values.yaml"}),
            PlaybookStep("Search for OpenTofu variables tied to Helm values", "search_repo", {"query": "tofu terraform variable helm"}),
            PlaybookStep("Find values files", "find_related_files", {"path": "values.yaml"}),
            PlaybookStep("Read values file", "read_file_slice", {}),
            PlaybookStep("Run OpenTofu format check", "opentofu_fmt_check", {}, requires_cluster=True),
            PlaybookStep("Validate OpenTofu inputs", "opentofu_validate", {}, requires_cluster=True),
            PlaybookStep("Render Helm chart", "render_helm", {"summary_only": True}),
            PlaybookStep("Summarize rendered output", "summarize_files", {}),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Value overridden in environment-specific file",
            "OpenTofu variable value differs from expected Helm input",
            "Template references key that doesn't exist in values",
            "Chart dependency version changed",
            "Subchart values not under correct key",
        ],
        stop_conditions=["Helm render succeeds", "Values resolve correctly"],
        missing_evidence=["All values override files", "Rendered manifest diff"],
        key_resources=["Chart.yaml", "values.yaml"],
    ),
    "namespace_mismatch": Playbook(
        pattern="namespace_mismatch",
        steps=[
            PlaybookStep("Search for namespace references", "search_repo", {"query": "namespace metadata"}),
            PlaybookStep("Find K8s objects", "find_k8s_objects", {}),
            PlaybookStep("Read manifests", "read_file_slice", {}),
            PlaybookStep("Review cross-namespace references", "review_yaml", {}),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Resource deployed to wrong namespace",
            "Cross-namespace reference without ReferenceGrant",
            "Hardcoded namespace vs Helm release namespace",
        ],
        stop_conditions=["All resources in correct namespace"],
        missing_evidence=["Namespace of dependent resources"],
        key_resources=["Namespace", "ReferenceGrant"],
    ),
    "port_mismatch": Playbook(
        pattern="port_mismatch",
        steps=[
            PlaybookStep("Search for port definitions", "search_repo", {"query": "containerPort targetPort port"}),
            PlaybookStep("Find Services", "find_k8s_objects", {"kind": "Service"}),
            PlaybookStep("Find Deployments", "find_k8s_objects", {"kind": "Deployment"}),
            PlaybookStep("Read manifests", "read_file_slice", {}),
            PlaybookStep("Review port alignment", "review_yaml", {}),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "Service targetPort != container port",
            "Named port reference doesn't match",
            "containerPort not declared in pod spec",
        ],
        stop_conditions=["Port chain is consistent (Service → Pod → Container)"],
        missing_evidence=["Container port declaration", "Service spec"],
        key_resources=["Service", "Deployment"],
    ),
    "rbac_denial": Playbook(
        pattern="rbac_denial",
        steps=[
            PlaybookStep("Search for RBAC manifests", "search_repo", {"query": "ClusterRoleBinding RoleBinding ServiceAccount"}),
            PlaybookStep("Find RBAC objects", "find_k8s_objects", {"kind": "ClusterRoleBinding"}),
            PlaybookStep("Read RBAC YAML", "read_file_slice", {}),
            PlaybookStep("Review RBAC rules", "review_yaml", {}),
            PlaybookStep("Prepare Copilot brief", "prepare_copilot_brief", {}),
        ],
        common_root_causes=[
            "ServiceAccount not bound to required Role",
            "RoleBinding in wrong namespace",
            "ClusterRole missing verb or resource",
        ],
        stop_conditions=["ServiceAccount has required permissions"],
        missing_evidence=["Role and RoleBinding for the ServiceAccount"],
        key_resources=["ServiceAccount", "Role", "ClusterRole", "RoleBinding", "ClusterRoleBinding"],
    ),
}


def get_playbook(pattern: str) -> Playbook | None:
    return PLAYBOOKS.get(pattern)


def get_repo_steps(pattern: str) -> list[PlaybookStep]:
    """Return only steps that do NOT require cluster access."""
    pb = get_playbook(pattern)
    if pb is None:
        return []
    return [s for s in pb.steps if not s.requires_cluster]


def get_cluster_steps(pattern: str) -> list[PlaybookStep]:
    """Return only steps that require cluster access (stubs for now)."""
    pb = get_playbook(pattern)
    if pb is None:
        return []
    return [s for s in pb.steps if s.requires_cluster]


def playbook_to_dict(pattern: str) -> dict:
    """Serialize a playbook to MCP-friendly dict."""
    pb = get_playbook(pattern)
    if pb is None:
        return {"result": f"No playbook for pattern: {pattern}", "files": [], "data": {}}

    steps_data = []
    for i, step in enumerate(pb.steps, 1):
        steps_data.append({
            "step": i,
            "description": step.description,
            "tool": step.tool,
            "requires_cluster": step.requires_cluster,
        })

    return {
        "result": f"Playbook for {pb.pattern}: {len(pb.steps)} steps, {len(get_repo_steps(pattern))} repo-only.",
        "files": [],
        "data": {
            "pattern": pb.pattern,
            "steps": steps_data,
            "common_root_causes": pb.common_root_causes,
            "stop_conditions": pb.stop_conditions,
            "missing_evidence": pb.missing_evidence,
            "key_resources": pb.key_resources,
            "cluster_steps_available": False,  # stubs only
        },
    }
