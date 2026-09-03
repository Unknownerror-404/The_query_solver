"""Ranking helpers for the civic community board."""

from __future__ import annotations

from typing import Any, Iterable


def rank_issues(issues: Iterable[dict[str, Any]], mode: str = "supporters") -> list[dict[str, Any]]:
    """Return issues ordered for a transparent community-board view."""
    if mode == "recent":
        return sorted(issues, key=lambda issue: issue.get("age", ""), reverse=True)
    if mode == "evidence":
        return sorted(issues, key=lambda issue: (issue.get("proof_status") == "verified", issue.get("supporters", 0)), reverse=True)
    return sorted(issues, key=lambda issue: issue.get("supporters", 0), reverse=True)
