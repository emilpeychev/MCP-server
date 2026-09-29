---
name: gateway-audit
description: "Use to audit Kubernetes north-south routing: compare declared Gateway API / Ingress config in the repo against the live cluster and trace whether routes actually resolve to healthy backends. Trigger when asked to 'audit the gateway/ingress/routes', 'why is this host/route 404/503', 'check HTTPRoute wiring', or 'is traffic reaching the service'. Runs through the local-infra MCP; read-only."
---

# /gateway-audit

Follow a request path from Gateway/Ingress → HTTPRoute → Service → Endpoints/Pods, comparing what the repo declares against what the cluster actually serves, and flag every break in the chain.

## Usage

```
/gateway-audit                       # audit all gateways/routes in scope
/gateway-audit <host-or-route>       # scope to a hostname or route name
/gateway-audit ns:<namespace>        # scope to a namespace
/gateway-audit --declared-only       # repo/inspect only, no cluster access
/gateway-audit --help                # print this Usage block and stop
```

If no argument is given, audit all discovered gateways/routes; if the set is large, list them and ask the user to narrow.

## Auth model

- `kubectl_*` tools shell out and inherit the terminal's ambient AWS/EKS auth — no kubeconfig to mount, no login step here.
- On every cluster call read `data.status`/`data.category`: `unavailable` = binary missing; `unverified`+`auth` = cluster/context error (surface real `stderr`, do not guess). All cluster access is **read-only**.

## Steps

Cite the tool output backing each finding.

### 1. Declared routing (repo)
- `inspect_gateway` — analyze declared Gateway API / Ingress routing in the repo.
- `find_k8s_objects` — enumerate Gateway, HTTPRoute, Ingress, Service objects.
- `search_repo` / `read_file_slice` — pull hostnames, path rules, `backendRefs`, ports, and TLS config.

### 2. Live routing (cluster), scoped to target
- `kubectl_get_gateway` — Gateway programmed status / listeners / addresses.
- `kubectl_get_httproute` — route acceptance and resolved `backendRefs`.
- `kubectl_get_ingress` — Ingress rules and load balancer address.
- `kubectl_get_service` — the target Service exists and its type/ports match the route.
- `kubectl_get_endpoints` — the Service actually has **ready endpoints** (empty endpoints = 503 even when routing is correct).

### 3. Trace the chain
For each host/route, walk: listener → route match → `backendRef` service → service port → endpoints → ready pods. Stop at the first break.

### 4. Classify findings
| Class | Meaning |
|---|---|
| **Declared-not-live** | Repo declares a Gateway/route/host absent from the cluster. |
| **Live-not-declared** | Cluster serves a route/host with no repo source (orphan). |
| **Backend break** | Route resolves but Service missing, wrong port, or **no ready endpoints**. |
| **Listener/TLS** | Gateway listener not programmed, or TLS/cert mismatch. |
| **Host/path mismatch** | Hostname or path rules differ repo ↔ live. |

## Report

- Table: `Host/Route | Declared | Live | First break | Class | Severity | Evidence`.
- Severity **HIGH** for any break that would drop production traffic (missing route, no endpoints, unprogrammed listener).
- If any leg was `unavailable`/`unverified`, state which conclusions are incomplete — never present a partial audit as complete.

## Guardrails

- MCP-first; if a tool fails/returns empty, say so, then fall back.
- Evidence before conclusions — no routing claim without the backing tool output.
- Read-only cluster access; never mutate gateways, routes, or services.
- Never fabricate live routing state to fill a gap left by a failed call.
