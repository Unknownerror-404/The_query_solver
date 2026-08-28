"""A small civic-issues map inspired by Swaraj's public accountability map.
Run with ``python map.py`` and open http://localhost:8000 in a browser.
The map uses OpenStreetMap tiles through Leaflet, so an internet connection is needed for the basemap.
"""
from __future__ import annotations
import json
import secrets
import threading
import webbrowser
import base64
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
LOGIN_PAGE_FILE = BASE_DIR / "templates" / "login.html"
REGISTER_PAGE_FILE = BASE_DIR / "templates" / "register.html"
PROPOSALS_PAGE_FILE = BASE_DIR / "templates" / "proposals.html"
PROFESSIONALS_PAGE_FILE = BASE_DIR / "templates" / "professionals.html"
try:
    from .login_users import authenticate, create_account, professional_profile
    from .community import ISSUES, add_issue, nearby_issues, render_page, upvote_issue
    from .AI_model import inspect_image_proof
except ImportError:
    from login_users import authenticate, create_account, professional_profile
    from community import ISSUES, add_issue, nearby_issues, render_page, upvote_issue
    from AI_model import inspect_image_proof
HOST = "127.0.0.1"
PORT = 8000
SESSIONS: dict[str, str] = {}
PROPOSALS: list[dict] = load_proposals()
NEXT_PROPOSAL_ID = max((proposal["id"] for proposal in PROPOSALS), default=0) + 1
ADMIN_PAGE = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Admin moderation</title><style>body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#172b28}article{border:1px solid #d9d7cd;padding:18px;margin:14px 0}button{padding:9px 14px;margin-right:8px;cursor:pointer}textarea{width:100%;min-height:50px;margin:8px 0}</style></head><body><h1>Issue moderation</h1><p>Review pending community reports before institutional assignment.</p>__ISSUES__<script>document.querySelectorAll('form').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));data.status=event.submitter.value;const response=await fetch('/api/admin/issues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(response.ok)location.reload();else alert((await response.json()).message||'Moderation failed')})</script></body></html>"""
UNIVERSITY_PAGE = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>University collaboration</title><style>body{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#172b28}article{border:1px solid #d9d7cd;padding:18px;margin:14px 0}select,input,button{padding:9px 12px;margin:5px 5px 5px 0}input{min-width:220px}h2{margin-bottom:6px}</style></head><body><h1>University collaboration</h1><p>Approved civic issues can be assigned to an institution and a project team.</p>__ISSUES__<script>document.querySelectorAll('.assignment').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/assignments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Assignment failed')});document.querySelectorAll('.team').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));data.members=data.members.split(',').map(member=>member.trim()).filter(Boolean);const response=await fetch('/api/admin/teams',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(response.ok)location.reload();else alert((await response.json()).message||'Team creation failed')})</script></body></html>"""
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</script></body></html>", "document.querySelectorAll('.response').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/assignment-response',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Response failed')});</script></body></html>")
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</script></body></html>", "document.querySelectorAll('.university-profile').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/universities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Profile update failed')});</script></body></html>")
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</script></body></html>", "document.querySelector('.university-create').onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/universities/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});if(response.ok)location.reload();else alert((await response.json()).message||'Registration failed')};</script></body></html>")
UNIVERSITY_DASHBOARD = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>University dashboard</title><style>body{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#172b28}article{border:1px solid #d9d7cd;padding:18px;margin:14px 0}select,input,textarea,button{padding:9px;margin:4px 4px 4px 0}textarea{width:95%;min-height:70px}</style></head><body><h1>University dashboard</h1><p>Assigned challenges, university decisions, project teams, and proposed solutions.</p>__ASSIGNMENTS__<script>document.querySelectorAll('form').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));if(form.className==='team')data.members=data.members.split(',').map(member=>member.trim()).filter(Boolean);const response=await fetch(form.dataset.endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(response.ok)location.reload();else alert((await response.json()).message||'Request failed')})</script></body></html>"""
INDUSTRY_DASHBOARD = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Industry dashboard</title><style>body{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#172b28}article{border:1px solid #d9d7cd;padding:18px;margin:14px 0}select,input,textarea,button{padding:9px;margin:4px 4px 4px 0}textarea{width:95%;min-height:70px}</style></head><body><h1>Industry partnership dashboard</h1><p>Offer practical support to approved societal challenges.</p>__CONTENT__<script>document.querySelectorAll('form').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/industry/offers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Offer failed')})</script></body></html>"""
GOVERNMENT_DASHBOARD = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Government dashboard</title><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#172b28}section{border:1px solid #d9d7cd;padding:18px;margin:14px 0}li{margin:7px 0}</style></head><body>__CONTENT__</body></html>"""
def load_login_page(error=""):
    page = LOGIN_PAGE_FILE.read_text(encoding="utf-8")
    return page.replace("__ERROR__", error)
def load_university_login_page(error=""):
    page = UNIVERSITY_LOGIN_PAGE_FILE.read_text(encoding="utf-8")
    return page.replace("__ERROR__", error)
def load_register_page(error=""):
    page = REGISTER_PAGE_FILE.read_text(encoding="utf-8")
    return page.replace("__ERROR__", error)
def load_proposals_page():
    return PROPOSALS_PAGE_FILE.read_text(encoding="utf-8")
def load_professionals_page():
    return PROFESSIONALS_PAGE_FILE.read_text(encoding="utf-8")
SAMPLE_ISSUES = [
    {"title": "Pothole on Main Road", "category": "Roads", "area": "Morabadi, Ranchi", "lat": 23.3441, "lng": 85.3096, "supporters": 28, "age": "5h ago", "description": "A deep pothole is slowing traffic near the service road."},
    {"title": "Garbage uncollected for four days", "category": "Waste", "area": "Bank More, Dhanbad", "lat": 23.7957, "lng": 86.4304, "supporters": 18, "age": "4d ago", "description": "Household waste has accumulated beside the community park."},
    {"title": "Water cut, no notice", "category": "Water", "area": "Sakchi, Jamshedpur", "lat": 22.8046, "lng": 86.2029, "supporters": 42, "age": "36h ago", "description": "The neighbourhood has had no supply since yesterday morning."},
    {"title": "Streetlight outage at junction", "category": "Streetlights", "area": "Tower Chowk, Deoghar", "lat": 24.4857, "lng": 86.6947, "supporters": 12, "age": "2d ago", "description": "Three streetlights are out, making the junction difficult to cross at night."},
]
PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Civic Map</title><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><style>:root{--ink:#172b28;--muted:#667773;--paper:#f5f1e8;--card:#fffdf8;--accent:#e65f38;--line:#dedbd1;--blue:#317c91;--gold:#c48622}*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Georgia,serif;background:var(--paper);color:var(--ink)}header{padding:22px 28px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;background:var(--paper)}.brand{display:flex;align-items:center;gap:12px}.brand-mark{width:42px;height:42px;display:grid;place-items:center;border-radius:10px;background:var(--ink);color:white;font:700 17px Arial,sans-serif;box-shadow:0 6px 18px rgba(23,43,40,.16)}.brand-name{font:700 15px Arial,sans-serif;letter-spacing:.3px}.brand-sub{margin-top:2px;color:var(--accent);font:700 8px Arial,sans-serif;letter-spacing:1.5px;text-transform:uppercase}.eyebrow{margin:0 0 5px;color:var(--accent);font:700 11px Arial,sans-serif;letter-spacing:1.8px;text-transform:uppercase}.tagline{color:var(--muted);font:14px Arial,sans-serif}nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.nav-button{display:inline-block;padding:9px 12px;border:1px solid var(--ink);border-radius:8px;background:var(--card);color:var(--ink);text-decoration:none;font:700 12px Arial,sans-serif;transition:all .2s ease}.nav-button:hover,.nav-button.active{background:var(--ink);color:white}main{display:grid;grid-template-columns:320px 1fr;height:calc(100vh - 105px);min-height:540px}aside{padding:24px;overflow:auto;border-right:1px solid var(--line)}.stat{display:flex;justify-content:space-between;padding:14px 0;border-top:1px solid var(--line);font:13px Arial,sans-serif}.stat strong{font-size:21px}h2{font-size:18px;font-weight:500;margin:28px 0 12px}.filters{display:grid;gap:7px}button,select,input,textarea{font:14px Arial,sans-serif}button{cursor:pointer;border:1px solid var(--ink);background:transparent;padding:10px 12px;text-align:left;color:var(--ink);border-radius:8px}button:hover,button.active{background:var(--ink);color:white}.report{margin-top:28px;padding-top:20px;border-top:1px solid var(--line)}input,select,textarea{width:100%;margin:5px 0 9px;padding:10px;border:1px solid var(--line);border-radius:8px;background:#fffdf8;color:var(--ink)}textarea{resize:vertical;min-height:62px}.submit{width:100%;background:var(--accent);border-color:var(--accent);color:white;text-align:center;font-weight:bold}.submit:hover{background:#d44d27}#map{width:100%;height:100%;min-height:540px}.leaflet-popup-content-wrapper{border-radius:6px}.popup h3{margin:0 0 6px;font:700 17px Georgia,serif}.popup p{margin:5px 0;font:13px Arial,sans-serif;line-height:1.4}.popup .category{color:var(--accent);text-transform:uppercase;font-weight:bold;font-size:10px;letter-spacing:1px}.popup img{width:220px;max-height:150px;object-fit:cover;margin-top:8px;border-radius:6px}.proof{font:12px Arial,sans-serif;color:var(--muted)}@media(max-width:760px){header{align-items:start;flex-direction:column;gap:5px}main{display:block;height:auto}aside{border-right:0}#map{height:58vh;min-height:420px}}</style></head><body><header><div class="brand"><div class="brand-mark">C</div><div><div class="brand-name">Civic Map</div><div class="brand-sub">Live Civic Record</div></div></div><div class="tagline">Signed in as __USER__ · <a href="/logout" style="color:var(--muted)">Log out</a></div><nav class="nav"><a class="nav-button active" href="/">Live Map</a><a class="nav-button" href="/community">Community</a><a class="nav-button" href="/proposals">Solutions</a><a class="nav-button" href="/citizen-dashboard">My Dashboard</a><a class="nav-button" href="/university-dashboard">University</a><a class="nav-button" href="/industry-dashboard">Industry</a><a class="nav-button" href="/government-dashboard">Government</a></nav></header><main><aside><div class="stat"><span>Visible voices</span><strong id="count">0</strong></div><div class="stat"><span>People supporting</span><strong id="supporters">0</strong></div><h2>Browse issues</h2><div id="filters" class="filters"></div><button id="locate" style="margin-top:18px;width:100%;text-align:center">Use my location</button><form id="report" class="report"><h2>Drop a voice</h2><label>Issue title<input name="title" required placeholder="What needs attention?"></label><label>Category<select name="category"><option>Roads</option><option>Waste</option><option>Water</option><option>Streetlights</option><option>Footpaths</option><option>Other</option></select></label><label>Details<textarea name="description" placeholder="Add useful context"></textarea></label><label>Photo proof<input name="proof_image" type="file" accept="image/jpeg,image/png,image/webp"><small>Geotagged photos receive a location verification badge.</small></label><p style="font:12px Arial,sans-serif;color:var(--muted)">Click the map first to choose the location.</p><button class="submit" type="submit">Report this issue</button></form></aside><section id="map" aria-label="Map of civic issues"></section></main><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>const issues=__ISSUES__;const map=L.map('map').setView([12.9716,77.5946],12);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);const markers=L.layerGroup().addTo(map);let selectedCategory='All';let reportLocation=null;let selectedPin=null;const colors={Roads:'#e65f38',Waste:'#657a39',Water:'#317c91',Streetlights:'#c48622',Footpaths:'#785b86',Other:'#4f6560'};function popup(issue){return `<div class="popup"><div class="category">${issue.category} · ${issue.area}</div><h3>${issue.title}</h3><p>${issue.description||''}</p><p><b>${issue.supporters||0} supporters</b> · ${issue.age||'just now'}</p>${issue.proof_id?`<img src="/proof/${issue.proof_id}" alt="Photo proof"><p class="proof">${issue.proof_status==='verified'?'✓ GPS location verified':'Photo proof · location unverified'}</p>`:''}</div>`}function render(){markers.clearLayers();const visible=issues.filter(i=>selectedCategory==='All'||i.category===selectedCategory);visible.forEach(issue=>L.circleMarker([issue.lat,issue.lng],{radius:9,color:'#fff',weight:2,fillColor:colors[issue.category]||colors.Other,fillOpacity:.92}).bindPopup(popup(issue)).addTo(markers));document.getElementById('count').textContent=visible.length;document.getElementById('supporters').textContent=visible.reduce((sum,i)=>sum+(i.supporters||0),0)}function buildFilters(){const categories=['All',...new Set(issues.map(i=>i.category))];const root=document.getElementById('filters');root.replaceChildren();categories.forEach(category=>{const button=document.createElement('button');button.textContent=category;button.className=category==='All'?'active':'';button.onclick=()=>{selectedCategory=category;root.querySelectorAll('button').forEach(b=>b.classList.remove('active'));button.classList.add('active');render()};root.appendChild(button)})}function updatePinLabel(){if(reportLocation)document.querySelector('#report p').textContent=`Pin selected: ${reportLocation.lat.toFixed(5)}, ${reportLocation.lng.toFixed(5)}`}function setReportLocation(latlng){reportLocation=latlng;if(selectedPin)map.removeLayer(selectedPin);selectedPin=L.marker(latlng,{draggable:true}).addTo(map);selectedPin.on('dragend',event=>{reportLocation=event.target.getLatLng();updatePinLabel()});updatePinLabel()}map.on('click',e=>setReportLocation(e.latlng));document.getElementById('locate').onclick=()=>{map.once('locationfound',event=>setReportLocation(event.latlng));map.once('locationerror',()=>alert('Location access was unavailable. Please allow location access or click the map to place a pin.')).locate({setView:true,maxZoom:15})};document.getElementById('report').onsubmit=async event=>{event.preventDefault();if(!reportLocation)return alert('Click the map to choose a location first.');const form=new FormData(event.target);const proofFile=form.get('proof_image');let proofImage='';if(proofFile&&proofFile.size){const bytes=new Uint8Array(await proofFile.arrayBuffer());let binary='';bytes.forEach(byte=>binary+=String.fromCharCode(byte));proofImage=btoa(binary)}const response=await fetch('/api/issues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:form.get('title'),category:form.get('category'),description:form.get('description'),area:'New report',lat:reportLocation.lat,lng:reportLocation.lng,proof_image:proofImage,proof_type:proofFile&&proofFile.type||'image/jpeg'})});const result=await response.json();if(result.result==='possible_duplicate'){alert('A similar issue is already reported nearby. Please support the existing issue from the community page.');return}if(!response.ok)return alert(result.message||'The issue could not be submitted.');if(result.result==='duplicate'){alert('This matches an existing issue and was added as support.');return}issues.push(result.issue);buildFilters();render();event.target.reset();reportLocation=null;if(selectedPin){map.removeLayer(selectedPin);selectedPin=null}alert('Your issue was added to the map.')};buildFilters();render();const districtCoords={"Bokaro":[23.6693,85.9563],"Chatra":[24.2120,84.8715],"Deoghar":[24.4826,86.6966],"Dhanbad":[23.7957,86.4304],"Dumka":[24.2676,87.2497],"East Singhbhum":[22.8046,86.2029],"Garhwa":[24.1624,83.8073],"Giridih":[24.1868,86.3050],"Godda":[24.8267,87.2132],"Gumla":[23.0448,84.5422],"Hazaribagh":[23.9925,85.3637],"Jamtara":[23.9629,86.8000],"Khunti":[23.0763,85.2787],"Koderma":[24.4678,85.5938],"Latehar":[23.7454,84.4632],"Lohardaga":[23.4377,84.6806],"Pakur":[24.6341,87.8488],"Palamu":[24.0326,84.0722],"Ramgarh":[23.6288,85.5173],"Ranchi":[23.3441,85.3096],"Sahibganj":[25.2425,87.6419],"Seraikela Kharsawan":[22.7001,85.9298],"Simdega":[22.6148,84.5074],"West Singhbhum":[22.5694,85.8115]};document.addEventListener('change',e=>{if(e.target&&e.target.name==='district'){const c=districtCoords[e.target.value];if(c)map.flyTo(c,11,{duration:1.5})}});</script></body></html>"""
district_options = "".join(f"<option>{html.escape(district)}</option>" for district in JHARKHAND_DISTRICTS)
domain_options = "".join(f"<option>{html.escape(domain)}</option>" for domain in JHARKHAND_DOMAINS)
PAGE = PAGE.replace("setView([12.9716,77.5946],12)", "setView([23.3441,85.3096],7)")
PAGE = PAGE.replace(
    "<option>Roads</option><option>Waste</option><option>Water</option><option>Streetlights</option><option>Footpaths</option><option>Other</option>",
    domain_options,
).replace(
    "<label>Details<textarea name=\"description\" placeholder=\"Add useful context\"></textarea></label>",
    "<label>District<select name=\"district\">" + district_options + "</select></label><label>Block or city<input name=\"block\" placeholder=\"Block, municipality, or ward\"></label><label>Details<textarea name=\"description\" placeholder=\"Add useful context\"></textarea></label>",
).replace(
    "description:form.get('description'),area:'New report',lat:reportLocation.lat,lng:reportLocation.lng,proof_image:proofImage",
    "description:form.get('description'),area:form.get('block')||form.get('district'),district:form.get('district'),block:form.get('block'),lat:reportLocation.lat,lng:reportLocation.lng,proof_image:proofImage",
)
MAP_PAGE = PAGE
def proposal_issue(issue_id: int):
    for issue in ISSUES:
        if issue.get("id") == issue_id:
            return issue
    return None
def render_proposal_issues():
    if not ISSUES:
        return '<p class="muted">No civic issues are available yet.</p>'
    ranked = sorted(ISSUES,key=lambda issue: issue.get("supporters",0),reverse=True)
    output = []
    for index, issue in enumerate(ranked, start=1):
        issue_id = issue.get("id", index)
        output.append(f'<article class="issue"><div class="rank">#{index} · {html.escape(str(issue.get("category","Other")))}</div><h2>{html.escape(str(issue.get("title","Untitled issue")))}</h2><p>{html.escape(str(issue.get("description","")))}</p><p><strong>{issue.get("supporters",0)} supporters</strong> · {html.escape(str(issue.get("area","Nearby")))}</p><small>Issue ID: {issue_id}</small></article>')
    return "".join(output)
def render_proposal_options():
    if not ISSUES:
        return '<option value="">No issues available</option>'
    ranked = sorted(ISSUES,key=lambda issue: issue.get("supporters",0),reverse=True)
    options = []
    for index, issue in enumerate(ranked, start=1):
        issue_id = issue.get("id", index)
        options.append(f'<option value="{issue_id}">{html.escape(str(issue.get("title","Untitled issue")))} · {issue.get("supporters",0)} supporters</option>')
    return "".join(options)
def render_proposals():
    if not PROPOSALS:
        return '<p class="empty">No proposals have been submitted yet. Be the first to propose a practical solution.</p>'
    output = []
    for proposal in sorted(PROPOSALS,key=lambda item: item.get("votes",0),reverse=True):
        issue = proposal_issue(proposal["issue_id"])
        issue_title = issue.get("title","Unknown issue") if issue else "Unknown issue"
        output.append(f'<article class="proposal"><p class="eyebrow">Proposal #{proposal["id"]}</p><h2>{html.escape(proposal["title"])}</h2><p>{html.escape(proposal["description"])}</p><p><strong>Problem:</strong> {html.escape(str(issue_title))}</p><p><b>{proposal.get("votes",0)} solution votes</b></p><span class="status">{html.escape(proposal.get("status","Submitted"))}</span><br><button class="solution-vote" data-id="{proposal["id"]}" type="button">Vote for this solution</button></article>')
    return "".join(output)
def render_professional_proposals():
    if not PROPOSALS:
        return '<p class="empty">No community proposals are available for review yet.</p>'
    output = []
    for proposal in sorted(PROPOSALS,key=lambda item: item.get("votes",0),reverse=True):
        issue = proposal_issue(proposal["issue_id"])
        issue_title = issue.get("title","Unknown issue") if issue else "Unknown issue"
        review = proposal.get("review")
        if review:
            review_html = f'<div class="review-note"><strong>{html.escape(review["decision"])}</strong><p>{html.escape(review["explanation"])}</p><small>Reviewed by {html.escape(review["reviewer"])}</small></div>'
        else:
            review_html = f'<form class="review-form"><input type="hidden" name="proposal_id" value="{proposal["id"]}"><label>Decision<select name="decision" required><option value="Under review">Under review</option><option value="Feasible">Feasible</option><option value="Needs revision">Needs revision</option><option value="Not feasible">Not feasible</option></select></label><label>Explanation<textarea name="explanation" required placeholder="Explain the feasibility, evidence needed, or changes required."></textarea></label><button type="submit">Save review</button></form>'
        output.append(f'<article class="proposal"><p class="eyebrow">Community proposal</p><h2>{html.escape(proposal["title"])}</h2><p>{html.escape(proposal["description"])}</p><p><strong>Related issue:</strong> {html.escape(str(issue_title))}</p><p class="votes">{proposal.get("votes",0)} solution votes</p><span class="status">{html.escape(proposal.get("status","Submitted"))}</span><div class="review">{review_html}</div></article>')
    return "".join(output)
def build_proposals_page(user):
    page = load_proposals_page()
    page = page.replace("__USER__",html.escape(user))
    page = page.replace("__ISSUES__",render_proposal_issues())
    page = page.replace("__OPTIONS__",render_proposal_options())
    page = page.replace("__PROPOSALS__",render_proposals())
    page = page.replace("__MESSAGE__","")
    return page
def build_professionals_page(user):
    page = load_professionals_page()
    profile = professional_profile(user)
    if profile:
        affiliation = profile.get("affiliation","Verified professional")
        organization = profile.get("organization","Organization")
    else:
        affiliation = "Community reviewer"
        organization = "Civic Map"
    reviewed = sum(1 for proposal in PROPOSALS if proposal.get("review"))
    total = len(PROPOSALS)
    page_count = max(1,(total+4)//5)
    page = page.replace("__USER__",html.escape(user))
    page = page.replace("__AFFILIATION__",html.escape(affiliation))
    page = page.replace("__ORGANIZATION__",html.escape(organization))
    page = page.replace("__ORG_SHORT__",html.escape(organization[:25]))
    page = page.replace("__PAGE__","1")
    page = page.replace("__PAGE_COUNT__",str(page_count))
    page = page.replace("__TOTAL__",str(total))
    page = page.replace("__REVIEWED__",str(reviewed))
    page = page.replace("__PREV__","1")
    page = page.replace("__NEXT__","2")
    page = page.replace("__PREV_DISABLED__","disabled")
    page = page.replace("__NEXT_DISABLED__","disabled" if page_count <= 1 else "")
    page = page.replace("__PROPOSALS__",render_professional_proposals())
    return page
class MapHandler(BaseHTTPRequestHandler):
    def session_user(self) -> str | None:
        cookie = self.headers.get("Cookie","")
        for part in cookie.split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name == "session_id":
                user = get_session_user(value)
                if user:
                    return user
                return SESSIONS.get(value)
        return None
    def redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(303)
        self.send_header("Location",location)
        if cookie:
            self.send_header("Set-Cookie",cookie)
        self.end_headers()
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/login":
            self.send_html(load_login_page(""))
            return
        if path == "/university/login" or path == "/university-login":
            self.send_html(load_university_login_page(""))
            return
        if path == "/register":
            self.send_html(load_register_page(""))
            return
        if path == "/logout":
            cookie = self.headers.get("Cookie","")
            for part in cookie.split(";"):
                name, separator, value = part.strip().partition("=")
                if separator and name == "session_id":
                    delete_session_record(value)
                    SESSIONS.pop(value,None)
            self.redirect("/login","session_id=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax")
            return
        if path.startswith("/proof/"):
            proof_id = path.split("/",2)[2]
            proof = get_proof(proof_id)
            if proof is None:
                self.send_error(404)
                return
            self.send_payload(proof[1],content_type=proof[0])
            return
        if path.startswith("/proposal-visual/"):
            try:
                proposal_id = int(path.split("/", 2)[2])
            except (IndexError, ValueError):
                self.send_error(404)
                return
            visual = get_proposal_visual(proposal_id)
            if visual is None:
                self.send_error(404)
                return
            self.send_payload(visual[1], content_type=visual[0])
            return
        if path == "/community":
            if self.session_user() is None:
                self.redirect("/login")
                return
            query = parse_qs(urlsplit(self.path).query)
            try:
                latitude = float(query["lat"][0])
                longitude = float(query["lng"][0])
            except (KeyError,ValueError):
                latitude = longitude = None
            self.send_html(render_page(self.session_user() or "",latitude,longitude))
            return
        if path == "/proposals":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            self.send_html(build_proposals_page(user))
            return
        if path == "/professionals":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            self.send_html(build_professionals_page(user))
            return
        if path == "/admin":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not is_admin(user):
                self.send_error(403)
                return
            self.send_html(ADMIN_PAGE.replace("__ISSUES__", render_admin_issues()))
            return
        if path == "/industry-admin":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            self.send_html(f"<!doctype html><html><body>{render_industry_admin()}<script>document.querySelector('.industry-create').onsubmit=async event=>{{event.preventDefault();const response=await fetch('/api/admin/industry-partners',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))}});if(response.ok)location.reload();else alert((await response.json()).message||'Registration failed')}};document.querySelectorAll('.offer-update').forEach(form=>form.onsubmit=async event=>{{event.preventDefault();const response=await fetch('/api/admin/offer-commitments',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(Object.fromEntries(new FormData(form)))}});if(response.ok)location.reload();else alert((await response.json()).message||'Commitment update failed')}})</script></body></html>")
            return
        if path == "/universities":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not is_admin(user):
                self.send_error(403)
                return
            self.send_html(UNIVERSITY_PAGE.replace("__ISSUES__", render_university_issues()))
            return
        if path == "/citizen-dashboard" or path == "/my-issues":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            template = CITIZEN_PAGE_FILE.read_text(encoding="utf-8")
            self.send_html(template.replace("__USER__", html.escape(user)).replace("__ISSUES__", render_user_issues(user)))
            return
        if path == "/university-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if university_for_user(user) is None:
                self.send_error(403)
                return
            template = UNIVERSITY_DASHBOARD_FILE.read_text(encoding="utf-8")
            self.send_html(template.replace("__ASSIGNMENTS__", render_university_dashboard(user)))
            return
        if path == "/industry-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if industry_for_user(user) is None:
                self.send_error(403)
                return
            template = INDUSTRY_DASHBOARD_FILE.read_text(encoding="utf-8")
            self.send_html(template.replace("__CONTENT__", render_industry_dashboard(user)))
            return
        if path == "/government-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not is_admin(user):
                self.send_error(403)
                return
            template = GOVERNMENT_DASHBOARD_FILE.read_text(encoding="utf-8")
            self.send_html(template.replace("__CONTENT__", render_government_dashboard()))
            return
        if path not in ("/","/index.html"):
            self.send_error(404)
            return
        user = self.session_user()
        if user is None:
            self.redirect("/login")
            return
        issues_json = json.dumps(ISSUES).replace("</", "<\\/")
        payload = MAP_PAGE.replace("__ISSUES__", issues_json).replace("__USER__", html.escape(user)).encode("utf-8")
        self.send_payload(payload)
    def do_POST(self) -> None:
        global NEXT_PROPOSAL_ID
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        if not check_rate_limit(client_ip, max_requests=60, window_seconds=60):
            self.send_json({"message": "Rate limit exceeded. Please wait a minute."}, status=429)
            return
        path = urlsplit(self.path).path
        if path == "/api/issues" or path == "/api/issues/" or (path.startswith("/api/issues/") and path.endswith("/upvote")):
            if self.session_user() is None:
                self.send_error(401)
                return
            if path.endswith("/upvote"):
                try:
                    issue_id = int(path.split("/")[3])
                except (IndexError,ValueError):
                    self.send_error(400)
                    return
                supported, supporters = upvote_issue(issue_id, self.session_user() or "")
                if not supported:
                    self.send_error(404)
                    return
                self.send_json({"supporters": supporters})
                return
            length = int(self.headers.get("Content-Length","0"))
            try:
                issue = json.loads(self.rfile.read(length).decode("utf-8"))
                issue["lat"] = float(issue["lat"])
                issue["lng"] = float(issue["lng"])
                issue["district"] = str(issue.get("district", "Ranchi")).strip() or "Ranchi"
                issue["block"] = str(issue.get("block", "")).strip()
                issue["reporter"] = self.session_user() or ""
                encoded_proof = issue.pop("proof_image","")
                proof_type = issue.pop("proof_type","image/jpeg")
                if proof_type not in {"image/jpeg","image/png","image/webp"}:
                    self.send_error(415,"Unsupported proof image type")
                    return
                proof_bytes = base64.b64decode(encoded_proof,validate=True) if encoded_proof else b""
                if len(proof_bytes) > 8 * 1024 * 1024:
                    self.send_error(413,"Proof image is larger than 8 MB")
                    return
                if proof_bytes:
                    proof_bytes, proof_type = sanitize_and_reencode_image(proof_bytes, proof_type)
                    proof = inspect_image_proof(proof_bytes,issue["lat"],issue["lng"])
                    if proof["status"] == "mismatch":
                        self.send_json(proof,status=422)
                        return
                    issue.update({"proof_status":proof["status"],"proof_message":proof["message"]})
                    proof_id = secrets.token_urlsafe(12)
                    issue["proof_id"] = proof_id
                    issue["_proof_type"] = proof_type
                    issue["_proof_data"] = proof_bytes
                else:
                    proof_id = ""
                created = add_issue(issue)
            except (ValueError,KeyError,json.JSONDecodeError):
                self.send_error(400)
                return
            if proof_bytes and created.get("issue") and created["result"] != "possible_duplicate":
                created["issue"]["proof_id"] = proof_id
            self.send_json(created,status=201 if created["result"] == "new" else 200)
            return
        if path == "/api/proposals":
            user = self.session_user()
            if user is None:
                self.send_json({"message":"You must be signed in."},status=401)
                return
            length = int(self.headers.get("Content-Length","0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data.get("issue_id"))
                title = str(data.get("title","")).strip()
                description = str(data.get("description","")).strip()
                visual = data.get("visual","")
                visual_type = data.get("visual_type","")
            except (ValueError,TypeError,json.JSONDecodeError):
                self.send_json({"message":"Invalid proposal data."},status=400)
                return
            if not title:
                self.send_json({"message":"Proposal title is required."},status=400)
                return
            if not description:
                self.send_json({"message":"Proposal description is required."},status=400)
                return
            issue = proposal_issue(issue_id)
            if issue is None:
                self.send_json({"message":"The selected issue was not found."},status=404)
                return
            try:
                visual_data = base64.b64decode(visual, validate=True) if visual else b""
            except (ValueError, base64.binascii.Error):
                self.send_json({"message":"Invalid proposal visual."},status=400)
                return
            if len(visual_data) > 8 * 1024 * 1024:
                self.send_json({"message":"Proposal visual is larger than 8 MB."},status=413)
                return
            proposal = {"issue_id":issue_id,"title":title[:120],"description":description[:3000],"author":user,"visual":"","visual_type":visual_type,"_visual_data":visual_data}
            proposal = insert_proposal(proposal)
            PROPOSALS.append(proposal)
            self.send_json({"message":"Proposal published.","proposal":proposal},status=201)
            return
        if path.startswith("/api/proposals/") and path.endswith("/vote"):
            if self.session_user() is None:
                self.send_json({"message":"You must be signed in."},status=401)
                return
            try:
                proposal_id = int(path.split("/")[3])
            except (IndexError,ValueError):
                self.send_json({"message":"Invalid proposal ID."},status=400)
                return
            proposal = next((item for item in PROPOSALS if item["id"] == proposal_id),None)
            if proposal is None:
                self.send_json({"message":"Proposal not found."},status=404)
                return
            proposal["votes"] += 1
            update_proposal(proposal)
            self.send_json({"votes":proposal["votes"],"result":"voted"})
            return
        if path.startswith("/api/proposals/") and path.endswith("/review"):
            user = self.session_user()
            if user is None:
                self.send_json({"message":"You must be signed in."},status=401)
                return
            profile = professional_profile(user)
            if profile is None:
                self.send_json({"message":"Only verified professionals can submit reviews."},status=403)
                return
            try:
                proposal_id = int(path.split("/")[3])
            except (IndexError,ValueError):
                self.send_json({"message":"Invalid proposal ID."},status=400)
                return
            proposal = next((item for item in PROPOSALS if item["id"] == proposal_id),None)
            if proposal is None:
                self.send_json({"message":"Proposal not found."},status=404)
                return
            length = int(self.headers.get("Content-Length","0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                decision = str(data.get("decision","")).strip()
                explanation = str(data.get("explanation","")).strip()
            except (ValueError,TypeError,json.JSONDecodeError):
                self.send_json({"message":"Invalid review data."},status=400)
                return
            result, proposal = review_issue_evidence(PROPOSALS, proposal_id, profile.get("name",user), decision, explanation)
            if result == "invalid":
                self.send_json({"message":"Choose a valid decision and provide an explanation."},status=400)
                return
            update_proposal(proposal)
            self.send_json({"message":"Review saved.","result":"reviewed"})
            return
        if path.startswith("/api/issues/") and path.endswith("/evidence-review"):
            user = self.session_user()
            if user is None:
                self.send_json({"message":"You must be signed in."},status=401)
                return
            profile = professional_profile(user)
            if profile is None:
                self.send_json({"message":"Only verified professionals can review evidence."},status=403)
                return
            try:
                issue_id = int(path.split("/")[3])
            except (IndexError,ValueError):
                self.send_json({"message":"Invalid issue ID."},status=400)
                return
            length = int(self.headers.get("Content-Length","0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                decision = str(data.get("decision","")).strip()
                explanation = str(data.get("explanation","")).strip()
            except (ValueError,TypeError,json.JSONDecodeError):
                self.send_json({"message":"Invalid evidence review data."},status=400)
                return
            result, issue = review_issue_evidence(ISSUES, issue_id, profile.get("name",user), decision, explanation)
            if result == "invalid":
                self.send_json({"message":"Choose a valid evidence decision and provide an explanation."},status=400)
                return
            if result == "missing":
                self.send_json({"message":"Issue not found."},status=404)
                return
            self.send_json({"message":"Evidence review saved.","result":result,"issue":issue})
            return
        if path not in ("/login","/register"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length","0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        email = form.get("email",[""])[0].strip().lower()
        password = form.get("password",[""])[0]
        if path == "/register":
            if password != form.get("confirm_password",[""])[0]:
                self.send_html(load_register_page('<p class="error">Passwords do not match.</p>'),status=400)
                return
            created,message = create_account(email,password)
            if not created:
                self.send_html(load_register_page(f'<p class="error">{html.escape(message)}</p>'),status=400)
                return
            self.redirect("/login")
            return
        if not authenticate(email,password):
            self.send_html(load_login_page('<p class="error">Email or password is incorrect.</p>'),status=401)
            return
        session_id = secrets.token_urlsafe(32)
        SESSIONS[session_id] = email
        self.redirect("/",f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
    def send_html(self,page,status=200):
        self.send_payload(page.encode("utf-8"),status)
    def send_json(self,data,status=200):
        self.send_payload(json.dumps(data).encode("utf-8"),status,"application/json")
    def send_payload(self,payload,status=200,content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self,format,*args):
        return
if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST,PORT),MapHandler)
    threading.Timer(0.5,lambda:webbrowser.open(f"http://{HOST}:{PORT}")).start()
    print(f"Civic map running at http://{HOST}:{PORT} (press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMap stopped.")
    finally:
        server.server_close()
