"""
AI utilities for civic issue reports.

This module provides:

1. Text-based civic issue classification.
2. Severity estimation.
3. Duplicate detection.
4. Image GPS verification.
5. Fine-tuned CLIP ViT civic issue classification.
6. Video frame sampling and aggregation.

The visual model is a fine-tuned:
    openai/clip-vit-base-patch32

Expected trained model directory:

    models/
        civic_clip/
            config.json
            model.safetensors
            preprocessor_config.json
            labels.json
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile

from io import BytesIO

from dataclasses import dataclass

from pathlib import Path

from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Existing application dependency
# ---------------------------------------------------------------------------

try:
    from .community import distance_km
except ImportError:
    from community import distance_km

# #region agent log
def _agent_log(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    try:
        import time
        payload = {
            "sessionId": "0d8a0a",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
            "runId": "pre-fix",
        }
        with open(Path(__file__).resolve().parent / "debug-0d8a0a.log", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    except Exception:
        pass
# #endregion


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DuplicateMatch:

    issue: dict[str, Any]

    text_score: float

    distance_km: float

    score: float

    decision: str


class IssueDeduplicator:
    """
    Find likely duplicate reports using:

    - text similarity
    - category
    - geographic distance
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        auto_merge_threshold: float = 0.88,
        review_threshold: float = 0.70,
    ) -> None:

        self.model_name = model_name

        self.auto_merge_threshold = (
            auto_merge_threshold
        )

        self.review_threshold = (
            review_threshold
        )

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

            if self._same_category(
                report,
                issue
            )

            and self._distance_for(
                report,
                issue
            )
            <=
            self._radius_km(report)
        ]

        if not candidates:
            return None

        report_text = self._text(
            report
        )

        candidate_texts = [
            self._text(issue)
            for issue in candidates
        ]

        text_scores = self._similarities(
            report_text,
            candidate_texts
        )

        matches = [
            self._build_match(
                report,
                issue,
                text_score
            )

            for issue, text_score

            in zip(
                candidates,
                text_scores
            )
        ]

        return max(
            matches,
            key=lambda match: match.score
        )


    def _build_match(
        self,
        report: dict[str, Any],
        issue: dict[str, Any],
        text_score: float,
    ) -> DuplicateMatch:

        distance = self._distance_for(
            report,
            issue
        )

        radius = self._radius_km(
            report
        )

        location_score = max(
            0.0,
            1.0 - (
                distance / radius
            )
        )

        score = (
            0.70 * text_score
            +
            0.30 * location_score
        )

        if score >= self.auto_merge_threshold:

            decision = "duplicate"

        elif score >= self.review_threshold:

            decision = "possible_duplicate"

        else:

            decision = "new"

        return DuplicateMatch(
            issue,
            text_score,
            distance,
            score,
            decision
        )


    def _similarities(
        self,
        text: str,
        candidates: list[str],
    ) -> list[float]:

        self._load_model()

        if self._model is not None:

            vectors = self._model.encode(
                [
                    text,
                    *candidates
                ],
                normalize_embeddings=True
            )

            query = vectors[0]

            return [
                max(
                    0.0,
                    float(
                        query @ vector
                    )
                )

                for vector in vectors[1:]
            ]

        return [
            _token_similarity(
                text,
                candidate
            )

            for candidate in candidates
        ]


    def _load_model(self) -> None:

        if self._model_loaded:
            return

        self._model_loaded = True
        if os.getenv("CIVIC_MAP_LOAD_TRANSFORMERS", "0") != "1":
            self._model = None
            return

        try:

            from sentence_transformers import (
                SentenceTransformer
            )

            self._model = SentenceTransformer(
                self.model_name
            )

        except (
            ImportError,
            OSError,
            RuntimeError,
            Exception,
        ):

            self._model = None
            self._model = None


    @staticmethod
    def _same_category(
        first: dict[str, Any],
        second: dict[str, Any],
    ) -> bool:

        return (
            str(
                first.get(
                    "category",
                    ""
                )
            )
            .strip()
            .casefold()
            ==
            str(
                second.get(
                    "category",
                    ""
                )
            )
            .strip()
            .casefold()
        )


    @staticmethod
    def _distance_for(
        first: dict[str, Any],
        second: dict[str, Any],
    ) -> float:

        return distance_km(
            float(first["lat"]),
            float(first["lng"]),
            float(second["lat"]),
            float(second["lng"])
        )


    @staticmethod
    def _radius_km(
        report: dict[str, Any]
    ) -> float:

        category = str(
            report.get(
                "category",
                ""
            )
        ).casefold()

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
    def _text(
        issue: dict[str, Any]
    ) -> str:

        return (
            f"{issue.get('title', '')}. "
            f"{issue.get('description', '')}. "
            f"{issue.get('area', '')}"
        ).strip()


# ---------------------------------------------------------------------------
# Fallback token similarity
# ---------------------------------------------------------------------------

def _tokens(
    text: str
) -> set[str]:

    return set(
        re.findall(
            r"[a-z0-9]+",
            text.casefold()
        )
    )


def _token_similarity(
    first: str,
    second: str
) -> float:

    first_tokens = _tokens(first)

    second_tokens = _tokens(second)

    if not first_tokens or not second_tokens:
        return 0.0

    return (
        len(
            first_tokens
            &
            second_tokens
        )
        /
        math.sqrt(
            len(first_tokens)
            *
            len(second_tokens)
        )
    )


# ---------------------------------------------------------------------------
# Existing text classifier
# ---------------------------------------------------------------------------

AI_CATEGORY_KEYWORDS = {

    "Education": {
        "school",
        "college",
        "teacher",
        "student",
        "education",
        "classroom",
    },

    "Healthcare": {
        "hospital",
        "doctor",
        "clinic",
        "medicine",
        "health",
        "ambulance",
    },

    "Agriculture": {
        "farmer",
        "crop",
        "irrigation",
        "agriculture",
        "seed",
        "farm",
    },

    "Water Resources": {
        "water",
        "pipeline",
        "supply",
        "drinking",
        "flood",
        "drainage",
    },

    "Sanitation": {
        "garbage",
        "waste",
        "sewer",
        "toilet",
        "sanitation",
        "uncollected",
    },

    "Environment": {
        "pollution",
        "tree",
        "forest",
        "smoke",
        "environment",
        "river",
    },

    "Energy": {
        "electricity",
        "power",
        "transformer",
        "energy",
        "voltage",
        "cable",
        "wire",
    },

    "Accessibility": {
        "wheelchair",
        "accessible",
        "disability",
        "ramp",
        "blind",
    },

    "Urban Infrastructure": {
        "road",
        "pothole",
        "streetlight",
        "traffic",
        "bridge",
        "footpath",
    },

    "Public Administration": {
        "office",
        "certificate",
        "pension",
        "ration",
        "complaint",
        "government",
    },

    "Rural Livelihoods": {
        "livelihood",
        "employment",
        "market",
        "self-help",
        "income",
        "work",
    },
}


def classify_issue(
    title: str,
    description: str,
    category: str = "",
) -> dict[str, Any]:
    """
    Existing text classifier and severity estimator.
    """

    text = _tokens(
        f"{title} "
        f"{description} "
        f"{category}"
    )

    scores = {
        name: len(
            text & keywords
        )

        for name, keywords

        in AI_CATEGORY_KEYWORDS.items()
    }

    predicted_category, match_count = max(
        scores.items(),
        key=lambda item: item[1]
    )

    if match_count == 0:

        predicted_category = (
            category.strip()
            or
            "Urban Infrastructure"
        )

        explanation = (
            "No strong keyword signal; "
            "retained the submitted category."
        )

    else:

        explanation = (
            f"Matched {match_count} civic-domain "
            f"signal(s) for {predicted_category}."
        )

    urgent_terms = {
        "danger",
        "accident",
        "collapse",
        "fire",
        "flood",
        "unsafe",
        "emergency",
        "death",
    }

    impact_terms = {
        "blocked",
        "days",
        "week",
        "entire",
        "children",
        "elderly",
        "hospital",
        "school",
    }

    severity_score = min(
        100,

        30
        +
        len(
            text & impact_terms
        )
        * 10

        +

        len(
            text & urgent_terms
        )
        * 20
    )

    if severity_score >= 80:

        severity = "Critical"

    elif severity_score >= 60:

        severity = "High"

    elif severity_score >= 40:

        severity = "Medium"

    else:

        severity = "Low"

    return {

        "predicted_category":
            predicted_category,

        "category_confidence":
            round(
                min(
                    0.99,
                    0.45
                    +
                    match_count * 0.12
                ),
                2
            )
            if match_count
            else 0.25,

        "priority_score":
            severity_score,

        "priority_label":
            severity,

        "matching_explanation":
            explanation,
    }


# ---------------------------------------------------------------------------
# Global duplicate detector
# ---------------------------------------------------------------------------

DETECTOR = IssueDeduplicator()


def find_duplicate(
    report: dict[str, Any],
    existing_issues: Iterable[dict[str, Any]],
) -> DuplicateMatch | None:

    return DETECTOR.find_match(
        report,
        existing_issues
    )


# ---------------------------------------------------------------------------
# Image GPS verification
# ---------------------------------------------------------------------------

def inspect_image_proof(
    image_bytes: bytes,
    expected_lat: float,
    expected_lng: float,
) -> dict[str, Any]:
    """
    Inspect an image's EXIF GPS metadata
    and compare it with the map pin.
    """

    try:

        from PIL import Image

    except ImportError:

        return {
            "status": "unverified",
            "message":
                "Install Pillow to verify "
                "image GPS metadata.",
        }

    try:

        with Image.open(
            BytesIO(image_bytes)
        ) as image:

            exif = image.getexif()

            gps = exif.get_ifd(
                34853
            )

            latitude = _exif_coordinate(
                gps,
                2,
                1
            )

            longitude = _exif_coordinate(
                gps,
                4,
                3
            )

            if (
                latitude is None
                or
                longitude is None
            ):

                return {
                    "status": "unverified",
                    "message":
                        "Image has no GPS metadata.",
                }

            distance = distance_km(
                expected_lat,
                expected_lng,
                latitude,
                longitude
            )

            if distance > 0.1:

                return {
                    "status": "mismatch",
                    "message":
                        f"Image GPS is "
                        f"{distance * 1000:.0f} m "
                        f"from the selected pin.",
                }

            return {
                "status": "verified",
                "message":
                    f"GPS verified within "
                    f"{distance * 1000:.0f} m.",
                "lat": latitude,
                "lng": longitude,
            }

    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        ZeroDivisionError,
    ):

        return {
            "status": "unverified",
            "message":
                "Image GPS metadata "
                "could not be read.",
        }


def _exif_coordinate(
    gps: Any,
    value_key: int,
    reference_key: int,
) -> float | None:

    value = gps.get(
        value_key
    )

    reference = gps.get(
        reference_key
    )

    if not value or not reference:
        return None

    degrees, minutes, seconds = (
        float(part)
        for part in value
    )

    coordinate = (
        degrees
        +
        minutes / 60
        +
        seconds / 3600
    )

    if str(reference).upper() in {
        "S",
        "W"
    }:

        coordinate = -coordinate

    return coordinate


# ---------------------------------------------------------------------------
# Image sanitization
# ---------------------------------------------------------------------------

def sanitize_and_reencode_image(
    image_bytes: bytes,
    default_type: str = "image/jpeg",
) -> tuple[bytes, str]:

    if not image_bytes:

        return (
            b"",
            default_type
        )

    try:

        from PIL import (
            Image,
            ImageOps
        )

    except ImportError:

        return (
            image_bytes,
            default_type
        )

    try:

        with Image.open(
            BytesIO(image_bytes)
        ) as img:

            img = ImageOps.exif_transpose(
                img
            )

            target_format = (
                img.format
                if img.format
                in {
                    "JPEG",
                    "PNG",
                    "WEBP"
                }
                else
                "JPEG"
            )

            content_type = (
                f"image/"
                f"{target_format.lower()}"
            )

            output = BytesIO()

            if (
                target_format == "JPEG"
                and
                img.mode in (
                    "RGBA",
                    "P"
                )
            ):

                img = img.convert(
                    "RGB"
                )

            img.save(
                output,
                format=target_format,
                optimize=True
            )

            return (
                output.getvalue(),
                content_type
            )

    except Exception:

        return (
            image_bytes,
            default_type
        )


# ---------------------------------------------------------------------------
# Fine-tuned CLIP model
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# IMPORTANT:
#
# Place the trained model at:
#
#     <project>/models/civic_clip/
#
# or set:
#
#     CIVIC_CLIP_MODEL_DIR
#
# environment variable.
# ---------------------------------------------------------------------------

BASE_DIR = Path(
    __file__
).resolve().parent

DEFAULT_CLIP_MODEL_DIR = (
    BASE_DIR
    /
    "models"
    /
    "civic_clip"
)

CLIP_MODEL_DIR = Path(
    os.environ.get(
        "CIVIC_CLIP_MODEL_DIR",
        str(DEFAULT_CLIP_MODEL_DIR)
    )
)
if not CLIP_MODEL_DIR.exists():
    alt = BASE_DIR / "models" / "civic_clip_pothole_model"
    if alt.exists():
        CLIP_MODEL_DIR = alt

_CLIP_MODEL: Any = None

_CLIP_PROCESSOR: Any = None

_CLIP_MODEL_LOADED = False

_CLIP_LABELS: list[str] = []

_CLIP_FALLBACK: Any = None

_CLIP_FALLBACK_LOADED = False


def _load_finetuned_clip() -> bool:
    """
    Lazily load the fine-tuned CLIP classifier.

    Returns True when the model is available.
    """

    global _CLIP_MODEL

    global _CLIP_PROCESSOR

    global _CLIP_MODEL_LOADED

    global _CLIP_LABELS

    if _CLIP_MODEL_LOADED:

        return (
            _CLIP_MODEL is not None
        )

    _CLIP_MODEL_LOADED = True

    if not CLIP_MODEL_DIR.exists():

        print(
            "[AI_model] Fine-tuned CLIP "
            f"model not found at "
            f"{CLIP_MODEL_DIR}"
        )
        # #region agent log
        _agent_log("A", "AI_model.py:_load_finetuned_clip", "CLIP dir missing", {"clip_dir": str(CLIP_MODEL_DIR), "env_civic": os.environ.get("CIVIC_CLIP_MODEL_DIR"), "env_wrong_key": os.environ.get("./models/civic_clip_pothole_model")})
        # #endregion

        return False

    try:

        import torch

        from transformers import (
            CLIPImageProcessor,
            CLIPForImageClassification,
        )

        _CLIP_PROCESSOR = (
            CLIPImageProcessor.from_pretrained(
                str(CLIP_MODEL_DIR)
            )
        )

        _CLIP_MODEL = (
            CLIPForImageClassification
            .from_pretrained(
                str(CLIP_MODEL_DIR)
            )
        )

        device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        _CLIP_MODEL.to(device)

        _CLIP_MODEL.eval()

        # Read labels from config.
        id2label = (
            getattr(
                _CLIP_MODEL.config,
                "id2label",
                {}
            )
            or {}
        )

        if id2label:

            _CLIP_LABELS = [
                id2label[index]
                if index in id2label
                else id2label[str(index)]
                if str(index) in id2label
                else str(index)

                for index
                in range(
                    _CLIP_MODEL.config.num_labels
                )
            ]

        # Explicit labels.json is preferred.
        labels_file = (
            CLIP_MODEL_DIR
            /
            "labels.json"
        )

        if labels_file.exists():

            try:

                with open(
                    labels_file,
                    "r",
                    encoding="utf-8"
                ) as handle:

                    label_data = json.load(
                        handle
                    )

                label_map = (
                    label_data.get(
                        "id2label",
                        {}
                    )
                )

                _CLIP_LABELS = [
                    label_map.get(
                        str(index),
                        label_map.get(
                            index,
                            _CLIP_LABELS[index]
                            if index
                            <
                            len(_CLIP_LABELS)
                            else str(index)
                        )
                    )

                    for index
                    in range(
                        _CLIP_MODEL.config.num_labels
                    )
                ]

            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
            ):

                pass

        print(
            "[AI_model] Loaded fine-tuned "
            "CLIP civic classifier: "
            f"{CLIP_MODEL_DIR}"
        )

        print(
            "[AI_model] Classes:",
            _CLIP_LABELS
        )

        # #region agent log
        _agent_log("A", "AI_model.py:_load_finetuned_clip", "CLIP loaded", {"clip_dir": str(CLIP_MODEL_DIR), "labels": list(_CLIP_LABELS)[:12], "num_labels": len(_CLIP_LABELS)})
        # #endregion
        return True

    except (
        ImportError,
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
    ) as exc:

        print(
            "[AI_model] Could not load "
            f"fine-tuned CLIP: {exc}"
        )
        # #region agent log
        _agent_log("A", "AI_model.py:_load_finetuned_clip", "CLIP load failed", {"clip_dir": str(CLIP_MODEL_DIR), "error": str(exc)})
        # #endregion

        _CLIP_MODEL = None

        _CLIP_PROCESSOR = None

        return False


def _clip_device():

    import torch

    if _CLIP_MODEL is None:

        return torch.device(
            "cpu"
        )

    return next(
        _CLIP_MODEL.parameters()
    ).device


# ---------------------------------------------------------------------------
# Fine-grained issue -> existing civic domain mapping
# ---------------------------------------------------------------------------

VISUAL_DOMAIN_MAP = {

    "pothole":
        "Urban Infrastructure",

    "damaged_road":
        "Urban Infrastructure",

    "damaged_footpath":
        "Accessibility",

    "broken_streetlight":
        "Energy",

    "loose_cable":
        "Energy",

    "fallen_power_line":
        "Energy",

    "water_leak":
        "Water Resources",

    "flooded_road":
        "Water Resources",

    "blocked_drain":
        "Water Resources",

    "garbage":
        "Sanitation",

    "other":
        "Urban Infrastructure",
}


def _normalise_visual_label(
    label: str
) -> str:

    label = str(
        label
    ).strip()

    return label


def _visual_domain_for(
    label: str
) -> str:

    key = (
        str(label)
        .strip()
        .casefold()
    )

    return VISUAL_DOMAIN_MAP.get(
        key,
        "Urban Infrastructure"
    )


# ---------------------------------------------------------------------------
# Single image inference
# ---------------------------------------------------------------------------

def _predict_clip_fallback(images: list[Any]) -> dict[str, Any]:
    """Zero-shot CLIP ViT when the fine-tuned civic_clip weights are absent."""
    global _CLIP_FALLBACK, _CLIP_FALLBACK_LOADED
    if not images:
        return {}
    if not _CLIP_FALLBACK_LOADED:
        _CLIP_FALLBACK_LOADED = True
        try:
            from sentence_transformers import SentenceTransformer
            _CLIP_FALLBACK = SentenceTransformer("clip-ViT-B-32")
            # #region agent log
            _agent_log("A", "AI_model.py:_predict_clip_fallback", "fallback CLIP loaded", {"model": "clip-ViT-B-32"})
            # #endregion
        except (ImportError, OSError, RuntimeError) as exc:
            _CLIP_FALLBACK = None
            # #region agent log
            _agent_log("A", "AI_model.py:_predict_clip_fallback", "fallback CLIP failed", {"error": str(exc)})
            # #endregion
    if _CLIP_FALLBACK is None:
        return {}
    try:
        labels = list(VISUAL_DOMAIN_MAP.keys())
        prompts = [f"a photo of {label.replace('_', ' ')}" for label in labels]
        image_vectors = _CLIP_FALLBACK.encode(images, normalize_embeddings=True)
        text_vectors = _CLIP_FALLBACK.encode(prompts, normalize_embeddings=True)
        pooled = image_vectors.mean(axis=0)
        scores = [float(pooled @ vector) for vector in text_vectors]
        best_index = max(range(len(scores)), key=lambda index: scores[index])
        predicted_label = labels[best_index]
        confidence = max(0.0, min(0.99, (scores[best_index] + 1) / 2))
        return {
            "issue_type": predicted_label,
            "predicted_category": _visual_domain_for(predicted_label),
            "category_confidence": round(confidence, 2),
            "matching_explanation": f"CLIP ViT fallback matched frames to {predicted_label}.",
        }
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        # #region agent log
        _agent_log("A", "AI_model.py:_predict_clip_fallback", "fallback inference failed", {"error": str(exc)})
        # #endregion
        return {}


def _predict_clip_images(
    images: list[Any],
) -> dict[str, Any]:

    if not images:

        return {}

    if not _load_finetuned_clip():

        return _predict_clip_fallback(images)

    try:

        import torch

        encoded = _CLIP_PROCESSOR(
            images=images,
            return_tensors="pt"
        )

        device = _clip_device()

        pixel_values = (
            encoded["pixel_values"]
            .to(device)
        )

        with torch.no_grad():

            outputs = _CLIP_MODEL(
                pixel_values=pixel_values
            )

            probabilities = torch.softmax(
                outputs.logits,
                dim=-1
            )

        probabilities = (
            probabilities
            .detach()
            .cpu()
            .numpy()
        )

        # Average probabilities across
        # frames rather than averaging raw
        # embeddings.
        mean_probabilities = (
            probabilities.mean(
                axis=0
            )
        )

        best_index = int(
            np_argmax(
                mean_probabilities
            )
        )

        best_probability = float(
            mean_probabilities[
                best_index
            ]
        )

        if (
            not _CLIP_LABELS
            or
            best_index
            >=
            len(_CLIP_LABELS)
        ):

            predicted_label = (
                str(best_index)
            )

        else:

            predicted_label = (
                _CLIP_LABELS[
                    best_index
                ]
            )

        # Top predictions are useful for
        # debugging and explanation.
        ranked_indices = sorted(
            range(
                len(mean_probabilities)
            ),
            key=lambda index:
                mean_probabilities[index],
            reverse=True
        )

        top_predictions = []

        for index in ranked_indices[:5]:

            if (
                _CLIP_LABELS
                and
                index < len(_CLIP_LABELS)
            ):

                label = _CLIP_LABELS[
                    index
                ]

            else:

                label = str(index)

            top_predictions.append(
                {
                    "label": label,
                    "confidence": round(
                        float(
                            mean_probabilities[
                                index
                            ]
                        ),
                        4
                    ),
                }
            )

        domain = _visual_domain_for(
            predicted_label
        )

        return {

            # Fine-grained issue.
            "issue_type":
                predicted_label,

            # Existing application-compatible
            # civic domain.
            "predicted_category":
                domain,

            "category_confidence":
                round(
                    best_probability,
                    4
                ),

            "top_predictions":
                top_predictions,

            "matching_explanation":
                (
                    "Fine-tuned CLIP ViT "
                    "classified the sampled "
                    f"frames as "
                    f"{predicted_label} "
                    f"({best_probability * 100:.1f}% "
                    "model confidence)."
                ),
        }

    except (
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:

        print(
            "[AI_model] CLIP inference "
            f"failed: {exc}"
        )

        return {}


def np_argmax(values):

    return max(
        range(len(values)),
        key=lambda index: values[index]
    )


# ---------------------------------------------------------------------------
# Visual frame classification
# ---------------------------------------------------------------------------

def classify_visual_frames(
    frames: Iterable[Any]
) -> dict[str, Any]:
    """
    Classify sampled image/video frames using
    the fine-tuned CLIP ViT classifier.

    Multiple frames are combined by averaging
    class probabilities.
    """

    images = [
        frame
        for frame in frames
        if frame is not None
    ]

    if not images:

        return {}

    return _predict_clip_images(
        images
    )


# ---------------------------------------------------------------------------
# Still image classification
# ---------------------------------------------------------------------------

def classify_image_problem(
    image_bytes: bytes
) -> dict[str, Any]:
    """
    Classify a still proof image.
    """

    if not image_bytes:

        return {}

    try:

        from PIL import Image

        with Image.open(
            BytesIO(image_bytes)
        ) as image:

            return classify_visual_frames(
                [
                    image.convert(
                        "RGB"
                    )
                ]
            )

    except (
        OSError,
        ValueError,
        TypeError,
    ):

        return {}


# ---------------------------------------------------------------------------
# Video frame extraction
# ---------------------------------------------------------------------------

def extract_video_frames(
    video_bytes: bytes,
    max_frames: int = 12,
) -> list[Any]:
    """
    Sample evenly spaced RGB frames from
    an uploaded MP4/WebM clip.

    The old implementation used 8 frames.
    We use 12 here because the fine-tuned
    classifier benefits from slightly more
    visual coverage.
    """

    if not video_bytes:

        return []

    try:

        import cv2

        from PIL import Image

    except ImportError:

        # #region agent log
        _agent_log("B", "AI_model.py:extract_video_frames", "cv2 or PIL missing", {"nbytes": len(video_bytes)})
        # #endregion
        return []

    if not hasattr(cv2, "VideoCapture"):
        # #region agent log
        _agent_log("B", "AI_model.py:extract_video_frames", "cv2 stub without VideoCapture", {"nbytes": len(video_bytes)})
        # #endregion
        return []

    path = ""

    capture = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            delete=False
        ) as handle:

            handle.write(
                video_bytes
            )

            path = handle.name

        capture = cv2.VideoCapture(
            path
        )

        if not capture.isOpened():

            # #region agent log
            _agent_log("B", "AI_model.py:extract_video_frames", "VideoCapture failed", {"nbytes": len(video_bytes), "path": path})
            # #endregion
            return []

        total = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
            or 0
        )

        if total <= 0:

            return []

        frame_count = min(
            max_frames,
            total
        )

        if frame_count == 1:

            indexes = [0]

        else:

            indexes = [
                int(
                    round(
                        index
                        *
                        (total - 1)
                        /
                        (frame_count - 1)
                    )
                )

                for index
                in range(frame_count)
            ]

        frames = []

        for position in indexes:

            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                position
            )

            ok, frame = (
                capture.read()
            )

            if not ok or frame is None:

                continue

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            image = Image.fromarray(
                rgb
            )

            frames.append(
                image
            )

        # #region agent log
        _agent_log("B", "AI_model.py:extract_video_frames", "frames sampled", {"nbytes": len(video_bytes), "total": total, "nframes": len(frames)})
        # #endregion
        return frames

    except (
        OSError,
        ValueError,
        RuntimeError,
        AttributeError,
    ):

        return []

    finally:

        if capture is not None:

            capture.release()

        if path:

            try:

                os.unlink(
                    path
                )

            except OSError:

                pass


# ---------------------------------------------------------------------------
# Video classification
# ---------------------------------------------------------------------------

def classify_video_proof(
    video_bytes: bytes
) -> dict[str, Any]:
    """
    Classify uploaded video evidence.

    The video itself is still treated as
    supporting evidence, exactly as before.

    The sampled frames are classified using
    the fine-tuned civic CLIP model.
    """

    try:
        frames = extract_video_frames(
            video_bytes,
            max_frames=12
        )
    except Exception:  # pragma: no cover
        frames = []

    if not frames:

        # #region agent log
        _agent_log("B", "AI_model.py:classify_video_proof", "no frames; skip CLIP", {"nbytes": len(video_bytes)})
        # #endregion
        return {

            "status":
                "unverified",

            "message":
                "Video stored as supporting "
                "evidence. Location verification "
                "is only applied to geotagged photos.",
        }

    visual = classify_visual_frames(
        frames
    )

    result = {

        "status":
            "unverified",

        "message":
            "Video stored as supporting "
            "evidence. Location verification "
            "is only applied to geotagged photos.",
    }

    result.update(
        visual
    )

    # #region agent log
    _agent_log("A", "AI_model.py:classify_video_proof", "video classified", {"nbytes": len(video_bytes), "nframes": len(frames), "visual_keys": list(visual.keys()), "predicted": visual.get("predicted_category"), "issue_type": visual.get("issue_type")})
    # #endregion

    if visual:

        issue_type = visual.get(
            "issue_type"
        )

        domain = visual.get(
            "predicted_category"
        )

        confidence = float(
            visual.get(
                "category_confidence",
                0
            )
            or 0
        )

        result["message"] = (
            "Video stored as supporting "
            "evidence (not geotagged). "
            "Visual classifier identified "
            f"{issue_type} "
            f"under {domain} "
            f"with {confidence * 100:.1f}% "
            "model confidence."
        )

    return result


# ---------------------------------------------------------------------------
# Merge text + visual classification
# ---------------------------------------------------------------------------

def merge_text_and_visual_classification(
    text: dict[str, Any],
    visual: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Merge existing text classification with
    fine-tuned visual classification.

    IMPORTANT:

    The application already uses broad domains
    such as:

        Energy
        Water Resources
        Urban Infrastructure
        Sanitation

    Therefore:

        pothole
            -> Urban Infrastructure

        loose_cable
            -> Energy

        water_leak
            -> Water Resources

    The fine-grained prediction is retained as
    `issue_type` in the returned dictionary.
    """

    merged = dict(
        text
    )

    if (
        not visual
        or
        not visual.get(
            "predicted_category"
        )
    ):

        return merged

    visual_category = (
        visual[
            "predicted_category"
        ]
    )

    visual_confidence = float(
        visual.get(
            "category_confidence",
            0
        )
        or 0
    )

    text_confidence = float(
        text.get(
            "category_confidence",
            0
        )
        or 0
    )

    # Keep the existing database fields
    # compatible with the application.
    merged[
        "video_predicted_category"
    ] = visual_category

    merged[
        "video_confidence"
    ] = round(
        visual_confidence,
        4
    )

    merged[
        "video_explanation"
    ] = visual.get(
        "matching_explanation",
        ""
    )

    # Fine-grained class.
    if visual.get(
        "issue_type"
    ):

        merged[
            "video_issue_type"
        ] = visual[
            "issue_type"
        ]

    # Keep the existing application-level
    # category as the prediction.
    if visual_confidence >= text_confidence:

        merged[
            "predicted_category"
        ] = visual_category

        merged[
            "category_confidence"
        ] = visual_confidence

    explanations = " ".join(

        part

        for part in (
            visual.get(
                "matching_explanation",
                ""
            ),

            text.get(
                "matching_explanation",
                ""
            ),
        )

        if part
    ).strip()

    if explanations:

        merged[
            "matching_explanation"
        ] = explanations

    return merged

DEFAULT_RESEARCH_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "research_institute"
    / "jharkhand_research_institute_recommender_v3.joblib"
)

# Backward-compatible fallback for the model previously generated beside
# the Python script.
LEGACY_RESEARCH_MODEL_PATH = (
    BASE_DIR
    / "jharkhand_research_institute_recommender_v3.joblib"
)

RESEARCH_INSTITUTE_MODEL_PATH = Path(
    os.environ.get(
        "RESEARCH_INSTITUTE_MODEL_PATH",
        str(DEFAULT_RESEARCH_MODEL_PATH),
    )
)

_RESEARCH_MODEL: dict[str, Any] | None = None
_RESEARCH_MODEL_LOADED = False


def _resolve_research_model_path() -> Path:
    """Resolve the research recommender model path."""
    configured = RESEARCH_INSTITUTE_MODEL_PATH

    if configured.exists():
        return configured

    if (
        "RESEARCH_INSTITUTE_MODEL_PATH" not in os.environ
        and LEGACY_RESEARCH_MODEL_PATH.exists()
    ):
        return LEGACY_RESEARCH_MODEL_PATH

    return configured


def _load_research_institute_model() -> dict[str, Any] | None:
    """
    Lazily load the saved V3 research-institute model.

    Lazy loading keeps startup fast and means the existing civic AI does not
    require the research-model dependencies until this feature is used.
    """
    global _RESEARCH_MODEL
    global _RESEARCH_MODEL_LOADED

    if _RESEARCH_MODEL_LOADED:
        return _RESEARCH_MODEL

    _RESEARCH_MODEL_LOADED = True

    model_path = _resolve_research_model_path()

    if not model_path.exists():
        print(
            "[AI_model] Research institute model not found at "
            f"{model_path}"
        )
        return None

    try:
        import joblib

        model = joblib.load(model_path)

        required_keys = {
            "word_vectorizer",
            "char_vectorizer",
            "classifier",
            "experience_prior",
            "experience_weight",
            "eligible_institutes",
        }

        missing = required_keys.difference(model.keys())

        if missing:
            raise ValueError(
                "Saved research model is missing required fields: "
                + ", ".join(sorted(missing))
            )

        _RESEARCH_MODEL = model

        print(
            "[AI_model] Loaded research institute recommender: "
            f"{model_path}"
        )

        return _RESEARCH_MODEL

    except (
        ImportError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        print(
            "[AI_model] Could not load research institute model: "
            f"{exc}"
        )
        _RESEARCH_MODEL = None
        return None


def research_institute_model_available() -> bool:
    """Return True when the saved V3 recommender can be loaded."""
    return _load_research_institute_model() is not None


def recommend_research_institutes(
    project_title: str,
    research_area: str = "",
    research_keywords: str = "",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Recommend Jharkhand research/technical institutes for a new project.

    Parameters
    ----------
    project_title:
        Title or short description of the proposed research project.

    research_area:
        Optional research area/domain.

    research_keywords:
        Optional semicolon- or comma-separated research keywords.

    top_k:
        Maximum number of ranked institutes to return.

    Returns
    -------
    list[dict[str, Any]]
        Each result contains:
            institution
            final_score
            content_score
            experience_score

        Scores are ranking scores, NOT probabilities.

    Notes
    -----
    The V3 model uses content as the dominant signal and experience only as
    a small prior. Institutes with insufficient project records were not
    included as supervised classes in V3.
    """
    title = str(project_title or "").strip()
    area = str(research_area or "").strip()
    keywords = str(research_keywords or "").strip()

    if not title and not area and not keywords:
        return []

    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 5

    top_k = max(1, min(top_k, 20))

    model = _load_research_institute_model()

    if model is None:
        return []

    try:
        from scipy.sparse import hstack

        word_vectorizer = model["word_vectorizer"]
        char_vectorizer = model["char_vectorizer"]
        classifier = model["classifier"]

        # Keep this feature construction EXACTLY aligned with V3:
        # title + area twice + keywords twice.
        text = (
            f"{title} "
            f"{area} {area} "
            f"{keywords} {keywords}"
        )

        X = hstack([
            word_vectorizer.transform([text]),
            char_vectorizer.transform([text]),
        ])

        raw_scores = classifier.decision_function(X)

        # LinearSVC is binary/multiclass. The V3 model currently has four
        # supervised institute classes, but keep this compatible with either
        # binary or multiclass decision output.
        if getattr(raw_scores, "ndim", 1) == 1:
            raw_scores = [
                [-float(raw_scores[0]), float(raw_scores[0])]
            ]

        row_scores = raw_scores[0]
        classes = classifier.classes_

        # V3 normalization: convert margins to a 0..1 ranking scale.
        minimum = min(float(score) for score in row_scores)
        maximum = max(float(score) for score in row_scores)

        if maximum == minimum:
            content_scores = [0.5] * len(row_scores)
        else:
            content_scores = [
                (float(score) - minimum) / (maximum - minimum)
                for score in row_scores
            ]

        experience_prior = model["experience_prior"]
        experience_weight = float(model["experience_weight"])

        experience_scores = [
            float(experience_prior.get(institute, 0.0))
            for institute in classes
        ]

        final_scores = [
            (
                (1.0 - experience_weight) * content
                + experience_weight * experience
            )
            for content, experience in zip(
                content_scores,
                experience_scores,
            )
        ]

        ranked_indices = sorted(
            range(len(final_scores)),
            key=lambda index: final_scores[index],
            reverse=True,
        )

        results = []

        for index in ranked_indices[:top_k]:
            results.append({
                "institution": str(classes[index]),
                "final_score": round(
                    float(final_scores[index]), 4
                ),
                "content_score": round(
                    float(content_scores[index]), 4
                ),
                "experience_score": round(
                    float(experience_scores[index]), 4
                ),
            })

        return results

    except (
        ImportError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ) as exc:
        print(
            "[AI_model] Research institute recommendation failed: "
            f"{exc}"
        )
        return []


def get_research_institute_model_info() -> dict[str, Any]:
    """
    Return metadata useful to the application/UI.

    This does not expose internal model objects.
    """
    model = _load_research_institute_model()

    if model is None:
        return {
            "available": False,
            "model_path": str(_resolve_research_model_path()),
        }

    return {
        "available": True,
        "model_path": str(_resolve_research_model_path()),
        "experience_weight": float(
            model["experience_weight"]
        ),
        "eligible_institutes": list(
            model["eligible_institutes"]
        ),
        "excluded_low_data_institutes": list(
            model.get(
                "excluded_low_data_institutes",
                [],
            )
        ),
        "experience_definition": (
            "Observed project records in the dataset; "
            "not a verified completed-project count."
        ),
    }