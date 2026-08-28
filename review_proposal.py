"""Validation and update helpers for professional proposal reviews."""

from __future__ import annotations

from typing import Any

def review_issue_evidence(proposals: list[dict[str, Any]], proposal_id: int, reviewer: str, decision: str, explanation: str) -> tuple[str, dict[str, Any] | None]:
    if decision not in {"Under review", "Approved", "Non-feasible", "Needs revision"} or not explanation.strip() or len(explanation) > 2000:
        return "invalid", None
    proposal = next((item for item in proposals if item["id"] == proposal_id), None)
    if proposal is None:
        return "missing", None
    proposal["status"] = decision
    proposal["review"] = {"decision": decision, "reviewer": reviewer, "explanation": explanation.strip()}
    return "updated", proposal
