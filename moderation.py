"""MVP moderation queue and actions for civic content."""

from __future__ import annotations

from typing import Any


def moderation_queue(issues: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for issue in issues:
        if issue.get("moderation_status", "Pending") == "Pending":
            items.append({"kind": "issue", "id": issue["id"], "title": issue["title"], "reason": "Issue awaiting moderation"})
    for proposal in proposals:
        if proposal.get("moderation_status", "Pending") == "Pending":
            items.append({"kind": "proposal", "id": proposal["id"], "title": proposal["title"], "reason": "Proposal awaiting moderation"})
    return items


def moderate_item(issues: list[dict[str, Any]], proposals: list[dict[str, Any]], kind: str, item_id: int, decision: str, moderator: str, explanation: str) -> tuple[str, dict[str, Any] | None]:
    if decision not in {"Approved", "Rejected", "Archived"} or not explanation.strip() or len(explanation) > 1000:
        return "invalid", None
    collection = issues if kind == "issue" else proposals if kind == "proposal" else []
    item = next((entry for entry in collection if entry["id"] == item_id), None)
    if item is None:
        return "missing", None
    item["moderation_status"] = decision
    item["moderation"] = {"moderator": moderator, "explanation": explanation.strip()}
    return "updated", item