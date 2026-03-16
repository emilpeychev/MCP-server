"""Cluster/runtime tool stubs — interfaces for kubectl, ArgoCD, and OpenTofu CLI tools.

These return structured "not configured" responses until cluster access is wired up.
The playbooks reference these tool names; when cluster access is enabled,
replace the stub implementations with real subprocess calls.
"""

from __future__ import annotations

_NOT_CONFIGURED = (
    "Runtime CLI access not configured. Mount a kubeconfig and install kubectl/argocd/opentofu CLI to enable."
)


def _stub_response(tool_name: str, **kwargs: str) -> dict:
    return {
        "result": _NOT_CONFIGURED,
        "files": [],
        "data": {
            "tool": tool_name,
            "status": "stub",
            "params": kwargs,
            "hint": "Set KUBECONFIG for cluster checks and install kubectl/argocd/opentofu in the container.",
        },
    }


# --- kubectl stubs ---

def kubectl_get_pods(namespace: str | None = None, label_selector: str | None = None) -> dict:
    return _stub_response("kubectl_get_pods", namespace=namespace or "", label_selector=label_selector or "")


def kubectl_describe_pod(name: str, namespace: str | None = None) -> dict:
    return _stub_response("kubectl_describe_pod", name=name, namespace=namespace or "")


def kubectl_get_events(namespace: str | None = None, field_selector: str | None = None) -> dict:
    return _stub_response("kubectl_get_events", namespace=namespace or "", field_selector=field_selector or "")


def kubectl_logs(name: str, namespace: str | None = None, container: str | None = None) -> dict:
    return _stub_response("kubectl_logs", name=name, namespace=namespace or "", container=container or "")


def kubectl_logs_previous(name: str, namespace: str | None = None, container: str | None = None) -> dict:
    return _stub_response("kubectl_logs_previous", name=name, namespace=namespace or "", container=container or "")


def kubectl_get_service(name: str | None = None, namespace: str | None = None) -> dict:
    return _stub_response("kubectl_get_service", name=name or "", namespace=namespace or "")


def kubectl_get_endpoints(name: str | None = None, namespace: str | None = None) -> dict:
    return _stub_response("kubectl_get_endpoints", name=name or "", namespace=namespace or "")


def kubectl_get_ingress(name: str | None = None, namespace: str | None = None) -> dict:
    return _stub_response("kubectl_get_ingress", name=name or "", namespace=namespace or "")


def kubectl_get_gateway(name: str | None = None, namespace: str | None = None) -> dict:
    return _stub_response("kubectl_get_gateway", name=name or "", namespace=namespace or "")


def kubectl_get_httproute(name: str | None = None, namespace: str | None = None) -> dict:
    return _stub_response("kubectl_get_httproute", name=name or "", namespace=namespace or "")


# --- ArgoCD stubs ---

def argocd_get_app(app_name: str) -> dict:
    return _stub_response("argocd_get_app", app_name=app_name)


def argocd_get_app_events(app_name: str) -> dict:
    return _stub_response("argocd_get_app_events", app_name=app_name)


def argocd_get_app_resources(app_name: str) -> dict:
    return _stub_response("argocd_get_app_resources", app_name=app_name)


# --- OpenTofu stubs ---

def opentofu_version() -> dict:
    return _stub_response("opentofu_version")


def opentofu_fmt_check(path: str | None = None) -> dict:
    return _stub_response("opentofu_fmt_check", path=path or "")


def opentofu_validate(path: str | None = None, var_file: str | None = None) -> dict:
    return _stub_response("opentofu_validate", path=path or "", var_file=var_file or "")


def opentofu_plan(path: str | None = None, var_file: str | None = None, target: str | None = None) -> dict:
    return _stub_response(
        "opentofu_plan",
        path=path or "",
        var_file=var_file or "",
        target=target or "",
    )


def opentofu_show_plan(path: str | None = None, plan_file: str | None = None) -> dict:
    return _stub_response("opentofu_show_plan", path=path or "", plan_file=plan_file or "")


# --- Terraform stubs ---

def terraform_version() -> dict:
    return _stub_response("terraform_version")


def terraform_fmt_check(path: str | None = None) -> dict:
    return _stub_response("terraform_fmt_check", path=path or "")


def terraform_validate(path: str | None = None, var_file: str | None = None) -> dict:
    return _stub_response("terraform_validate", path=path or "", var_file=var_file or "")


def terraform_plan(path: str | None = None, var_file: str | None = None, target: str | None = None) -> dict:
    return _stub_response(
        "terraform_plan",
        path=path or "",
        var_file=var_file or "",
        target=target or "",
    )


def terraform_show_plan(path: str | None = None, plan_file: str | None = None) -> dict:
    return _stub_response("terraform_show_plan", path=path or "", plan_file=plan_file or "")
