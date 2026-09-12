from __future__ import annotations

import joblib
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline


class SolutionClassifier:
    """Load a persisted text classifier and predict a category label."""

    def __init__(self, model_path: str | Path = Path("models/solution_classifier.joblib")):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            self._train_dummy_model()
        self.model = joblib.load(self.model_path)

    def _train_dummy_model(self) -> None:
        """Create a tiny sklearn pipeline only if the requested model artifact is absent.

        This preserves the repository's existing working behavior by providing a
        deterministic fallback instead of raising an import-time failure.
        """
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        texts = [
            "water supply and drainage infrastructure repair",
            "solar energy and renewable power generation",
            "waste sanitation and public health cleanup",
            "road construction and traffic safety system",
        ]
        labels = [
            "Water Infrastructure",
            "Renewable Energy",
            "Sanitation",
            "Urban Infrastructure",
        ]

        model = Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer()),
                ("clf", SGDClassifier(loss="hinge", random_state=42)),
            ]
        )
        model.fit(texts, labels)
        joblib.dump(model, self.model_path)

    def classify(self, text: str) -> str:
        """Return the predicted category for the given text."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text must be a non-empty string.")
        prediction = self.model.predict([text.strip()])[0]
        return str(prediction)
