"""
Semantic problem tagging for civic issue reports.

Uses Sentence Transformers with a multilingual E5 model to:

1. Understand the title + description of a civic report.
2. Determine the most likely civic problem category.
3. Apply stable/canonical tags.
4. Compare the user's selected category with the semantic classification.
5. Flag likely category mismatches.
6. Store the model/version information with the issue.

Install:
    pip install sentence-transformers

Recommended model:
    intfloat/multilingual-e5-small

The model is downloaded automatically the first time it is used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
import json

from sentence_transformers import SentenceTransformer

# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "intfloat/multilingual-e5-small"

TAG_VERSION = "semantic-e5-small-v1"

# Minimum confidence at which we consider a semantic prediction
# strong enough to flag a user's selected category as suspicious.
MISMATCH_THRESHOLD = 0.65

# Number of prototype examples whose similarity contributes to
# the category score.
TOP_PROTOTYPES_PER_CATEGORY = 3


# ============================================================
# MODEL
# ============================================================

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """
    Load the Sentence Transformer lazily.

    This means importing tagging.py does not immediately download/load
    the model. The model is loaded when the first issue is classified.
    """

    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


# ============================================================
# CATEGORY DESCRIPTIONS
# ============================================================

CATEGORY_DESCRIPTIONS: dict[str, str] = {

    "Roadways": (
        "Problems involving roads, streets, potholes, broken roads, "
        "road cracks, damaged roads, traffic hazards and unsafe road conditions."
    ),

    "Electricity": (
        "Problems involving electricity supply, power cuts, power outages, "
        "transformers, electrical wiring, live wires, voltage problems "
        "and malfunctioning streetlights."
    ),

    "Water Supply": (
        "Problems involving municipal water supply, water shortages, "
        "no water, leaking pipes, damaged pipelines, low water pressure "
        "and contaminated water."
    ),

    "Garbage Collection": (
        "Problems involving garbage, rubbish, trash, waste collection, "
        "uncollected waste, illegal dumping, litter, overflowing bins "
        "and sanitation."
    ),

    "Public Transport": (
        "Problems involving buses, bus frequency, bus timings, bus stops, "
        "public transport, trains, metro services, delays and transportation availability."
    ),

    "Drainage and Flooding": (
        "Problems involving blocked drains, drainage systems, flooding, "
        "waterlogging, sewage, stormwater and overflowing drains."
    ),

    "Footpaths and Accessibility": (
        "Problems involving footpaths, sidewalks, pavements, pedestrian access, "
        "wheelchair accessibility, ramps, curbs and blocked walkways."
    ),

    "Public Safety": (
        "Problems involving unsafe areas, accidents, crime, dangerous conditions, "
        "harassment, security hazards and risks to residents."
    ),

    "Other Civic Issue": (
        "A civic or municipal problem that does not clearly belong to "
        "roads, electricity, water, garbage, transport, drainage, accessibility "
        "or public safety."
    ),
}


# ============================================================
# MULTILINGUAL CATEGORY PROTOTYPES
# ============================================================
#
# These are semantic examples rather than exact keywords.
#
# English + Hindi + Hinglish examples are intentionally included.
#
# As real reports are collected, these can eventually be expanded
# using moderator-confirmed examples from the database.
# ============================================================

CATEGORY_PROTOTYPES: dict[str, tuple[str, ...]] = {

    "Roadways": (
        "There is a large pothole in the road.",
        "The road is badly damaged.",
        "The street has many potholes.",
        "There are several holes in the road.",
        "The road surface is broken.",
        "The road is full of cracks.",
        "Cars are swerving to avoid potholes.",
        "Vehicles are having difficulty because of the damaged road.",
        "The road needs immediate repair.",
        "A section of the road has collapsed.",
        "The street is in terrible condition.",
        "There is a dangerous pothole near the school.",
        "सड़क में बहुत बड़ा गड्ढा है।",
        "सड़क पर कई गड्ढे हैं।",
        "सड़क बहुत खराब हो गई है।",
        "सड़क टूट गई है।",
        "सड़क की हालत बहुत खराब है।",
        "सड़क पर दरारें पड़ गई हैं।",
        "गड्ढों के कारण वाहन चलाने में परेशानी हो रही है।",
        "सड़क की मरम्मत की जरूरत है।",
        "Road mein bahut bada gaddha hai.",
        "Yahan road bahut kharab hai.",
        "Road par bahut saare potholes hain.",
        "Road toot gayi hai.",
        "Road ki condition bahut kharab hai.",
        "Gaddhon ki wajah se gaadi chalane mein problem ho rahi hai.",
        "Road repair ki zarurat hai.",
    ),

    "Electricity": (
        "There is no electricity in the area.",
        "There has been a power outage.",
        "The electricity supply has been interrupted.",
        "Power has been cut since yesterday.",
        "The transformer is not working.",
        "There is a problem with the transformer.",
        "A power pole is damaged.",
        "A live electrical wire is hanging dangerously.",
        "Electrical wires are exposed.",
        "The voltage is fluctuating.",
        "The streetlight is not working.",
        "Several streetlights are not working.",
        "The street is dark because the lights are broken.",
        "There is an electrical hazard near the road.",
        "इलाके में बिजली नहीं आ रही है।",
        "कल से बिजली नहीं है।",
        "बिजली की सप्लाई बंद है।",
        "बिजली बार-बार जा रही है।",
        "ट्रांसफॉर्मर खराब है।",
        "बिजली का तार नीचे लटक रहा है।",
        "स्ट्रीट लाइट खराब है।",
        "रात में सड़क पर अंधेरा रहता है।",
        "बिजली का वोल्टेज बहुत कम है।",
        "Yahan bijli nahi aa rahi hai.",
        "Kal se power nahi hai.",
        "Bijli baar baar ja rahi hai.",
        "Transformer kharab hai.",
        "Bijli ka wire neeche latak raha hai.",
        "Street light kharab hai.",
        "Raat mein road par bahut andhera hota hai.",
        "Voltage bahut low hai.",
    ),

    "Water Supply": (
        "There is no water supply in the area.",
        "The water supply has stopped.",
        "Residents have not received water since yesterday.",
        "There is a shortage of drinking water.",
        "The municipal water pipeline is leaking.",
        "A water pipe has burst.",
        "The pipeline is damaged.",
        "Water is leaking onto the street.",
        "The tap water supply is irregular.",
        "There is very little water pressure.",
        "The water supply is contaminated.",
        "The water coming from the tap is dirty.",
        "Residents are not getting enough water.",
        "There is a problem with the municipal water line.",
        "इलाके में पानी की सप्लाई नहीं आ रही है।",
        "कल से पानी नहीं आया है।",
        "पानी की सप्लाई बंद है।",
        "पानी की पाइपलाइन लीक हो रही है।",
        "पाइपलाइन टूट गई है।",
        "पानी का प्रेशर बहुत कम है।",
        "नल से गंदा पानी आ रहा है।",
        "पीने का पानी उपलब्ध नहीं है।",
        "लोगों को पर्याप्त पानी नहीं मिल रहा है।",
        "Yahan paani nahi aa raha hai.",
        "Kal se paani ki supply band hai.",
        "Paani ki pipeline leak ho rahi hai.",
        "Pipeline toot gayi hai.",
        "Paani ka pressure bahut low hai.",
        "Nal se ganda paani aa raha hai.",
        "Paani regular nahi aa raha hai.",
        "Area mein paani ki bahut problem hai.",
    ),

    "Garbage Collection": (
        "Garbage has not been collected.",
        "Waste has been piling up for several days.",
        "The garbage collection truck has not arrived.",
        "Household waste is accumulating on the street.",
        "There is a large garbage dump near the road.",
        "Someone is illegally dumping waste here.",
        "The garbage bin is overflowing.",
        "The public garbage bin is full.",
        "There is litter everywhere.",
        "Waste is being dumped in an open area.",
        "The area has become unhygienic because of garbage.",
        "Garbage collection is irregular.",
        "People are throwing rubbish on the roadside.",
        "There is a foul smell from accumulated waste.",
        "कई दिनों से कूड़ा नहीं उठाया गया है।",
        "सड़क के किनारे कचरा जमा है।",
        "कूड़ेदान भर गया है।",
        "कूड़ा सड़क पर फैल गया है।",
        "यहां खुले में कचरा फेंका जा रहा है।",
        "कचरा उठाने वाली गाड़ी नहीं आ रही है।",
        "इलाके में बहुत गंदगी है।",
        "कूड़े की वजह से बदबू आ रही है।",
        "Kayi din se kachra nahi uthaya gaya.",
        "Road ke side mein bahut kachra pada hai.",
        "Dustbin overflow ho gaya hai.",
        "Kachra road par phail gaya hai.",
        "Garbage truck nahi aa raha hai.",
        "Area mein bahut gandagi hai.",
        "Kachre ki wajah se badbu aa rahi hai.",
    ),

    "Public Transport": (
        "Buses are not arriving on time.",
        "The bus frequency is too low.",
        "There are not enough buses in the area.",
        "The bus stop is not being serviced properly.",
        "Public transport is unreliable.",
        "The bus service has been reduced.",
        "The bus is frequently delayed.",
        "There is no public transport available nearby.",
        "The metro service is frequently delayed.",
        "The train is regularly delayed.",
        "Public transportation is overcrowded.",
        "The bus timings are inconvenient.",
        "There is no bus service after a certain time.",
        "Residents have difficulty accessing public transport.",
        "बस समय पर नहीं आती है।",
        "इलाके में बसें बहुत कम हैं।",
        "बस के लिए बहुत देर तक इंतजार करना पड़ता है।",
        "सार्वजनिक परिवहन की सुविधा खराब है।",
        "बस सेवा नियमित नहीं है।",
        "बस बहुत देर से आती है।",
        "यहां सार्वजनिक परिवहन उपलब्ध नहीं है।",
        "ट्रेन अक्सर लेट होती है।",
        "Bus time par nahi aati.",
        "Yahan buses bahut kam hain.",
        "Bus ke liye bahut wait karna padta hai.",
        "Public transport reliable nahi hai.",
        "Bus service bahut kharab hai.",
        "Bus stop par bus bahut late aati hai.",
        "Train aksar late hoti hai.",
    ),

    "Drainage and Flooding": (
        "The drain is blocked.",
        "The drainage system is clogged.",
        "Rainwater is not draining properly.",
        "The street is flooded after rain.",
        "There is severe waterlogging on the road.",
        "The drain is overflowing.",
        "Sewage is overflowing onto the street.",
        "The stormwater drain is blocked.",
        "The drainage system needs cleaning.",
        "Rainwater is accumulating in the area.",
        "The road floods whenever it rains.",
        "The sewer is overflowing.",
        "There is stagnant water near the houses.",
        "Water remains on the street for several days.",
        "The drainage infrastructure is inadequate.",
        "नाली बंद है।",
        "नाली में पानी नहीं जा रहा है।",
        "बारिश के बाद सड़क पर पानी भर जाता है।",
        "इलाके में जलभराव हो गया है।",
        "नाली का पानी सड़क पर आ रहा है।",
        "नाली ओवरफ्लो हो रही है।",
        "सीवेज सड़क पर बह रहा है।",
        "बारिश का पानी जमा हो जाता है।",
        "हर बारिश में यह इलाका डूब जाता है।",
        "Naali band hai.",
        "Naali ka paani road par aa raha hai.",
        "Barish ke baad road par paani bhar jata hai.",
        "Yahan waterlogging ho jati hai.",
        "Drain completely block hai.",
        "Sewage road par aa raha hai.",
        "Naali overflow ho rahi hai.",
        "Har baarish mein yahan flood ho jata hai.",
        "Paani kai din tak jama rehta hai.",
    ),

    "Footpaths and Accessibility": (
        "The footpath is broken.",
        "The sidewalk is badly damaged.",
        "There is no proper footpath.",
        "The pavement is unsafe for pedestrians.",
        "The sidewalk is blocked.",
        "Vehicles are parked on the footpath.",
        "Street vendors are blocking the footpath.",
        "The pedestrian path is inaccessible.",
        "There is no wheelchair access.",
        "The wheelchair ramp is broken.",
        "The curb is too high for wheelchair users.",
        "The pedestrian crossing is difficult to use.",
        "People have to walk on the road because the footpath is blocked.",
        "The pavement is uneven and difficult to walk on.",
        "फुटपाथ टूटा हुआ है।",
        "फुटपाथ पर चलना मुश्किल है।",
        "यहां सही फुटपाथ नहीं है।",
        "फुटपाथ पर गाड़ियां खड़ी रहती हैं।",
        "फुटपाथ बंद है।",
        "व्हीलचेयर के लिए रास्ता नहीं है।",
        "रैंप टूटा हुआ है।",
        "लोगों को सड़क पर चलना पड़ता है।",
        "Footpath toot gaya hai.",
        "Yahan proper footpath nahi hai.",
        "Footpath par gaadiyan khadi hain.",
        "Footpath blocked hai.",
        "Pedestrians ko road par chalna padta hai.",
        "Wheelchair ke liye access nahi hai.",
        "Ramp toot gaya hai.",
        "Footpath bahut uneven hai.",
    ),

    "Public Safety": (
        "This area is unsafe at night.",
        "There have been repeated accidents here.",
        "This location is dangerous for pedestrians.",
        "There is a serious safety hazard here.",
        "People are afraid to use this street at night.",
        "There have been reports of street crime.",
        "There is frequent harassment in this area.",
        "The location is poorly lit and unsafe.",
        "There is a dangerous open area near the road.",
        "Children are at risk because of this hazard.",
        "The area needs better security.",
        "There have been several accidents at this intersection.",
        "The road is dangerous because drivers cannot see pedestrians.",
        "There is a potential danger to residents.",
        "यह इलाका रात में सुरक्षित नहीं है।",
        "यह जगह बहुत खतरनाक है।",
        "यहां अक्सर दुर्घटनाएं होती हैं।",
        "रात में यहां चलना सुरक्षित नहीं है।",
        "इलाके में सुरक्षा की समस्या है।",
        "यहां लोगों के साथ छेड़छाड़ होती है।",
        "यहां सुरक्षा व्यवस्था बेहतर होनी चाहिए।",
        "Yeh area raat mein safe nahi hai.",
        "Yahan aksar accidents hote hain.",
        "Raat mein yahan chalna dangerous hai.",
        "Yahan safety ka problem hai.",
        "Is area mein security badhani chahiye.",
        "Log raat mein yahan aane se darte hain.",
        "Yahan harassment ki problem hai.",
    ),

    "Other Civic Issue": (
        "I want to report a civic problem.",
        "There is a municipal problem in my area.",
        "There is an issue with public infrastructure.",
        "There is a local government service problem.",
        "This public facility needs attention.",
        "There is a problem in the neighbourhood.",
        "The municipality needs to address this issue.",
        "मेरे इलाके में एक नागरिक समस्या है।",
        "नगरपालिका से जुड़ी समस्या है।",
        "इलाके में सार्वजनिक सुविधा की समस्या है।",
        "Mere area mein ek civic problem hai.",
        "Municipality se related problem hai.",
        "Area mein public facility ki problem hai.",
    ),
}


# ============================================================
# CANONICAL TAGS
# ============================================================
#
# These should remain stable because other parts of the application
# can eventually use them for routing, recommendations and analytics.
# ============================================================

CATEGORY_TAGS: dict[str, tuple[str, ...]] = {

    "Roadways": (
        "road_damage",
        "pothole",
        "road_crack",
        "traffic_hazard",
    ),

    "Electricity": (
        "power",
        "power_outage",
        "electrical",
        "streetlight",
        "wiring",
    ),

    "Water Supply": (
        "water",
        "water_shortage",
        "water_leak",
        "pipeline",
        "water_supply",
    ),

    "Garbage Collection": (
        "garbage",
        "waste",
        "waste_collection",
        "illegal_dumping",
        "sanitation",
    ),

    "Public Transport": (
        "bus",
        "transit",
        "transport",
        "frequency",
        "delay",
    ),

    "Drainage and Flooding": (
        "flooding",
        "waterlogging",
        "drainage",
        "blocked_drain",
        "sewage",
    ),

    "Footpaths and Accessibility": (
        "footpath",
        "sidewalk",
        "accessibility",
        "pedestrian",
        "wheelchair",
    ),

    "Public Safety": (
        "safety",
        "hazard",
        "crime",
        "accident",
        "harassment",
    ),

    "Other Civic Issue": (
        "other",
    ),
}


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass(frozen=True)
class ProblemTag:
    problem_type: str
    tags: tuple[str, ...]
    confidence: float

    submitted_category: str
    category_matches: bool
    category_mismatch: bool

    semantic_similarity: float
    submitted_category_similarity: float

    tag_version: str = TAG_VERSION


# ============================================================
# TEXT NORMALISATION
# ============================================================

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _normalise_category(category: str) -> str:
    """
    Handle small naming differences between the UI and our canonical
    semantic categories.

    For example:
        Roads -> Roadways
        Waste -> Garbage Collection
        Water -> Water Supply
        Streetlights -> Electricity
        Footpaths -> Footpaths and Accessibility
    """

    value = _normalise(category)

    aliases = {
        "roads": "roadways",
        "road": "roadways",

        "waste": "garbage collection",
        "garbage": "garbage collection",

        "water": "water supply",

        "streetlights": "electricity",
        "street lights": "electricity",
        "streetlight": "electricity",

        "footpaths": "footpaths and accessibility",
        "footpath": "footpaths and accessibility",

        "drainage": "drainage and flooding",
        "flooding": "drainage and flooding",

        "transport": "public transport",

        "safety": "public safety",

        "other": "other civic issue",
    }

    return aliases.get(value, value)


# ============================================================
# ISSUE TEXT
# ============================================================

def build_issue_text(issue: dict[str, Any]) -> str:
    """
    Build the semantic text from the actual problem information.

    IMPORTANT:
    The submitted category is deliberately excluded.

    Otherwise, selecting "Electricity" would itself influence the
    model into predicting Electricity.
    """

    title = str(issue.get("title", "")).strip()
    description = str(issue.get("description", "")).strip()

    parts = []

    if title:
        parts.append(title)

    if description:
        parts.append(description)

    return ". ".join(parts).strip()


# ============================================================
# EMBEDDING HELPERS
# ============================================================

def _encode_query(text: str):
    """
    E5 query embedding.

    E5 recommends the query: prefix for user/search-like inputs.
    """

    model = get_model()

    return model.encode(
        f"query: {text}",
        normalize_embeddings=True,
        convert_to_tensor=True,
    )


def _encode_passages(texts: list[str]):
    """
    E5 passage embeddings.

    Used for category descriptions and prototype examples.
    """

    model = get_model()

    return model.encode(
        [f"passage: {text}" for text in texts],
        normalize_embeddings=True,
        convert_to_tensor=True,
    )


# ============================================================
# PROTOTYPE CLASSIFICATION
# ============================================================

def _classify_against_prototypes(
    issue_embedding,
) -> tuple[str, float, dict[str, float]]:
    """
    Compare an issue against every category's prototype examples.

    For each category we take the strongest few prototype matches.

    This prevents one unusual prototype from completely determining
    the category.
    """

    categories = list(CATEGORY_PROTOTYPES.keys())

    all_prototypes = []
    prototype_categories = []

    for category in categories:
        for prototype in CATEGORY_PROTOTYPES[category]:
            all_prototypes.append(prototype)
            prototype_categories.append(category)

    prototype_embeddings = _encode_passages(all_prototypes)

    similarities = issue_embedding @ prototype_embeddings.T

    category_scores: dict[str, float] = {}

    for category in categories:

        scores = [
            float(similarities[index].item())
            for index, prototype_category
            in enumerate(prototype_categories)
            if prototype_category == category
        ]

        scores.sort(reverse=True)

        top_scores = scores[:TOP_PROTOTYPES_PER_CATEGORY]

        if top_scores:
            category_scores[category] = sum(top_scores) / len(top_scores)
        else:
            category_scores[category] = 0.0

    predicted_category = max(
        category_scores,
        key=category_scores.get,
    )

    predicted_score = category_scores[predicted_category]

    return predicted_category, predicted_score, category_scores


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_problem(issue: dict[str, Any]) -> ProblemTag:
    """
    Understand and classify a civic issue semantically.
    """

    text = build_issue_text(issue)

    submitted_category = str(
        issue.get("category", "")
    ).strip()

    # --------------------------------------------------------
    # No useful issue text
    # --------------------------------------------------------

    if not text:

        return ProblemTag(
            problem_type="Other Civic Issue",
            tags=CATEGORY_TAGS["Other Civic Issue"],
            confidence=0.0,

            submitted_category=submitted_category,
            category_matches=False,
            category_mismatch=bool(submitted_category),

            semantic_similarity=0.0,
            submitted_category_similarity=0.0,
        )

    # --------------------------------------------------------
    # Embed user's actual report
    # --------------------------------------------------------

    issue_embedding = _encode_query(text)

    (
        predicted_category,
        semantic_similarity,
        category_scores,
    ) = _classify_against_prototypes(issue_embedding)

    # --------------------------------------------------------
    # Compare against user's selected category
    # --------------------------------------------------------

    submitted_normalised = _normalise_category(
        submitted_category
    )

    canonical_submitted_category = None

    for category in CATEGORY_PROTOTYPES:

        if (
            _normalise_category(category)
            == submitted_normalised
        ):
            canonical_submitted_category = category
            break

    if canonical_submitted_category is None:

        submitted_category_similarity = 0.0
        category_matches = False

    else:

        submitted_category_similarity = category_scores.get(
            canonical_submitted_category,
            0.0,
        )

        category_matches = (
            canonical_submitted_category
            == predicted_category
        )

    # --------------------------------------------------------
    # Mismatch detection
    # --------------------------------------------------------
    #
    # Only flag a mismatch if:
    #
    #   1. We have a strong semantic prediction.
    #   2. The prediction differs from the submitted category.
    #
    # This avoids flagging borderline cases.
    # --------------------------------------------------------

    category_mismatch = (
        bool(submitted_category)
        and not category_matches
        and semantic_similarity >= MISMATCH_THRESHOLD
    )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------
    #
    # This is NOT a probability.
    #
    # It is a scaled semantic similarity score.
    # --------------------------------------------------------

    confidence = _similarity_to_confidence(
        semantic_similarity
    )

    return ProblemTag(
        problem_type=predicted_category,
        tags=CATEGORY_TAGS[predicted_category],
        confidence=round(confidence, 4),

        submitted_category=submitted_category,
        category_matches=category_matches,
        category_mismatch=category_mismatch,

        semantic_similarity=round(
            semantic_similarity,
            4,
        ),

        submitted_category_similarity=round(
            submitted_category_similarity,
            4,
        ),
    )


# ============================================================
# APPLY TAGGING TO ISSUE
# ============================================================

def tag_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """
    Add semantic classification information to an issue.

    This is the function map.py calls immediately before add_issue().
    """

    tagged = dict(issue)

    result = classify_problem(tagged)

    # Canonical classification
    tagged["problem_type"] = result.problem_type
    tagged["problem_tags"] = json.dumps(
    list(result.tags),
    ensure_ascii=False)

    # Confidence
    tagged["tag_confidence"] = result.confidence

    # User-selected category
    tagged["submitted_category"] = result.submitted_category

    # Consistency check
    tagged["category_matches"] = result.category_matches
    tagged["category_mismatch"] = result.category_mismatch

    # Raw semantic scores
    tagged["semantic_similarity"] = result.semantic_similarity
    tagged["submitted_category_similarity"] = (
        result.submitted_category_similarity
    )

    # Allows future versions of the classifier to coexist with
    # old classifications in the database.
    tagged["tag_version"] = result.tag_version

    return tagged


# ============================================================
# CONFIDENCE SCALING
# ============================================================

def _similarity_to_confidence(
    similarity: float,
) -> float:
    """
    Convert semantic similarity into a conservative 0-1 score.

    This is a heuristic, NOT a statistical probability.
    """

    minimum = 0.25
    maximum = 0.75

    if similarity <= minimum:
        return 0.0

    if similarity >= maximum:
        return 1.0

    return (
        similarity - minimum
    ) / (
        maximum - minimum
    )


# ============================================================
# LOCAL TESTING
# ============================================================

if __name__ == "__main__":

    test_issues = [

        # Correct category
        {
            "category": "Roads",
            "title": "Huge pothole near school",
            "description": (
                "There is a large hole in the road and cars "
                "are swerving to avoid it."
            ),
        },

        # Deliberately incorrect category
        {
            "category": "Electricity",
            "title": "Huge pothole near school",
            "description": (
                "There is a large hole in the road and cars "
                "are swerving to avoid it."
            ),
        },

        # Hindi
        {
            "category": "Water",
            "title": "पानी की समस्या",
            "description": (
                "कल से हमारे इलाके में पानी नहीं आ रहा है।"
            ),
        },

        # Hinglish
        {
            "category": "Waste",
            "title": "Kachra nahi uthaya gaya",
            "description": (
                "Kayi din se road ke side mein garbage pada hua hai."
            ),
        },

        # Drainage
        {
            "category": "Roads",
            "title": "Road par paani bhar gaya",
            "description": (
                "Har baarish ke baad yahan bahut waterlogging "
                "ho jati hai aur drain block hai."
            ),
        },
    ]

    for number, issue in enumerate(
        test_issues,
        start=1,
    ):

        print()
        print("=" * 70)
        print(f"TEST {number}")
        print("=" * 70)

        result = classify_problem(issue)
        print(
            "Submitted category:",
            result.submitted_category,
        )
        print(
            "Predicted category:",
            result.problem_type,
        )
        print(
            "Tags:",
            result.tags,
        )
        print(
            "Confidence:",
            result.confidence,
        )
        print(
            "Semantic similarity:",
            result.semantic_similarity,
        )
        print(
            "Submitted category similarity:",
            result.submitted_category_similarity,
        )
        print(
            "Category matches:",
            result.category_matches,
        )
        print(
            "CATEGORY MISMATCH:",
            result.category_mismatch,
        )