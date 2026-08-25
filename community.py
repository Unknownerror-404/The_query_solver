"""Community view and shared civic-issue operations for the local map app."""

from __future__ import annotations

import html
import math
import threading

ISSUES = [
    {"id": 1, "title": "Pothole on Outer Ring Road", "category": "Roads", "area": "Bengaluru", "lat": 12.9352, "lng": 77.6245, "supporters": 28, "age": "5h ago", "description": "A deep pothole is slowing traffic near the service road."},
    {"id": 2, "title": "Garbage uncollected for four days", "category": "Waste", "area": "Indiranagar", "lat": 12.9784, "lng": 77.6408, "supporters": 18, "age": "4d ago", "description": "Household waste has accumulated beside the community park."},
    {"id": 3, "title": "Water cut, no notice", "category": "Water", "area": "Jayanagar", "lat": 12.9250, "lng": 77.5938, "supporters": 42, "age": "36h ago", "description": "The neighbourhood has had no supply since yesterday morning."},
    {"id": 4, "title": "Streetlight outage at junction", "category": "Streetlights", "area": "Koramangala", "lat": 12.9352, "lng": 77.6245, "supporters": 12, "age": "2d ago", "description": "Three streetlights are out, making the junction difficult to cross at night."},
]
ISSUE_LOCK = threading.Lock()


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
            return {"result": "duplicate", "issue": match.issue, "score": match.score}
    if match and match.decision == "possible_duplicate":
        return {"result": "possible_duplicate", "issue": match.issue, "score": match.score}
    with ISSUE_LOCK:
        issue["id"] = max((item["id"] for item in ISSUES), default=0) + 1
        issue["supporters"] = 1
        issue["age"] = "just now"
        ISSUES.append(issue)
        return {"result": "new", "issue": issue}


def upvote_issue(issue_id: int) -> bool:
    with ISSUE_LOCK:
        for issue in ISSUES:
            if issue["id"] == issue_id:
                issue["supporters"] += 1
                return True
    return False


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
    payload = json_page(user, location_label, cards)
    payload = payload.replace('<section class="intro">', '<section class="intro"><div class="actions"><button id="nearby">Near me</button><a class="nav-button" href="/">Map</a></div>')
    payload = payload.replace('</script></body></html>', "document.getElementById('nearby').onclick=()=>navigator.geolocation.getCurrentPosition(position=>{window.location='/community?lat='+position.coords.latitude+'&lng='+position.coords.longitude},()=>alert('Location access was unavailable.'));</script></body></html>")
    return payload


def json_page(user: str, location_label: str, cards: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Community · Civic Map</title><style>
:root{{--ink:#172b28;--muted:#667773;--paper:#f5f1e8;--accent:#e65f38;--line:#d9d7cd}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);background:var(--paper);font-family:Georgia,serif}}header{{padding:22px 28px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:end;gap:20px}}h1{{margin:0;font-size:clamp(2rem,5vw,3.6rem);font-weight:500}}.eyebrow,.meta{{color:var(--accent);font:700 11px Arial,sans-serif;letter-spacing:1.8px;text-transform:uppercase}}.tagline,a{{color:var(--muted);font:14px Arial,sans-serif}}main{{max-width:900px;margin:0 auto;padding:30px 24px}}.intro{{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--line);padding-bottom:18px;gap:20px}}.intro h2{{margin:6px 0 0;font-size:28px;font-weight:500}}.issues{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;margin-top:22px}}.issue{{padding:20px;background:#fffdf8;border:1px solid var(--line);transition:transform .18s ease,box-shadow .18s ease}}.issue:hover{{transform:translateY(-3px);box-shadow:6px 6px 0 var(--line)}}.issue h2{{font-size:20px;margin:8px 0}}.issue p{{color:var(--muted);line-height:1.45}}.issue-footer{{display:flex;justify-content:space-between;align-items:center;gap:10px;border-top:1px solid var(--line);padding-top:14px;font:12px Arial,sans-serif}}button{{cursor:pointer;border:1px solid var(--ink);background:transparent;padding:9px 10px;color:var(--ink)}}button:hover,.upvote.supported{{background:var(--ink);color:white}}.nav-button{{display:inline-block;padding:9px 12px;border:1px solid var(--ink);background:#fffdf8;color:var(--ink);text-decoration:none;font:700 12px Arial,sans-serif}}.nav-button:hover{{background:var(--ink);color:white}}.actions{{display:flex;align-items:center;gap:8px}}.back{{display:inline-block;margin-top:26px}}.empty{{color:var(--muted)}}@media(max-width:600px){{header,.intro{{align-items:start;flex-direction:column}}.issue-footer{{align-items:start;flex-direction:column}}}}
+</style></head><body><header><div><p class="eyebrow">Civic map · Community</p><h1>Local voices.</h1></div><div class="tagline">Signed in as {html.escape(user)} · <a href="/logout">Log out</a></div></header><main><section class="intro"><div><p class="eyebrow">Collective action</p><h2>What needs attention nearby?</h2><p>{html.escape(location_label)}</p></div><a href="/">Back to map</a></section><section class="issues">{cards}</section><a class="back" href="/">← Return to map</a></main><script>document.querySelectorAll('.upvote').forEach(button=>button.onclick=async()=>{{const response=await fetch('/api/issues/'+button.dataset.id+'/upvote',{{method:'POST'}});if(response.ok){{const data=await response.json();button.classList.add('supported');button.textContent='▲ Supported · '+data.supporters}}}});</script></body></html>'''
