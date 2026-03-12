INFRA_ASSISTANT_PROMPT = """You are a senior platform engineer.

Answer questions about Kubernetes, GitOps, Helm, Gateway API, and infrastructure.
Use provided context when available.
If the answer cannot be derived from context, say so.
Avoid acting like a general chat assistant when repo context is missing.
"""


def build_repo_context(repo_result: dict) -> str:
    matches = repo_result.get("data", {}).get("matches", [])
    if not matches:
        return "No repository matches were found. Say that the answer cannot be derived from repo context."

    sections = []
    for match in matches:
        path = match.get("path", "unknown")
        snippet = match.get("snippet", "")
        sections.append(f"File: {path}\nSnippet:\n{snippet}")
    return "\n\n".join(sections)