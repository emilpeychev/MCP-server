"""Cluster/runtime tools.

kubectl tools execute CLI commands directly and do not perform any login/auth flow.
ArgoCD/OpenTofu/Terraform tools remain stubs.
"""

from __future__ import annotations

import json
import shutil
import subprocess

_NOT_CONFIGURED = (
    "Runtime CLI access not configured. Mount a kubeconfig and install kubectl/argocd/opentofu CLI to enable."
)
_KUBECTL_BIN = "kubectl"
_CMD_TIMEOUT_SECONDS = 45
_MAX_OUTPUT_CHARS = 12000


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


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "\n... [truncated]"


def _summary_item(item: dict) -> dict:
    metadata = item.get("metadata") or {}
    status = item.get("status") or {}
    summary = {
        "kind": item.get("kind", ""),
        "name": metadata.get("name", ""),
        "namespace": metadata.get("namespace", ""),
    }
    phase = status.get("phase")
    if phase:
        summary["phase"] = phase
    load_balancer = status.get("loadBalancer")
    if isinstance(load_balancer, dict) and load_balancer.get("ingress"):
        summary["load_balancer"] = load_balancer.get("ingress")
    return summary


def _command_response(tool_name: str, command: list[str], expect_json: bool = False) -> dict:
    resolved_bin = shutil.which(command[0])
    if resolved_bin is None:
        return {
            "result": f"{command[0]} CLI is not available.",
            "files": [],
            "data": {
                "tool": tool_name,
                "status": "error",
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "hint": f"Install {command[0]} and ensure kube context/auth is already configured.",
            },
        }

    command[0] = resolved_bin
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=_CMD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "result": "Command timed out.",
            "files": [],
            "data": {
                "tool": tool_name,
                "status": "timeout",
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
            },
        }

    stdout = _truncate(completed.stdout)
    stderr = _truncate(completed.stderr)

    if completed.returncode != 0:
        return {
            "result": "Command failed.",
            "files": [],
            "data": {
                "tool": tool_name,
                "status": "error",
                "command": command,
                "exit_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
        }

    data = {
        "tool": tool_name,
        "status": "ok",
        "command": command,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }

    if expect_json:
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            payload = {}
        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, list):
            data["item_count"] = len(items)
            data["items"] = [_summary_item(item) for item in items if isinstance(item, dict)]
        elif isinstance(payload, dict):
            data["item_count"] = 1
            data["items"] = [_summary_item(payload)]
        else:
            data["item_count"] = 0
            data["items"] = []

    return {
        "result": "Command completed.",
        "files": [],
        "data": data,
    }


def _append_namespace(command: list[str], namespace: str | None) -> None:
    if namespace:
        command.extend(["-n", namespace])


def _kubectl_get(
    tool_name: str,
    resource: str,
    name: str | None = None,
    namespace: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> dict:
    command = [_KUBECTL_BIN, "get", resource]
    if name:
        command.append(name)
    _append_namespace(command, namespace)
    if label_selector:
        command.extend(["-l", label_selector])
    if field_selector:
        command.extend(["--field-selector", field_selector])
    command.extend(["-o", "json"])
    return _command_response(tool_name, command, expect_json=True)


# --- kubectl command tools ---

def kubectl_get_pods(namespace: str | None = None, label_selector: str | None = None) -> dict:
    return _kubectl_get(
        "kubectl_get_pods",
        "pods",
        namespace=namespace,
        label_selector=label_selector,
    )


def kubectl_describe_pod(name: str, namespace: str | None = None) -> dict:
    command = [_KUBECTL_BIN, "describe", "pod", name]
    _append_namespace(command, namespace)
    return _command_response("kubectl_describe_pod", command)


def kubectl_get_events(namespace: str | None = None, field_selector: str | None = None) -> dict:
    return _kubectl_get(
        "kubectl_get_events",
        "events",
        namespace=namespace,
        field_selector=field_selector,
    )


def kubectl_logs(name: str, namespace: str | None = None, container: str | None = None) -> dict:
    command = [_KUBECTL_BIN, "logs", name]
    _append_namespace(command, namespace)
    if container:
        command.extend(["-c", container])
    return _command_response("kubectl_logs", command)


def kubectl_logs_previous(name: str, namespace: str | None = None, container: str | None = None) -> dict:
    command = [_KUBECTL_BIN, "logs", name, "--previous"]
    _append_namespace(command, namespace)
    if container:
        command.extend(["-c", container])
    return _command_response("kubectl_logs_previous", command)


def kubectl_get_service(name: str | None = None, namespace: str | None = None) -> dict:
    return _kubectl_get("kubectl_get_service", "service", name=name, namespace=namespace)


def kubectl_get_endpoints(name: str | None = None, namespace: str | None = None) -> dict:
    return _kubectl_get("kubectl_get_endpoints", "endpoints", name=name, namespace=namespace)


def kubectl_get_ingress(name: str | None = None, namespace: str | None = None) -> dict:
    return _kubectl_get("kubectl_get_ingress", "ingress", name=name, namespace=namespace)


def kubectl_get_gateway(name: str | None = None, namespace: str | None = None) -> dict:
    return _kubectl_get("kubectl_get_gateway", "gateway", name=name, namespace=namespace)


def kubectl_get_httproute(name: str | None = None, namespace: str | None = None) -> dict:
    return _kubectl_get("kubectl_get_httproute", "httproute", name=name, namespace=namespace)


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
