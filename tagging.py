"""MVP problem-type tagging for civic issue reports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProblemTag:
    problem_type: str
    tags: tuple[str, ...]
    confidence: float


# Ordered from specific phrases to broader categories.
TAG_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("Roadways", ("pothole", "road hole", "road has hole", "road has holes", "holes in road", "road damage", "broken road", "road crack", "street damage", "traffic jam", "roadway"), ("pothole", "road damage", "traffic")),
    ("Electricity", ("power cut", "power outage", "electricity", "electrical", "transformer", "live wire", "voltage", "streetlight", "street light"), ("power", "streetlight", "wiring")),
    ("Water Supply", ("water cut", "no water", "water supply", "water leak", "leaking pipe", "pipeline", "tap water", "drinking water"), ("water", "leak", "supply")),
    ("Garbage Collection", ("garbage", "rubbish", "trash", "waste collection", "uncollected waste", "dumping", "litter", "bins"), ("garbage", "waste", "sanitation")),
    ("Public Transport", ("bus frequency", "bus timing", "bus timings", "buses have", "bus stop", "public transport", "metro", "train delay", "transport"), ("bus", "transit", "frequency")),
    ("Drainage and Flooding", ("flood", "flooding", "drain", "drainage", "waterlogging", "sewage", "stormwater"), ("flooding", "drainage", "sewage")),
    ("Footpaths and Accessibility", ("footpath", "sidewalk", "pavement", "wheelchair", "accessibility", "ramp", "curb", "kerb"), ("footpath", "accessibility", "pedestrian")),
    ("Public Safety", ("unsafe", "crime", "accident", "dangerous", "safety", "harassment", "street crime"), ("safety", "hazard")),
)


def classify_problem(issue: dict[str, Any]) -> ProblemTag:
    """Return a canonical type, tags, and simple confidence score."""
    text = _normalise(f"{issue.get('title', '')} {issue.get('description', '')} {issue.get('category', '')}")
    for problem_type, phrases, tags in TAG_RULES:
        matches = [phrase for phrase in phrases if phrase in text]
        if matches:
            confidence = min(0.99, 0.72 + 0.08 * len(matches))
            return ProblemTag(problem_type, tags, confidence)
    return ProblemTag("Other Civic Issue", ("other",), 0.25)


def tag_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of an issue with MVP classification fields added."""
    tagged = dict(issue)
    result = classify_problem(tagged)
    tagged["problem_type"] = result.problem_type
    tagged["problem_tags"] = list(result.tags)
    tagged["tag_confidence"] = result.confidence
    return tagged


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()
