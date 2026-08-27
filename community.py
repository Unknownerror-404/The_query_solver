"""Community view and shared civic-issue operations for the local map app."""

from __future__ import annotations

import html
import math
import threading
from pathlib import Path

try:
    from .storage import add_issue_support, initialise, insert_issue, load_issues, update_issue
except ImportError:
    from storage import add_issue_support, initialise, insert_issue, load_issues, update_issue

DEFAULT_ISSUES = [
    {"id": 1, "title": "Pothole on Outer Ring Road", "category": "Roads", "area": "Bengaluru", "lat": 12.9352, "lng": 77.6245, "supporters": 28, "age": "5h ago", "description": "A deep pothole is slowing traffic near the service road."},
    {"id": 2, "title": "Garbage uncollected for four days", "category": "Waste", "area": "Indiranagar", "lat": 12.9784, "lng": 77.6408, "supporters": 18, "age": "4d ago", "description": "Household waste has accumulated beside the community park."},
    {"id": 3, "title": "Water cut, no notice", "category": "Water", "area": "Jayanagar", "lat": 12.9250, "lng": 77.5938, "supporters": 42, "age": "36h ago", "description": "The neighbourhood has had no supply since yesterday morning."},
    {"id": 4, "title": "Streetlight outage at junction", "category": "Streetlights", "area": "Koramangala", "lat": 12.9352, "lng": 77.6245, "supporters": 12, "age": "2d ago", "description": "Three streetlights are out, making the junction difficult to cross at night."},
]
JHARKHAND_DISTRICTS = (
    "Bokaro", "Chatra", "Deoghar", "Dhanbad", "Dumka", "East Singhbhum",
    "Garhwa", "Giridih", "Godda", "Gumla", "Hazaribagh", "Jamtara",
    "Khunti", "Koderma", "Latehar", "Lohardaga", "Pakur", "Palamu",
    "Ramgarh", "Ranchi", "Sahibganj", "Seraikela Kharsawan", "Simdega",
    "West Singhbhum",
)
JHARKHAND_DOMAINS = (
    "Education", "Healthcare", "Agriculture", "Water Resources", "Sanitation",
    "Environment", "Energy", "Urban Infrastructure", "Accessibility",
    "Public Administration", "Rural Livelihoods",
)
initialise(DEFAULT_ISSUES)
ISSUES = load_issues()
PROPOSALS: list[dict] = []
ISSUE_LOCK = threading.Lock()
PROPOSAL_LOCK = threading.Lock()
ISSUE_SUPPORTERS: dict[int, set[str]] = {}
SOLUTION_VOTES: dict[int, dict[str, int]] = {}


def distance_km(first_lat: float, first_lng: float, second_lat: float, second_lng: float) -> float:
    """Return the great-circle distance between two coordinates."""
    earth_radius_km = 6371.0
    latitude_delta = math.radians(second_lat - first_lat)
    longitude_delta = math.radians(second_lng - first_lng)
    value = math.sin(latitude_delta / 2) ** 2 + math.cos(math.radians(first_lat)) * math.cos(math.radians(second_lat)) * math.sin(longitude_delta / 2) ** 2
    return earth_radius_km * 2 * math.asin(math.sqrt(value))


def nearby_issues(latitude: float | None = None, longitude: float | None = None, radius_km: float = 2.0) -> list[dict]:
    with ISSUE_LOCK:
        issues = list(ISSUES)
    if latitude is None or longitude is None:
        return issues
    return [issue for issue in issues if distance_km(latitude, longitude, issue["lat"], issue["lng"]) <= radius_km]


def add_issue(issue: dict) -> dict:
    try:
        from .AI_model import find_duplicate
    except ImportError:
        from AI_model import find_duplicate

    match = find_duplicate(issue, ISSUES)
    if match and match.decision == "duplicate":
        with ISSUE_LOCK:
            match.issue["supporters"] += 1
            for field in ("proof_id", "proof_status", "proof_message"):
                if field in issue:
                    match.issue[field] = issue[field]
            update_issue(match.issue)
            return {"result": "duplicate", "issue": match.issue, "score": match.score}
    if match and match.decision == "possible_duplicate":
        return {"result": "possible_duplicate", "issue": match.issue, "score": match.score}
    with ISSUE_LOCK:
        saved_issue = insert_issue(issue)
        issue.update(saved_issue)
        issue.pop("_proof_type", None)
        issue.pop("_proof_data", None)
        ISSUES.append(issue)
        return {"result": "new", "issue": issue}


def upvote_issue(issue_id: int, user: str) -> tuple[bool, int]:
    with ISSUE_LOCK:
        for issue in ISSUES:
            if issue["id"] == issue_id:
                supported, count = add_issue_support(issue_id, user)
                if supported:
                    issue["supporters"] = count
                return supported, count
    return False, 0


def top_issues(limit: int = 5) -> list[dict]:
    with ISSUE_LOCK:
        return sorted(ISSUES, key=lambda issue: issue.get("supporters", 0), reverse=True)[:limit]


def add_proposal(proposal: dict) -> dict:
    with PROPOSAL_LOCK:
        proposal["id"] = max((item["id"] for item in PROPOSALS), default=0) + 1
        proposal["status"] = "Awaiting Approval"
        proposal["votes"] = 0
        PROPOSALS.append(proposal)
        return proposal


def proposal_status(proposal: dict) -> str:
    status_labels = {
        "Under review": "Under Professional Review",
        "Approved": "Solution Approved",
        "Non-feasible": "Marked Non-Feasible",
        "Needs revision": "Revision Requested",
    }
    return status_labels.get(proposal.get("status", ""), proposal.get("status", "Awaiting Approval"))


def issue_consideration_status(index: int) -> str:
    return "Awaiting Solution" if index == 1 else "Awaiting Consideration"


def vote_for_proposal(proposal_id: int, user: str) -> tuple[str, int]:
    with PROPOSAL_LOCK:
        proposal = next((item for item in PROPOSALS if item["id"] == proposal_id), None)
        if proposal is None:
            return "missing", 0
        issue_id = proposal["issue_id"]
    with ISSUE_LOCK:
        if user not in ISSUE_SUPPORTERS.get(issue_id, set()):
            return "ineligible", proposal["votes"]
    with PROPOSAL_LOCK:
        votes_for_issue = SOLUTION_VOTES.setdefault(issue_id, {})
        previous_proposal_id = votes_for_issue.get(user)
        if previous_proposal_id == proposal_id:
            return "already_voted", proposal["votes"]
        if previous_proposal_id is not None:
            previous = next(item for item in PROPOSALS if item["id"] == previous_proposal_id)
            previous["votes"] = max(0, previous["votes"] - 1)
        votes_for_issue[user] = proposal_id
        proposal["votes"] += 1
        return "changed" if previous_proposal_id is not None else "voted", proposal["votes"]


def proposal_batch(page: int, batch_size: int = 10) -> tuple[list[dict], int, int]:
    with PROPOSAL_LOCK:
        ordered = sorted(PROPOSALS, key=lambda item: item.get("votes", 0), reverse=True)
    page_count = max(1, (len(ordered) + batch_size - 1) // batch_size)
    page = max(1, min(page, page_count))
    start = (page - 1) * batch_size
    return ordered[start:start + batch_size], page, page_count


def review_proposal(proposal_id: int, reviewer: str, decision: str, explanation: str) -> tuple[str, dict | None]:
    allowed = {"Under review", "Approved", "Non-feasible", "Needs revision"}
    if decision not in allowed or not explanation.strip() or len(explanation) > 2000:
        return "invalid", None
    with PROPOSAL_LOCK:
        proposal = next((item for item in PROPOSALS if item["id"] == proposal_id), None)
        if proposal is None:
            return "missing", None
        proposal["status"] = decision
        proposal["review"] = {"reviewer": reviewer, "decision": decision, "explanation": explanation.strip()}
        return "updated", proposal


def professional_page(template: str, profile: dict, page: int) -> str:
        batch, current_page, page_count = proposal_batch(page)
        proposal_markup = "".join(professional_proposal_markup(item) for item in batch)
        reviewed = sum(1 for item in PROPOSALS if item.get("review"))
        return (template.replace("__USER__", html.escape(profile["name"]))
            .replace("__AFFILIATION__", html.escape(profile["affiliation"]))
            .replace("__ORGANIZATION__", html.escape(profile["organization"]))
            .replace("__ORG_SHORT__", html.escape(profile["organization"][:22]))
            .replace("__PAGE__", str(current_page)).replace("__PAGE_COUNT__", str(page_count))
            .replace("__TOTAL__", str(len(PROPOSALS))).replace("__REVIEWED__", str(reviewed))
            .replace("__PROPOSALS__", proposal_markup or '<p class="empty">No proposed solutions have been submitted yet.</p>')
            .replace("__PREV__", str(max(1, current_page - 1))).replace("__NEXT__", str(min(page_count, current_page + 1)))
            .replace("__PREV_DISABLED__", "disabled" if current_page == 1 else "")
            .replace("__NEXT_DISABLED__", "disabled" if current_page == page_count else ""))


def professional_proposal_markup(proposal: dict) -> str:
    review = proposal.get("review")
    review_markup = ""
    if review:
        review_markup = f'<div class="review-note"><b>{html.escape(review["decision"])}</b><br>{html.escape(review["explanation"])}<br><small>Reviewed by {html.escape(review["reviewer"])}</small></div>'
    return (f'<article class="proposal"><p class="meta">{html.escape(proposal["issue_title"])} · {proposal.get("votes", 0)} community votes</p>'
        f'<h2>{html.escape(proposal["title"])}</h2><p>{html.escape(proposal["description"])}</p>{proposal_visual_markup(proposal)}'
        f'{review_markup if review else professional_review_form(proposal)}</article>')


def professional_review_form(proposal: dict) -> str:
    return (f'<form class="review-form review" data-id="{proposal["id"]}"><input type="hidden" name="proposal_id" value="{proposal["id"]}">'
        '<label>Decision<select name="decision"><option>Under review</option><option>Approved</option><option>Non-feasible</option><option>Needs revision</option></select></label>'
        '<label>Explanation<textarea name="explanation" required maxlength="2000" placeholder="Explain the feasibility, evidence, or required changes."></textarea></label>'
        '<button type="submit">Save professional response</button></form>')


def proposal_page(template: str, user: str, message: str = "") -> str:
    issues = top_issues()
    issue_markup = "".join(
        f'<article class="issue"><span class="rank">#{index} · {issue.get("supporters", 0)} supporters</span><span class="status">{issue_consideration_status(index)}</span>'
        f'<h2>{html.escape(issue["title"])}</h2><p>{html.escape(issue.get("description", ""))}</p>'
        f'<p class="muted">{html.escape(issue.get("area", ""))} · {html.escape(issue.get("category", ""))}</p></article>'
        for index, issue in enumerate(issues, 1)
    )
    options = "".join(
        f'<option value="{issue["id"]}">#{index} · {html.escape(issue["title"])} ({issue.get("supporters", 0)} supporters)</option>'
        for index, issue in enumerate(issues, 1)
    )
    proposal_markup = "".join(
        f'<article class="proposal"><h2>{html.escape(item["title"])}</h2>'
        f'<p>{html.escape(item["description"])}</p>'
        f'{proposal_visual_markup(item)}'
        f'<p class="proposal-votes"><b>{item["votes"]} solution votes</b> <button class="solution-vote" data-id="{item["id"]}">Vote for this solution</button></p>'
        f'<span class="status">{html.escape(proposal_status(item))}</span></article>'
        for item in reversed(PROPOSALS)
    ) or '<p class="muted">No proposals yet. Be the first to add a practical idea.</p>'
    return (template.replace("__USER__", html.escape(user)).replace("__MESSAGE__", message)
            .replace("__ISSUES__", issue_markup).replace("__OPTIONS__", options).replace("__PROPOSALS__", proposal_markup))


def proposal_visual_markup(proposal: dict) -> str:
    visual_url = proposal.get("visual_url")
    if not visual_url:
        return ""
    return f'<p><a href="{html.escape(visual_url)}">View proposal visual</a></p>'


def proposed_solutions_markup() -> str:
    with PROPOSAL_LOCK:
        proposals = list(reversed(PROPOSALS))
    if not proposals:
        return '<p class="muted">No solution proposals yet. Add an idea for one of the top problems.</p>'
    return "".join(
        f'<article class="proposal"><p class="meta">For: {html.escape(item["issue_title"])}</p>'
        f'<h2>{html.escape(item["title"])}</h2><p>{html.escape(item["description"])}</p>'
        f'{proposal_visual_markup(item)}<p><b>{item["votes"]} solution votes</b> <button class="solution-vote" data-id="{item["id"]}">Vote for this solution</button></p>'
        f'<span class="status">{html.escape(proposal_status(item))}</span></article>'
        for item in proposals
    )


def proof_markup(issue: dict) -> str:
    proof_id = issue.get("proof_id")
    if not proof_id:
        return ""
    status = "GPS location verified" if issue.get("proof_status") == "verified" else "Location unverified"
    return f'<p><a href="/proof/{html.escape(proof_id)}">View photo proof</a> · {status}</p>'


def render_page(user: str, latitude: float | None = None, longitude: float | None = None) -> str:
    issues = nearby_issues(latitude, longitude)
    location_label = "Showing all civic voices" if latitude is None or longitude is None else "Showing voices within 2 km of your location"
    cards = "".join(
        f'<article class="issue"><div class="meta">{html.escape(issue["category"])} · {html.escape(issue["area"])}</div>'
        f'<h2>{html.escape(issue["title"])}</h2><p>{html.escape(issue.get("description", ""))}</p>'
        f'{proof_markup(issue)}'
        f'<div class="issue-footer"><span>{issue["supporters"]} supporters · {html.escape(issue["age"])}</span>'
        f'<button class="upvote" data-id="{issue["id"]}">▲ Support this voice</button></div></article>'
        for issue in issues
    ) or '<p class="empty">No civic issues were found in this area yet.</p>'
    template = Path(__file__).with_name("templates").joinpath("community.html").read_text(encoding="utf-8")
    return (template.replace("__USER__", html.escape(user)).replace("__LOCATION__", html.escape(location_label))
            .replace("__ISSUES__", cards).replace("__PROPOSALS__", proposed_solutions_markup()))


def json_page(user: str, location_label: str, cards: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Community · Civic Map</title><style>
:root{{--ink:#172b28;--muted:#667773;--paper:#f5f1e8;--accent:#e65f38;--line:#d9d7cd}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);background:var(--paper);font-family:Georgia,serif}}header{{padding:22px 28px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:end;gap:20px}}h1{{margin:0;font-size:clamp(2rem,5vw,3.6rem);font-weight:500}}.eyebrow,.meta{{color:var(--accent);font:700 11px Arial,sans-serif;letter-spacing:1.8px;text-transform:uppercase}}.tagline,a{{color:var(--muted);font:14px Arial,sans-serif}}main{{max-width:900px;margin:0 auto;padding:30px 24px}}.intro{{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--line);padding-bottom:18px;gap:20px}}.intro h2{{margin:6px 0 0;font-size:28px;font-weight:500}}.issues{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;margin-top:22px}}.issue{{padding:20px;background:#fffdf8;border:1px solid var(--line);transition:transform .18s ease,box-shadow .18s ease}}.issue:hover{{transform:translateY(-3px);box-shadow:6px 6px 0 var(--line)}}.issue h2{{font-size:20px;margin:8px 0}}.issue p{{color:var(--muted);line-height:1.45}}.issue-footer{{display:flex;justify-content:space-between;align-items:center;gap:10px;border-top:1px solid var(--line);padding-top:14px;font:12px Arial,sans-serif}}button{{cursor:pointer;border:1px solid var(--ink);background:transparent;padding:9px 10px;color:var(--ink)}}button:hover,.upvote.supported{{background:var(--ink);color:white}}.nav-button{{display:inline-block;padding:9px 12px;border:1px solid var(--ink);background:#fffdf8;color:var(--ink);text-decoration:none;font:700 12px Arial,sans-serif}}.nav-button:hover{{background:var(--ink);color:white}}.actions{{display:flex;align-items:center;gap:8px}}.back{{display:inline-block;margin-top:26px}}.empty{{color:var(--muted)}}@media(max-width:600px){{header,.intro{{align-items:start;flex-direction:column}}.issue-footer{{align-items:start;flex-direction:column}}}}
+</style></head><body><header><div><p class="eyebrow">Civic map · Community</p><h1>Local voices.</h1></div><div class="tagline">Signed in as {html.escape(user)} · <a href="/logout">Log out</a></div></header><main><section class="intro"><div><p class="eyebrow">Collective action</p><h2>What needs attention nearby?</h2><p>{html.escape(location_label)}</p></div><a href="/">Back to map</a></section><section class="issues">{cards}</section><a class="back" href="/">← Return to map</a></main><script>document.querySelectorAll('.upvote').forEach(button=>button.onclick=async()=>{{const response=await fetch('/api/issues/'+button.dataset.id+'/upvote',{{method:'POST'}});if(response.ok){{const data=await response.json();button.classList.add('supported');button.textContent='▲ Supported · '+data.supporters}}}});</script></body></html>'''
