"""A small civic-issues map inspired by Swaraj's public accountability map.

Run with ``python map.py`` and open http://localhost:8000 in a browser.
The map uses OpenStreetMap tiles through Leaflet, so an internet connection is
needed for the basemap. Replace SAMPLE_ISSUES with records from your database
or API when connecting it to the rest of the project.
"""

from __future__ import annotations

import json
import secrets
import threading
import webbrowser
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGIN_PAGE_FILE = BASE_DIR / "templates" / "login.html"

try:
	from .login_users import authenticate, create_account
	from .community import ISSUES, add_issue, nearby_issues, render_page, upvote_issue
	from .AI_model import inspect_image_proof
except ImportError:
	from login_users import authenticate, create_account
	from community import ISSUES, add_issue, nearby_issues, render_page, upvote_issue
from AI_model import inspect_image_proof

HOST = "127.0.0.1"
PORT = 8000
SESSIONS: dict[str, str] = {}
PROOF_IMAGES: dict[str, tuple[str, bytes]] = {}


def load_login_page(error=""):
    page = LOGIN_PAGE_FILE.read_text(encoding="utf-8")
    return page.replace("__ERROR__", error)

SAMPLE_ISSUES = [
	{"title": "Pothole on Outer Ring Road", "category": "Roads", "area": "Bengaluru", "lat": 12.9352, "lng": 77.6245, "supporters": 28, "age": "5h ago", "description": "A deep pothole is slowing traffic near the service road."},
	{"title": "Garbage uncollected for four days", "category": "Waste", "area": "Indiranagar", "lat": 12.9784, "lng": 77.6408, "supporters": 18, "age": "4d ago", "description": "Household waste has accumulated beside the community park."},
	{"title": "Water cut, no notice", "category": "Water", "area": "Jayanagar", "lat": 12.9250, "lng": 77.5938, "supporters": 42, "age": "36h ago", "description": "The neighbourhood has had no supply since yesterday morning."},
	{"title": "Streetlight outage at junction", "category": "Streetlights", "area": "Koramangala", "lat": 12.9352, "lng": 77.6245, "supporters": 12, "age": "2d ago", "description": "Three streetlights are out, making the junction difficult to cross at night."},
]

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Civic Map</title><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><style>
:root{--ink:#172b28;--muted:#667773;--paper:#f5f1e8;--accent:#e65f38;--line:#d9d7cd}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--paper);font-family:Georgia,serif}header{padding:22px 28px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:end;gap:20px}h1{margin:0;font-size:clamp(2rem,5vw,3.6rem);letter-spacing:-1px;font-weight:500}.eyebrow{margin:0 0 5px;color:var(--accent);font:700 11px Arial,sans-serif;letter-spacing:1.8px;text-transform:uppercase}.tagline{color:var(--muted);font:14px Arial,sans-serif}main{display:grid;grid-template-columns:320px 1fr;height:calc(100vh - 105px);min-height:540px}aside{padding:24px;overflow:auto;border-right:1px solid var(--line)}.stat{display:flex;justify-content:space-between;padding:14px 0;border-top:1px solid var(--line);font:13px Arial,sans-serif}.stat strong{font-size:21px}h2{font-size:18px;font-weight:500;margin:28px 0 12px}.filters{display:grid;gap:7px}button,select,input,textarea{font:14px Arial,sans-serif}button{cursor:pointer;border:1px solid var(--ink);background:transparent;padding:10px 12px;text-align:left;color:var(--ink)}button:hover,button.active{background:var(--ink);color:white}.report{margin-top:28px;padding-top:20px;border-top:1px solid var(--line)}input,select,textarea{width:100%;margin:5px 0 9px;padding:10px;border:1px solid var(--line);background:#fffdf8;color:var(--ink)}textarea{resize:vertical;min-height:62px}.submit{width:100%;background:var(--accent);border-color:var(--accent);color:white;text-align:center;font-weight:bold}#map{width:100%;height:100%;min-height:540px}.leaflet-popup-content-wrapper{border-radius:2px}.popup h3{margin:0 0 6px;font:700 17px Georgia,serif}.popup p{margin:5px 0;font:13px Arial,sans-serif;line-height:1.4}.popup .category{color:var(--accent);text-transform:uppercase;font-weight:bold;font-size:10px;letter-spacing:1px}@media(max-width:760px){header{align-items:start;flex-direction:column;gap:5px}main{display:block;height:auto}aside{border-right:0}#map{height:58vh;min-height:420px}}
</style></head><body><header><div><p class="eyebrow">Live civic record</p><h1>City, on record.</h1></div><div class="tagline">Signed in as __USER__ · <a href="/logout">Log out</a><br>See it. Pin it. Report it.</div></header><main><aside><div class="stat"><span>Visible voices</span><strong id="count">0</strong></div><div class="stat"><span>People supporting</span><strong id="supporters">0</strong></div><h2>Browse issues</h2><div id="filters" class="filters"></div><button id="locate" style="margin-top:18px;width:100%;text-align:center">Use my location</button><form id="report" class="report"><h2>Drop a voice</h2><label>Issue title<input name="title" required placeholder="What needs attention?"></label><label>Category<select name="category"><option>Roads</option><option>Waste</option><option>Water</option><option>Streetlights</option><option>Footpaths</option><option>Other</option></select></label><label>Details<textarea name="description" placeholder="Add useful context"></textarea></label><p style="font:12px Arial,sans-serif;color:var(--muted)">Click the map first to choose the location.</p><button class="submit" type="submit">Report this issue</button></form></aside><section id="map" aria-label="Map of civic issues"></section></main><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
const issues=__ISSUES__;const map=L.map('map').setView([12.9716,77.5946],12);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);const markers=L.layerGroup().addTo(map);let selectedCategory='All';let reportLocation=null;const colors={Roads:'#e65f38',Waste:'#657a39',Water:'#317c91',Streetlights:'#c48622',Footpaths:'#785b86',Other:'#4f6560'};function popup(issue){return `<div class="popup"><div class="category">${issue.category} · ${issue.area}</div><h3>${issue.title}</h3><p>${issue.description||''}</p><p><b>${issue.supporters||0} supporters</b> · ${issue.age||'just now'}</p></div>`}function render(){markers.clearLayers();const visible=issues.filter(i=>selectedCategory==='All'||i.category===selectedCategory);visible.forEach(issue=>L.circleMarker([issue.lat,issue.lng],{radius:9,color:'#fff',weight:2,fillColor:colors[issue.category]||colors.Other,fillOpacity:.92}).bindPopup(popup(issue)).addTo(markers));document.getElementById('count').textContent=visible.length;document.getElementById('supporters').textContent=visible.reduce((sum,i)=>sum+(i.supporters||0),0)}function buildFilters(){const categories=['All',...new Set(issues.map(i=>i.category))];const root=document.getElementById('filters');root.replaceChildren();categories.forEach(category=>{const button=document.createElement('button');button.textContent=category;button.className=category==='All'?'active':'';button.onclick=()=>{selectedCategory=category;root.querySelectorAll('button').forEach(b=>b.classList.remove('active'));button.classList.add('active');render()};root.appendChild(button)})}map.on('click',e=>{reportLocation=e.latlng;document.querySelector('#report p').textContent=`Pin selected: ${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`});document.getElementById('locate').onclick=()=>map.locate({setView:true,maxZoom:15});document.getElementById('report').onsubmit=event=>{event.preventDefault();if(!reportLocation)return alert('Click the map to choose a location first.');const form=new FormData(event.target);issues.push({title:form.get('title'),category:form.get('category'),description:form.get('description'),area:'New report',lat:reportLocation.lat,lng:reportLocation.lng,supporters:1,age:'just now'});buildFilters();render();event.target.reset();reportLocation=null;alert('Your issue was added to the map.')};buildFilters();render();</script></body></html>"""


MAP_PAGE = (PAGE
	.replace('<label>Details<textarea name="description" placeholder="Add useful context"></textarea></label>', '<label>Details<textarea name="description" placeholder="Add useful context"></textarea></label><label>Photo proof<input name="proof_image" type="file" accept="image/jpeg,image/png,image/webp"><small>Geotagged photos receive a location verification badge.</small></label>')
	.replace('.popup .category{color:var(--accent);text-transform:uppercase;font-weight:bold;font-size:10px;letter-spacing:1px}', '.popup .category{color:var(--accent);text-transform:uppercase;font-weight:bold;font-size:10px;letter-spacing:1px}.popup img{width:220px;max-height:150px;object-fit:cover;margin-top:8px}.proof{font:12px Arial,sans-serif;color:var(--muted)}')
	.replace("<p><b>${issue.supporters||0} supporters</b> · ${issue.age||'just now'}</p>", "<p><b>${issue.supporters||0} supporters</b> · ${issue.age||'just now'}</p>${issue.proof_id?`<img src='/proof/${issue.proof_id}' alt='Photo proof'><p class='proof'>${issue.proof_status==='verified'?'✓ GPS location verified': 'Photo proof · location unverified'}</p>`:''}")
	.replace(".tagline{color:var(--muted);font:14px Arial,sans-serif}", ".tagline{color:var(--muted);font:14px Arial,sans-serif}.nav-button{display:inline-block;margin:0 0 7px 8px;padding:9px 12px;border:1px solid var(--ink);color:var(--ink);background:#fffdf8;text-decoration:none;font:700 12px Arial,sans-serif}.nav-button:hover{background:var(--ink);color:white}")
	.replace("<h2>Browse issues</h2>", "<a class=\"nav-button community-link\" href=\"/community\">Open community</a><h2>Browse issues</h2>")
	.replace("let selectedCategory='All';let reportLocation=null;", "let selectedCategory='All';let reportLocation=null;let selectedPin=null;function setReportLocation(latlng){reportLocation=latlng;if(selectedPin)map.removeLayer(selectedPin);selectedPin=L.marker(latlng,{draggable:true}).addTo(map);selectedPin.on('dragend',event=>{reportLocation=event.target.getLatLng();updatePinLabel()});updatePinLabel()}function updatePinLabel(){document.querySelector('#report p').textContent=`Pin selected: ${reportLocation.lat.toFixed(5)}, ${reportLocation.lng.toFixed(5)}`}")
	.replace("map.on('click',e=>{reportLocation=e.latlng;document.querySelector('#report p').textContent=`Pin selected: ${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`});", "map.on('click',e=>setReportLocation(e.latlng));")
	.replace("document.getElementById('locate').onclick=()=>map.locate({setView:true,maxZoom:15});", "document.getElementById('locate').onclick=()=>map.once('locationfound',event=>{setReportLocation(event.latlng);}).once('locationerror',()=>alert('Location access was unavailable. Please allow location access or click the map to place a pin.')).locate({setView:true,maxZoom:15});")
	.replace("<br>See it. Pin it. Report it.", "<br><a class=\"nav-button\" href=\"/community\">Community</a> See it. Pin it. Report it.")
	.replace('Signed in as __USER__ · <a href="/logout">Log out</a>', 'Signed in as __USER__ · <a href="/community">Community</a> · <a href="/logout">Log out</a>')
	.replace("document.getElementById('report').onsubmit=event=>", "document.getElementById('report').onsubmit=async event=>")
	.replace("const form=new FormData(event.target);issues.push({title:form.get('title'),category:form.get('category'),description:form.get('description'),area:'New report',lat:reportLocation.lat,lng:reportLocation.lng,supporters:1,age:'just now'});buildFilters();render();event.target.reset();reportLocation=null;alert('Your issue was added to the map.')", "const form=new FormData(event.target);const proofFile=form.get('proof_image');let proofImage='';if(proofFile&&proofFile.size){const bytes=new Uint8Array(await proofFile.arrayBuffer());let binary='';bytes.forEach(byte=>binary+=String.fromCharCode(byte));proofImage=btoa(binary)}const response=await fetch('/api/issues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:form.get('title'),category:form.get('category'),description:form.get('description'),area:'New report',lat:reportLocation.lat,lng:reportLocation.lng,proof_image:proofImage,proof_type:proofFile&&proofFile.type||'image/jpeg'})});const result=await response.json();if(result.result==='possible_duplicate'){alert('A similar issue is already reported nearby. Please support the existing issue from the community page.');return;}if(!response.ok)return alert(result.message||'The issue could not be submitted.');if(result.result==='duplicate'){alert('This matches an existing issue and was added as support.');return;}issues.push(result.issue);buildFilters();render();event.target.reset();reportLocation=null;alert('Your issue was added to the map.')")
)

REGISTER_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Create account · Civic Map</title><style>
:root{--ink:#172b28;--muted:#667773;--paper:#f5f1e8;--accent:#e65f38;--line:#d9d7cd}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;color:var(--ink);background:radial-gradient(circle at 85% 20%,#e8d7c1 0 12%,transparent 30%),var(--paper);font-family:Georgia,serif}.login{width:min(420px,calc(100% - 36px));padding:38px;background:#fffdf8;border:1px solid var(--line);box-shadow:12px 12px 0 #d9d7cd}.eyebrow{margin:0 0 8px;color:var(--accent);font:700 11px Arial,sans-serif;letter-spacing:1.8px;text-transform:uppercase}h1{margin:0 0 10px;font-size:42px;font-weight:500}p{color:var(--muted);line-height:1.5}label{display:block;margin-top:18px;font:13px Arial,sans-serif}input{display:block;width:100%;margin-top:6px;padding:12px;border:1px solid var(--line);background:white;font:14px Arial,sans-serif}button{width:100%;margin-top:24px;padding:12px;border:0;background:var(--accent);color:white;font-weight:bold;cursor:pointer}.error{padding:10px;background:#f8ddd4;color:#8b2e1c;font:13px Arial,sans-serif}.link{display:block;margin-top:20px;text-align:center;font:13px Arial,sans-serif;color:var(--muted)}</style></head><body><main class="login"><p class="eyebrow">Civic map</p><h1>Make your mark.</h1><p>Create an account to report civic issues and support your neighbours.</p>__ERROR__<form method="post" action="/register"><label>Email<input name="email" type="email" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="new-password" minlength="8" required></label><label>Confirm password<input name="confirm_password" type="password" autocomplete="new-password" minlength="8" required></label><button type="submit">Create account</button></form><a class="link" href="/login">Already have an account? Sign in</a></main></body></html>"""


class MapHandler(BaseHTTPRequestHandler):
	def session_user(self) -> str | None:
		cookie = self.headers.get("Cookie", "")
		for part in cookie.split(";"):
			name, separator, value = part.strip().partition("=")
			if separator and name == "session_id":
				return SESSIONS.get(value)
		return None

	def redirect(self, location: str, cookie: str | None = None) -> None:
		self.send_response(303)
		self.send_header("Location", location)
		if cookie:
			self.send_header("Set-Cookie", cookie)
		self.end_headers()

	def do_GET(self) -> None:
		path = urlsplit(self.path).path
		if path == "/login":
			page = load_login_page("").replace("</form>", '</form><a class="link" href="/register">New here? Create an account</a>')
			self.send_html(page)
			return
		if path == "/register":
			self.send_html(REGISTER_PAGE.replace("__ERROR__", ""))
			return
		if path == "/logout":
			cookie = self.headers.get("Cookie", "")
			for part in cookie.split(";"):
				name, separator, value = part.strip().partition("=")
				if separator and name == "session_id":
					SESSIONS.pop(value, None)
			self.redirect("/login", "session_id=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax")
			return
		if path.startswith("/proof/"):
			proof = PROOF_IMAGES.get(path.split("/", 2)[2])
			if proof is None:
				self.send_error(404)
				return
			self.send_payload(proof[1], content_type=proof[0])
			return
		if path == "/community":
			if self.session_user() is None:
				self.redirect("/login")
				return
			query = parse_qs(urlsplit(self.path).query)
			try:
				latitude = float(query["lat"][0])
				longitude = float(query["lng"][0])
			except (KeyError, ValueError):
				latitude = longitude = None
			self.send_html(render_page(self.session_user() or "", latitude, longitude))
			return
		if path not in ("/", "/index.html"):
			self.send_error(404)
			return
		user = self.session_user()
		if user is None:
			self.redirect("/login")
			return
		payload = MAP_PAGE.replace("__ISSUES__", json.dumps(ISSUES)).replace("__USER__", user).encode("utf-8")
		self.send_payload(payload)

	def do_POST(self) -> None:
		path = urlsplit(self.path).path
		if path == "/api/issues" or path == "/api/issues/" or path.startswith("/api/issues/") and path.endswith("/upvote"):
			if self.session_user() is None:
				self.send_error(401)
				return
			if path.endswith("/upvote"):
				try:
					issue_id = int(path.split("/")[3])
				except (IndexError, ValueError):
					self.send_error(400)
					return
				if not upvote_issue(issue_id):
					self.send_error(404)
					return
				issue = next(item for item in ISSUES if item["id"] == issue_id)
				self.send_json({"supporters": issue["supporters"]})
				return
			length = int(self.headers.get("Content-Length", "0"))
			try:
				issue = json.loads(self.rfile.read(length).decode("utf-8"))
				issue["lat"] = float(issue["lat"])
				issue["lng"] = float(issue["lng"])
				encoded_proof = issue.pop("proof_image", "")
				proof_type = issue.pop("proof_type", "image/jpeg")
				if proof_type not in {"image/jpeg", "image/png", "image/webp"}:
					self.send_error(415, "Unsupported proof image type")
					return
				proof_bytes = base64.b64decode(encoded_proof, validate=True) if encoded_proof else b""
				if len(proof_bytes) > 8 * 1024 * 1024:
					self.send_error(413, "Proof image is larger than 8 MB")
					return
				if proof_bytes:
					proof = inspect_image_proof(proof_bytes, issue["lat"], issue["lng"])
					if proof["status"] == "mismatch":
						self.send_json(proof, status=422)
						return
					issue.update({"proof_status": proof["status"], "proof_message": proof["message"]})
					proof_id = secrets.token_urlsafe(12)
					issue["proof_id"] = proof_id
				else:
					proof_id = ""
				created = add_issue(issue)
			except (ValueError, KeyError, json.JSONDecodeError):
				self.send_error(400)
				return
			if proof_bytes and created.get("issue") and created["result"] != "possible_duplicate":
				PROOF_IMAGES[proof_id] = (proof_type, proof_bytes)
				created["issue"]["proof_id"] = proof_id
			self.send_json(created, status=201 if created["result"] == "new" else 200)
			return
		if path not in ("/login", "/register"):
			self.send_error(404)
			return
		length = int(self.headers.get("Content-Length", "0"))
		form = parse_qs(self.rfile.read(length).decode("utf-8"))
		email = form.get("email", [""])[0].strip().lower()
		password = form.get("password", [""])[0]
		if path == "/register":
			if password != form.get("confirm_password", [""])[0]:
				page = REGISTER_PAGE.replace("__ERROR__", '<p class="error">Passwords do not match.</p>')
				self.send_html(page, status=400)
				return
			created, message = create_account(email, password)
			if not created:
				page = REGISTER_PAGE.replace("__ERROR__", f'<p class="error">{message}</p>')
				self.send_html(page, status=400)
				return
			self.redirect("/login")
			return
		if not authenticate(email, password):
			page = load_login_page('<p class="error">Email or password is incorrect.</p>').replace("</form>", '</form><a class="link" href="/register">New here? Create an account</a>')
			self.send_html(page, status=401)
			return
		session_id = secrets.token_urlsafe(32)
		SESSIONS[session_id] = email
		self.redirect("/", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")

	def send_html(self, page: str, status: int = 200) -> None:
		self.send_payload(page.encode("utf-8"), status)

	def send_json(self, data: dict, status: int = 200) -> None:
		self.send_payload(json.dumps(data).encode("utf-8"), status, "application/json")

	def send_payload(self, payload: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
		self.send_response(status)
		self.send_header("Content-Type", content_type)
		self.send_header("Content-Length", str(len(payload)))
		self.end_headers()
		self.wfile.write(payload)

	def log_message(self, format: str, *args: object) -> None:
		return


if __name__ == "__main__":
	server = ThreadingHTTPServer((HOST, PORT), MapHandler)
	threading.Timer(0.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
	print(f"Civic map running at http://{HOST}:{PORT} (press Ctrl+C to stop)")
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		print("\nMap stopped.")
	finally:
		server.server_close()
