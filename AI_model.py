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
        ):

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
        "./models/civic_clip_pothole_model",
        str(DEFAULT_CLIP_MODEL_DIR)
    )
)

_CLIP_MODEL: Any = None

_CLIP_PROCESSOR: Any = None

_CLIP_MODEL_LOADED = False

_CLIP_LABELS: list[str] = []


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

def _predict_clip_images(
    images: list[Any],
) -> dict[str, Any]:

    if not images:

        return {}

    if not _load_finetuned_clip():

        return {}

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

        return frames

    except (
        OSError,
        ValueError,
        RuntimeError,
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

    frames = extract_video_frames(
        video_bytes,
        max_frames=12
    )

    if not frames:

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