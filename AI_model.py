"""Duplicate detection for civic issue reports.

The matcher uses multilingual sentence embeddings when sentence-transformers is
installed. It falls back to a small token-based similarity function so the app
still works without downloading a machine-learning model.
"""

from __future__ import annotations

import math
import re
from io import BytesIO
from dataclasses import dataclass
from typing import Any, Iterable

try:
    from .community import distance_km
except ImportError:
    from community import distance_km


@dataclass(frozen=True)
class DuplicateMatch:
    issue: dict[str, Any]
    text_score: float
    distance_km: float
    score: float
    decision: str


class IssueDeduplicator:
    """Find likely duplicate reports using text, category, and location."""

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        auto_merge_threshold: float = 0.88,
        review_threshold: float = 0.70,
    ) -> None:
        self.model_name = model_name
        self.auto_merge_threshold = auto_merge_threshold
        self.review_threshold = review_threshold
        self._model: Any = None
        self._model_loaded = False

    def find_match(
        self,
        report: dict[str, Any],
        existing_issues: Iterable[dict[str, Any]],
    ) -> DuplicateMatch | None:
        candidates = [
            issue
            for issue in existing_issues
            if self._same_category(report, issue)
            and self._distance_for(report, issue) <= self._radius_km(report)
        ]
        if not candidates:
            return None

        report_text = self._text(report)
        candidate_texts = [self._text(issue) for issue in candidates]
        text_scores = self._similarities(report_text, candidate_texts)
        matches = [
            self._build_match(report, issue, text_score)
            for issue, text_score in zip(candidates, text_scores)
        ]
        return max(matches, key=lambda match: match.score)

    def _build_match(
        self,
        report: dict[str, Any],
        issue: dict[str, Any],
        text_score: float,
    ) -> DuplicateMatch:
        distance = self._distance_for(report, issue)
        radius = self._radius_km(report)
        location_score = max(0.0, 1.0 - (distance / radius))
        score = 0.70 * text_score + 0.30 * location_score
        if score >= self.auto_merge_threshold:
            decision = "duplicate"
        elif score >= self.review_threshold:
            decision = "possible_duplicate"
        else:
            decision = "new"
        return DuplicateMatch(issue, text_score, distance, score, decision)

    def _similarities(self, text: str, candidates: list[str]) -> list[float]:
        self._load_model()
        if self._model is not None:
            vectors = self._model.encode([text, *candidates], normalize_embeddings=True)
            query = vectors[0]
            return [max(0.0, float(query @ vector)) for vector in vectors[1:]]
        return [_token_similarity(text, candidate) for candidate in candidates]

    def _load_model(self) -> None:
        if self._model_loaded:
            return
        self._model_loaded = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except (ImportError, OSError, RuntimeError):
            self._model = None

    @staticmethod
    def _same_category(first: dict[str, Any], second: dict[str, Any]) -> bool:
        return str(first.get("category", "")).strip().casefold() == str(second.get("category", "")).strip().casefold()

    @staticmethod
    def _distance_for(first: dict[str, Any], second: dict[str, Any]) -> float:
        return distance_km(float(first["lat"]), float(first["lng"]), float(second["lat"]), float(second["lng"]))

    @staticmethod
    def _radius_km(report: dict[str, Any]) -> float:
        category = str(report.get("category", "")).casefold()
        if category == "water":
            return 2.0
        if category == "waste":
            return 0.15
        if category == "streetlights":
            return 0.10
        if category == "roads":
            return 0.075
        return 0.15

    @staticmethod
    def _text(issue: dict[str, Any]) -> str:
        return f"{issue.get('title', '')}. {issue.get('description', '')}. {issue.get('area', '')}".strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def _token_similarity(first: str, second: str) -> float:
    first_tokens = _tokens(first)
    second_tokens = _tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / math.sqrt(len(first_tokens) * len(second_tokens))


DETECTOR = IssueDeduplicator()


def inspect_image_proof(image_bytes: bytes, expected_lat: float, expected_lng: float) -> dict[str, Any]:
    """Inspect an image's EXIF GPS metadata and compare it with the map pin."""
    try:
        # pyrefly: ignore [missing-import]
        from PIL import Image
    except ImportError:
        return {"status": "unverified", "message": "Install Pillow to verify image GPS metadata."}

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            exif = image.getexif()
            gps = exif.get_ifd(34853)
            latitude = _exif_coordinate(gps, 2, 1)
            longitude = _exif_coordinate(gps, 4, 3)
            if latitude is None or longitude is None:
                return {"status": "unverified", "message": "Image has no GPS metadata."}
            distance = distance_km(expected_lat, expected_lng, latitude, longitude)
            if distance > 0.1:
                return {"status": "mismatch", "message": f"Image GPS is {distance * 1000:.0f} m from the selected pin."}
            return {"status": "verified", "message": f"GPS verified within {distance * 1000:.0f} m.", "lat": latitude, "lng": longitude}
    except (OSError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return {"status": "unverified", "message": "Image GPS metadata could not be read."}


def _exif_coordinate(gps: Any, value_key: int, reference_key: int) -> float | None:
    value = gps.get(value_key)
    reference = gps.get(reference_key)
    if not value or not reference:
        return None
    degrees, minutes, seconds = (float(part) for part in value)
    coordinate = degrees + minutes / 60 + seconds / 3600
    return -coordinate if str(reference).upper() in {"S", "W"} else coordinate


def find_duplicate(report: dict[str, Any], existing_issues: Iterable[dict[str, Any]]) -> DuplicateMatch | None:
    """Return the strongest match, or None when no nearby candidate exists."""
    return DETECTOR.find_match(report, existing_issues)


def sanitize_and_reencode_image(image_bytes: bytes, default_type: str = "image/jpeg") -> tuple[bytes, str]:
    """Validate, strip EXIF privacy metadata, and re-encode uploaded image data."""
    if not image_bytes:
        return b"", default_type

    try:
        # pyrefly: ignore [missing-import]
        from PIL import Image, ImageOps
    except ImportError:
        return image_bytes, default_type

    try:
        with Image.open(BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            target_format = img.format if img.format in {"JPEG", "PNG", "WEBP"} else "JPEG"
            content_type = f"image/{target_format.lower()}"

            output = BytesIO()
            if target_format == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img.save(output, format=target_format, optimize=True)
            return output.getvalue(), content_type
    except Exception:
        return image_bytes, default_type
