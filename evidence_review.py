"""MVP professional review helpers for issue evidence."""

from __future__ import annotations

from typing import Any


def review_issue_evidence(issues: list[dict[str, Any]], issue_id: int, reviewer: str, decision: str, explanation: str) -> tuple[str, dict[str, Any] | None]:
    if decision not in {"Verified", "Needs evidence", "Rejected"} or not explanation.strip() or len(explanation) > 1000:
        return "invalid", None
    issue = next((item for item in issues if item["id"] == issue_id), None)
    if issue is None:
        return "missing", None
    issue["evidence_review"] = {"decision": decision, "reviewer": reviewer, "explanation": explanation.strip()}
    return "updated", issue
