from __future__ import annotations

VERBOSITY_LIMITS = {"compact": 500, "normal": 1500, "detailed": 5000}


def prepare_copilot_brief(
    question: str,
    findings: list[str] | None = None,
    affected_files: list[str] | None = None,
    likely_cause: str | None = None,
    verbosity: str = "compact",
) -> dict:
    """Build a structured, distilled brief for Copilot. This is the final handoff tool.

    Call this after retrieval and summarization to package everything
    Copilot needs in one compact payload.
    """
    findings = findings or []
    affected_files = affected_files or []
    max_chars = VERBOSITY_LIMITS.get(verbosity, VERBOSITY_LIMITS["compact"])

    sections: list[str] = []
    sections.append(f"## Question\n{question}")

    if affected_files:
        file_list = "\n".join(f"- {f}" for f in affected_files)
        sections.append(f"## Affected Files\n{file_list}")

    if findings:
        finding_list = "\n".join(f"- {f}" for f in findings)
        sections.append(f"## Key Findings\n{finding_list}")

    if likely_cause:
        sections.append(f"## Likely Cause\n{likely_cause}")

    sections.append("## Action Needed\nAnalyze the above findings and suggest the fix.")

    brief = "\n\n".join(sections)
    if len(brief) > max_chars:
        brief = brief[:max_chars] + "\n... [truncated]"

    return {
        "result": brief,
        "files": affected_files,
        "data": {
            "question": question,
            "findings": findings,
            "affected_files": affected_files,
            "likely_cause": likely_cause or "",
            "verbosity": verbosity,
        },
    }
