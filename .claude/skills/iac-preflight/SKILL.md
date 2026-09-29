---
name: iac-preflight
description: "Use to validate infrastructure-as-code and manifests BEFORE a merge or apply: Terraform/OpenTofu validate + fmt + plan, Helm render, and Kubernetes YAML review, aggregated into one pass/fail gate. Trigger when asked to 'preflight', 'validate the IaC/manifests', 'is this safe to merge/apply', 'check terraform/helm before deploy', or as a pre-merge/pre-apply check. Runs through the local-infra MCP; never applies changes."
---

# /iac-preflight

A single read-only gate that runs every static check this repo supports for Terraform/OpenTofu, Helm, and Kubernetes YAML, then reports one aggregated PASS/FAIL with per-check evidence.

## Usage

```
/iac-preflight                    # check all IaC/manifests in the repo
/iac-preflight <path>             # scope to a dir/chart/module
/iac-preflight --plan             # also run terraform/opentofu plan (read-only)
/iac-preflight --no-plan          # skip plan (validate + fmt + render + yaml only) [default]
/iac-preflight --help             # print this Usage block and stop
```

Default is validate + fmt + Helm render + YAML review (fast, no cluster/state access). `--plan` adds a plan step, which may read remote state.

## Scope discovery

- `search_repo` / `find_related_files` to locate Terraform/OpenTofu modules (`*.tf`), Helm charts (`Chart.yaml`), and K8s manifests (`*.yaml`). Prefer OpenTofu tools if `.tofu`/OpenTofu is in use; otherwise Terraform.

## Steps

Run the checks that apply to what was discovered. Record each result with its tool output.

### 1. Terraform / OpenTofu
- `terraform_fmt_check` / `opentofu_fmt_check` — formatting drift.
- `terraform_validate` / `opentofu_validate` — config validity (must pass before trusting anything downstream).
- With `--plan`: `terraform_plan` / `opentofu_plan`, then `terraform_show_plan` / `opentofu_show_plan` to summarize the diff. Flag creates/replaces/**destroys** explicitly.
- `terraform_version` / `opentofu_version` if a version mismatch is suspected.

### 2. Helm
- `render_helm` for each chart — compare the **rendered** output; a template that renders is not the same as correct values.
- Feed rendered manifests into the YAML review below.

### 3. Kubernetes YAML
- `review_yaml` on raw and rendered manifests — structural issues, missing required fields, obvious misconfig.

## Report

- One aggregated verdict: **PASS** (all applicable checks clean) or **FAIL** (≥1 check failed), plus per-check status: `pass` / `fail` / `skipped` / `unavailable`.
- Table: `Check | Target | Result | Evidence`.
- For `--plan`, call out destructive actions (destroy/replace) as **HIGH** regardless of validate status.
- If a CLI is `unavailable` (binary missing) or a check errored, mark it `skipped`/`unavailable` and state that the gate is therefore not fully green — never report PASS over a skipped check.

## Guardrails

- MCP-first; if a tool fails/returns empty, say so, then fall back.
- **Never apply.** No `apply`, `destroy`, `import`, or state mutation. Plan is read-only and opt-in via `--plan`.
- Evidence before conclusions — no PASS/FAIL without the backing tool output.
