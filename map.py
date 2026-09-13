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
import logging
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
LOGIN_PAGE_FILE = BASE_DIR / "templates" / "login.html"
REGISTER_PAGE_FILE = BASE_DIR / "templates" / "register.html"
PROPOSALS_PAGE_FILE = BASE_DIR / "templates" / "proposals.html"
PROFESSIONALS_PAGE_FILE = BASE_DIR / "templates" / "professionals.html"
CITIZEN_PAGE_FILE = BASE_DIR / "templates" / "citizen.html"
UNIVERSITY_DASHBOARD_FILE = BASE_DIR / "templates" / "university.html"
UNIVERSITY_LOGIN_PAGE_FILE = BASE_DIR / "templates" / "university_login.html"
UNIVERSITY_REGISTER_PAGE_FILE = BASE_DIR / "templates" / "university_register.html"
INDUSTRY_DASHBOARD_FILE = BASE_DIR / "templates" / "industry.html"
INDUSTRY_LOGIN_PAGE_FILE = BASE_DIR / "templates" / "industry_login.html"
INDUSTRY_REGISTER_PAGE_FILE = BASE_DIR / "templates" / "industry_register.html"
INDUSTRY_ADMIN_PAGE_FILE = BASE_DIR / "templates" / "industry_admin.html"
GOVERNMENT_DASHBOARD_FILE = BASE_DIR / "templates" / "government.html"
UNIVERSITY_ADMIN_PAGE_FILE = BASE_DIR / "templates" / "university_admin.html"
MAIN_MAP_PAGE_FILE = BASE_DIR / "templates" / "map.html"
ADMIN_PAGE_FILE = BASE_DIR / "templates" / "admin.html"
MAP_PAGE_FILE = BASE_DIR / "templates" / "map.html"
CONTRACTOR_LOGIN_PAGE_FILE = BASE_DIR / "templates" / "contractor_login.html"
CONTRACTOR_REGISTER_PAGE_FILE = BASE_DIR / "templates" / "contractor_register.html"
CONTRACTOR_DASHBOARD_FILE = BASE_DIR / "templates" / "contractor_dashboard.html"
CONTRACTOR_ADMIN_FILE = BASE_DIR / "templates" / "contractor_admin.html"
try:
    from .login_users import authenticate, create_account, is_admin, professional_profile
    from .community import JHARKHAND_DISTRICTS, JHARKHAND_DOMAINS, ISSUES, add_issue, distance_km, nearby_issues, render_page, upvote_issue
    from .storage import assign_issue, assign_issue_to_contractor, cast_proposal_vote, check_rate_limit, create_account_record, create_contractor, create_contractor_complaint, create_industry_partner, create_message, create_milestone, create_notification, create_session_record, create_support_offer, create_team, create_university, create_university_report, delete_session_record, get_contractor_progress_image, get_proof, get_video, get_proposal_visual, get_session_user, insert_proposal, load_all_contractor_assignments, load_all_partner_offers, load_assignments, load_contractor_assignments, load_contractor_complaints, load_contractor_leaderboard, load_contractors, load_dashboard_metrics, load_industry_partners, load_milestones, load_notifications, mark_notification_read, mark_all_notifications_read, load_messages, load_partner_offers, load_proposals, load_status_history, load_teams, load_university_assignments, load_university_assignment_responses, load_university_reports, load_universities, load_user_issues, moderate_issue, recalculate_contractor_score, review_contractor_complaint, update_assignment, update_contractor_assignment, update_contractor_status, update_institution_approval, update_milestone, update_offer_commitment, update_proposal, update_team_outcomes, update_team_status, update_university, contractor_for_user as _contractor_for_user_storage
    from .AI_model import inspect_image_proof, sanitize_and_reencode_image
    from .evidence_review import review_issue_evidence
    from .tagging import tag_issue
except ImportError:
    from login_users import authenticate, create_account, is_admin, professional_profile
    from community import JHARKHAND_DISTRICTS, JHARKHAND_DOMAINS, ISSUES, add_issue, distance_km, nearby_issues, render_page, upvote_issue
    from storage import assign_issue, assign_issue_to_contractor, cast_proposal_vote, check_rate_limit, create_account_record, create_contractor, create_contractor_complaint, create_industry_partner, create_message, create_milestone, create_notification, create_session_record, create_support_offer, create_team, create_university, create_university_report, delete_session_record, get_contractor_progress_image, get_proof, get_video, get_proposal_visual, get_session_user, insert_proposal, load_all_contractor_assignments, load_all_partner_offers, load_assignments, load_contractor_assignments, load_contractor_complaints, load_contractor_leaderboard, load_contractors, load_dashboard_metrics, load_industry_partners, load_milestones, load_notifications, mark_notification_read, mark_all_notifications_read, load_messages, load_partner_offers, load_proposals, load_status_history, load_teams, load_university_assignments, load_university_assignment_responses, load_university_reports, load_universities, load_user_issues, moderate_issue, recalculate_contractor_score, review_contractor_complaint, update_assignment, update_contractor_assignment, update_contractor_status, update_institution_approval, update_milestone, update_offer_commitment, update_proposal, update_team_outcomes, update_team_status, update_university, contractor_for_user as _contractor_for_user_storage
    from AI_model import inspect_image_proof, sanitize_and_reencode_image
    from evidence_review import review_issue_evidence
    from tagging import tag_issue
HOST = "127.0.0.1"
PORT = 8000
SESSIONS: dict[str, str] = {}
PROPOSALS: list[dict] = load_proposals()
NEXT_PROPOSAL_ID = max((proposal["id"] for proposal in PROPOSALS), default=0) + 1
UNIVERSITY_CACHE = None
CACHE_LOCK = threading.Lock()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s', filename='app.log')
UNIVERSITY_PAGE = """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>University Administration Civic Map</title><link rel='stylesheet' href='/templates/shared.css'><style>body{font-family:Georgia,serif;background:var(--paper);color:var(--ink)}header{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap}main{max-width:1150px}.admin-intro{margin-bottom:26px}.admin-intro h1{margin:8px 0 6px;font-size:clamp(32px,4vw,44px);font-weight:500}.admin-intro p{color:var(--muted);font:14px/1.6 Arial,sans-serif}.admin-content{display:grid;gap:18px}article,.university-profile,.university-create,.approval{position:relative;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:0 6px 18px rgba(23,43,40,.06)}article:before,.university-profile:before,.university-create:before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--blue),var(--gold),var(--accent))}h2{font-size:24px;font-weight:500}input,select,textarea{padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fffdf8;font:13px Arial,sans-serif}.approval{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.approval button{padding:10px 14px}.admin-content>h2{margin:12px 0 0}@media(max-width:760px){header{align-items:flex-start;flex-direction:column}.nav{width:100%}.nav-button{flex:1 1 auto;text-align:center}main{padding:24px 16px}.approval{align-items:stretch;flex-direction:column}}</style></head><body><header><div class='brand'><div class='brand-mark'>G</div><div><div class='brand-name'>Civic Map</div><div class='brand-sub'>University Administration</div></div></div><div class='tagline'>Admin workspace <a href='/logout' style='color:var(--muted)'>Log out</a></div><nav class='nav'><a class='nav-button active' href='/universities'>Universities</a><a class='nav-button' href='/industry-admin'>Industry</a><a class='nav-button' href='/government-dashboard'>Analytics</a></nav></header><main><div class='admin-intro'><p class='eyebrow'>Institution verification</p><h1>University collaboration administration.</h1><p>Approve university registrations, maintain institutional profiles, and assign approved civic challenges to the right academic teams.</p></div><div class='admin-content'>__ISSUES__</div></main><script>document.querySelectorAll('form').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));if(form.className==='team')data.members=data.members.split(',').map(member=>member.trim()).filter(Boolean);let endpoint=form.dataset.endpoint||'/api/admin/universities';if(form.className==='assignment')endpoint='/api/admin/assignments';if(form.className==='team')endpoint='/api/admin/teams';if(form.className==='response')endpoint='/api/admin/assignment-response';if(form.className==='approval')endpoint='/api/admin/institutions/'+form.dataset.kind+'/'+form.dataset.id+'/approval';const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(response.ok)location.reload();else alert((await response.json()).message||'University operation failed')})</script></body></html>"""
def parse_multipart_form(headers, body: bytes) -> tuple[dict[str, str], tuple[str, str, bytes] | None]:
    """Parse text fields and one uploaded file without the removed cgi module."""
    content_type = headers.get("Content-Type", "")
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    fields: dict[str, str] = {}
    upload = None
    for part in message.iter_parts():
        disposition = part.get_content_disposition()
        name = part.get_param("name", header="content-disposition")
        if disposition != "form-data" or not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            upload = (filename, part.get_content_type(), payload)
        else:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, upload
ADMIN_PAGE = """<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Admin Moderation · Civic Map</title>
<link rel='stylesheet' href='/templates/shared.css'>
<style>
body{font-family:Georgia,serif;background:var(--paper);color:var(--ink)}
header{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap}
main{max-width:1150px}
.admin-intro{margin-bottom:26px}.admin-intro h1{margin:8px 0 6px;font-size:clamp(32px,4vw,44px);font-weight:500;letter-spacing:-1.5px}.admin-intro p{max-width:760px;color:var(--muted);font:14px/1.6 Arial,sans-serif}
.moderation-list{display:grid;gap:16px}.moderation-card{padding:24px}.moderation-card h2,.moderation-card h3{margin:0 0 8px;font-size:20px;font-weight:500}.moderation-card p{color:var(--muted);font:14px/1.55 Arial,sans-serif}.moderation-card form{margin-top:18px}.moderation-card textarea{display:block;width:100%;min-height:78px;padding:11px 13px;margin:8px 0;border:1px solid var(--line);border-radius:8px;font:13px Arial,sans-serif;resize:vertical}.moderation-card button{margin:4px 8px 0 0;padding:10px 14px}.moderation-card button[value='Approved']{background:var(--success)}.moderation-card button[value='Rejected']{background:var(--danger)}.empty{padding:28px;background:var(--card);border:1px dashed var(--line);border-radius:14px;color:var(--muted);font:14px Arial,sans-serif}
@media(max-width:760px){header{align-items:flex-start;flex-direction:column}.nav{width:100%}.nav-button{flex:1 1 auto;text-align:center}}
</style>
</head>
<body>
<header>
    <div class='brand'><div class='brand-mark'>G</div><div><div class='brand-name'>Civic Map</div><div class='brand-sub'>Government Administration</div></div></div>
    <div class='tagline'>Admin workspace · <a href='/logout' style='color:var(--muted)'>Log out</a></div>
    <nav class='nav'><a class='nav-button' href='/'>Live Map</a><a class='nav-button' href='/community'>Community</a><a class='nav-button' href='/proposals'>Solutions</a><a class='nav-button' href='/universities'>Universities</a><a class='nav-button' href='/industry-admin'>Industry</a><a class='nav-button active' href='/admin'>Moderation</a><a class='nav-button' href='/government-dashboard'>Analytics</a></nav>
</header>
<main>
    <div class='admin-portal-bar'><div class='admin-portal-title'>Government workspace</div><nav class='admin-portal-links'><a class='active' href='/admin'>Moderation</a><a href='/industry-admin'>Industry partners</a><a href='/universities'>Universities</a><a href='/government-dashboard'>Analytics</a></nav></div>
    <div class='admin-intro'><p class='eyebrow'>Trust and safety</p><h1>Issue and proposal moderation.</h1><p>Review community reports and solution proposals before they move into institutional collaboration.</p></div>
    <div class='moderation-list'>__ISSUES__</div>
</main>
<script>document.querySelectorAll('form').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));if(event.submitter&&event.submitter.name)data.status=event.submitter.value;let endpoint='/api/admin/issues';if(form.className==='proposal-moderation')endpoint='/api/admin/proposals';if(form.className==='approval')endpoint='/api/admin/institutions/'+form.dataset.kind+'/'+form.dataset.id+'/approval';if(form.className==='industry-create')endpoint='/api/admin/industry-partners';if(form.className==='offer-update')endpoint='/api/admin/offer-commitments';const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(response.ok)location.reload();else alert((await response.json()).message||'Admin operation failed')})</script>
</body>
</html>"""
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</script></body></html>", "document.querySelectorAll('.response').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/assignment-response',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Response failed')});</script></body></html>")
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</script></body></html>", "document.querySelectorAll('.approval').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/institutions/'+form.dataset.kind+'/'+form.dataset.id+'/approval',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Approval update failed')});</script></body></html>")
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</script></body></html>", "document.querySelectorAll('.university-profile').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/universities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Profile update failed')});</script></body></html>")
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</script></body></html>", "document.querySelector('.university-create').onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/universities/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});if(response.ok)location.reload();else alert((await response.json()).message||'Registration failed')};</script></body></html>")
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("</body></html>", "<script>document.querySelectorAll('.approval').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const button=form.querySelector('button');button.disabled=true;button.textContent='Saving...';const response=await fetch('/api/admin/institutions/'+form.dataset.kind+'/'+form.dataset.id+'/approval',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok){button.textContent='Saved';button.classList.add('saved');setTimeout(()=>location.reload(),500)}else{button.disabled=false;button.textContent='Save approval';alert((await response.json()).message||'Approval update failed')}});</script></body></html>")
UNIVERSITY_PAGE = UNIVERSITY_PAGE.replace("<main>", "<main><div class='admin-portal-bar'><div class='admin-portal-title'>Government workspace</div><nav class='admin-portal-links'><a href='/admin'>Moderation</a><a href='/industry-admin'>Industry partners</a><a class='active' href='/universities'>Universities</a><a href='/government-dashboard'>Analytics</a></nav></div>", 1)
UNIVERSITY_DASHBOARD = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>University dashboard</title><style>body{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#172b28}article{border:1px solid #d9d7cd;padding:18px;margin:14px 0}select,input,textarea,button{padding:9px;margin:4px 4px 4px 0}textarea{width:95%;min-height:70px}</style></head><body><h1>University dashboard</h1><p>Assigned challenges, university decisions, project teams, and proposed solutions.</p>__ASSIGNMENTS__<script>document.querySelectorAll('form').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));if(form.className==='team')data.members=data.members.split(',').map(member=>member.trim()).filter(Boolean);const response=await fetch(form.dataset.endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(response.ok)location.reload();else alert((await response.json()).message||'Request failed')})</script></body></html>"""
INDUSTRY_DASHBOARD = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Industry dashboard</title><style>body{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#172b28}article{border:1px solid #d9d7cd;padding:18px;margin:14px 0}select,input,textarea,button{padding:9px;margin:4px 4px 4px 0}textarea{width:95%;min-height:70px}</style></head><body><h1>Industry partnership dashboard</h1><p>Offer practical support to approved societal challenges.</p>__CONTENT__<script>document.querySelectorAll('form').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/industry/offers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Offer failed')})</script></body></html>"""
GOVERNMENT_DASHBOARD = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Government dashboard</title><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#172b28}section{border:1px solid #d9d7cd;padding:18px;margin:14px 0}li{margin:7px 0}</style></head><body>__CONTENT__</body></html>"""
def load_login_page(error="", next_path="", portal_role="citizen"):
    page = LOGIN_PAGE_FILE.read_text(encoding="utf-8")
    selected_role = (portal_role or "citizen").strip().lower()
    if selected_role not in {"citizen", "government", "university", "industry", "contractor"}:
        selected_role = "citizen"
    return (
        page
        .replace("__ERROR__", error)
        .replace("__NEXT__", html.escape(next_path, quote=True))
        .replace("__PORTAL_ROLE__", html.escape(selected_role, quote=True))
    )
def load_university_login_page(error=""):
    page = UNIVERSITY_LOGIN_PAGE_FILE.read_text(encoding="utf-8")
    return page.replace("__ERROR__", error)
def load_industry_login_page(message=""):
    return INDUSTRY_LOGIN_PAGE_FILE.read_text(encoding="utf-8").replace("__MESSAGE__", message)
def load_industry_register_page(message=""):
    return INDUSTRY_REGISTER_PAGE_FILE.read_text(encoding="utf-8").replace("__MESSAGE__", message)
def load_university_register_page(message=""):
    page = UNIVERSITY_REGISTER_PAGE_FILE.read_text(encoding="utf-8")
    district_options = "".join(f"<option>{html.escape(district)}</option>" for district in JHARKHAND_DISTRICTS)
    return page.replace("__MESSAGE__", message).replace("__DISTRICTS__", district_options)
def load_register_page(error=""):
    page = REGISTER_PAGE_FILE.read_text(encoding="utf-8")
    return page.replace("__ERROR__", error)
def load_proposals_page():
    return PROPOSALS_PAGE_FILE.read_text(encoding="utf-8")
def load_professionals_page():
    return PROFESSIONALS_PAGE_FILE.read_text(encoding="utf-8")
def known_recipients() -> set[str]:
    recipients = {"admin@jharkhand.gov.in", "innovation@bitmesra.ac.in", "partner@jin.example", "citizen@example.com"}
    for u in load_universities():
        if u.get("contact_email"):
            recipients.add(u["contact_email"].strip().lower())
    for p in load_industry_partners():
        if p.get("contact_email"):
            recipients.add(p["contact_email"].strip().lower())
    for t in load_teams():
        if t.get("faculty_mentor"):
            recipients.add(t["faculty_mentor"].strip().lower())
        for m in t.get("members", []):
            recipients.add(m.strip().lower())
    return recipients


def university_for_user(user):
    return next((university for university in load_universities() if university.get("approval_status", "Active") == "Active" and str(university.get("contact_email", "")).casefold() == user.casefold()), None)
def industry_for_user(user):
    return next((partner for partner in load_industry_partners() if str(partner.get("contact_email", "")).casefold() == user.casefold() and partner.get("approval_status") == "Active"), None)
def contractor_for_user(user: str):
    """Return the contractor record for a logged-in user, or None if not a contractor."""
    return _contractor_for_user_storage(user)


def portal_role_for_user(user: str) -> str:
    """Return the single portal role represented by a logged-in account."""
    email = (user or "").strip().casefold()
    if not email:
        return "citizen"
    if is_admin(email):
        return "government"
    if contractor_for_user(email) is not None:
        return "contractor"
    if university_for_user(email) is not None:
        return "university"
    if industry_for_user(email) is not None:
        return "industry"
    return "citizen"


def user_can_access_portal(user: str, portal: str) -> bool:
    """Allow each role into its own portal; admins use government/admin workspaces."""
    if is_admin(user):
        return portal in {"citizen", "government"}
    return portal_role_for_user(user) == portal


def render_role_nav(user: str, active: str = "") -> str:
    """Render navigation links appropriate to the signed-in user's role."""
    role = portal_role_for_user(user)

    links = [
        ("/", "Live Map", "map"),
        ("/community", "Community", "community"),
        ("/proposals", "Solutions", "proposals"),
    ]

    portal_links = {
        "citizen": ("/citizen-dashboard", "My Dashboard", "citizen"),
        "university": ("/university-dashboard", "University", "university"),
        "industry": ("/industry-dashboard", "Industry", "industry"),
        "contractor": ("/contractor-dashboard", "Contractor", "contractor"),
    }

    if role == "government":
        # Government/Admin uses the government and admin workspaces.
        # Do not expose the institution-specific dashboards.
        links.extend([
            ("/citizen-dashboard", "Citizen", "citizen"),
            ("/government-dashboard", "Government", "government"),

            # Government/Admin workspace pages.
            ("/admin", "Moderation", "admin"),
            ("/universities", "Universities Admin", "universities-admin"),
            ("/industry-admin", "Industry Admin", "industry-admin"),
            ("/contractor-admin", "Contractor Admin", "contractor-admin"),
        ])
    else:
        links.append(portal_links[role])

    nav_links = "".join(
        f"<a class='nav-button{' active' if key == active else ''}' "
        f"href='{href}'>{label}</a>"
        for href, label, key in links
    )

    notification_ui = """
    <div class="notification-wrap" id="notification-wrap">
        <button class="notification-bell" type="button" aria-label="Notifications"
                onclick="toggleNotifications(event)">
            <span class="notification-icon">🔔</span>
            <span class="notification-badge" id="notification-badge" hidden>0</span>
        </button>
        <div class="notification-dropdown" id="notification-dropdown" hidden>
            <div class="notification-head">
                <strong>Notifications</strong>
                <button type="button" onclick="markAllNotificationsRead()">Mark all read</button>
            </div>
            <div id="notification-list">
                <div class="notification-empty">Loading notifications...</div>
            </div>
            <a class="notification-footer" href="/notifications">View all notifications</a>
        </div>
    </div>
    <style>
        .notification-wrap {
            position: relative;
            display: inline-flex;
            align-items: center;
            margin-left: 8px;
        }

        .notification-bell {
            position: relative;
            border: 1px solid rgba(255,255,255,.25);
            background: rgba(255,255,255,.08);
            color: #ffffff;
            cursor: pointer;
            font-size: 20px;
            padding: 8px 10px;
            line-height: 1;
            border-radius: 10px;
            transition: .2s ease;
        }

        .notification-bell:hover {
            background: rgba(255,255,255,.18);
            transform: translateY(-1px);
        }

        .notification-badge {
            position: absolute;
            top: -3px;
            right: -4px;
            min-width: 18px;
            height: 18px;
            padding: 0 5px;
            border-radius: 999px;
            background: #c0392b;
            color: #ffffff;
            font: 700 10px/18px Arial, sans-serif;
            text-align: center;
            border: 2px solid #ffffff;
        }

        .notification-dropdown {
            position: absolute;
            z-index: 9999;
            right: 0;
            top: calc(100% + 10px);
            width: 360px;
            max-width: calc(100vw - 28px);
            background: #173b35;
            color: #ffffff;
            border: 1px solid rgba(255,255,255,.22);
            border-radius: 14px;
            box-shadow: 0 16px 40px rgba(0,0,0,.35);
            overflow: hidden;
        }

        .notification-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 16px;
            background: #102f2a;
            border-bottom: 1px solid rgba(255,255,255,.15);
        }

        .notification-head strong {
            color: #ffffff;
            font-size: 15px;
        }

        .notification-head button {
            border: 0;
            background: transparent;
            color: #e6c76a;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
        }

        .notification-head button:hover {
            text-decoration: underline;
        }

        .notification-item {
            display: block;
            width: 100%;
            text-align: left;
            border: 0;
            border-bottom: 1px solid rgba(255,255,255,.10);
            background: #173b35;
            color: #d7e2df;
            padding: 13px 16px;
            cursor: pointer;
            transition: .15s ease;
        }

        .notification-item:hover {
            background: #214c44;
        }

        .notification-item.unread {
            background: #24584e;
            color: #ffffff;
            border-left: 4px solid #e6c76a;
            padding-left: 12px;
        }

        .notification-message {
            display: block;
            color: inherit;
            font-size: 13px;
            line-height: 1.5;
        }

        .notification-time {
            display: block;
            margin-top: 5px;
            color: #a9bfba;
            font-size: 11px;
        }

        .notification-item.unread .notification-time {
            color: #d5ddd9;
        }

        .notification-empty {
            padding: 20px 16px;
            color: #b8c9c5;
            font-size: 13px;
            text-align: center;
        }

        .notification-footer {
            display: block;
            padding: 13px 14px;
            background: #102f2a;
            color: #e6c76a;
            text-align: center;
            text-decoration: none;
            border-top: 1px solid rgba(255,255,255,.15);
            font-size: 13px;
            font-weight: 600;
        }

        .notification-footer:hover {
            background: #214c44;
            color: #ffffff;
        }
    </style>
    <script>
    (function () {
        function escapeHtml(value) {
            return String(value ?? '').replace(/[&<>"']/g, function (c) {
                return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]);
            });
        }

        window.loadNotifications = async function () {
            try {
                const response = await fetch('/api/notifications?_=' + Date.now(), {credentials: 'same-origin', cache: 'no-store'});
                if (!response.ok) return;
                const data = await response.json();
                const badge = document.getElementById('notification-badge');
                const list = document.getElementById('notification-list');
                if (!badge || !list) return;

                const unread = Number(data.unread_count || 0);
                badge.textContent = unread > 99 ? '99+' : String(unread);
                badge.hidden = unread === 0;

                const items = data.notifications || [];
                if (!items.length) {
                    list.innerHTML = '<div class="notification-empty">No notifications yet.</div>';
                    return;
                }

                list.innerHTML = items.slice(0, 8).map(function (item) {
                    const cls = item.is_read ? 'notification-item' : 'notification-item unread';
                    return '<button class="' + cls + '" type="button" onclick="readNotification('
                        + Number(item.id) + ')">'
                        + '<span class="notification-message">' + escapeHtml(item.message) + '</span>'
                        + '<span class="notification-time">' + escapeHtml(item.created_at) + '</span>'
                        + '</button>';
                }).join('');
            } catch (error) {
                console.warn('Could not load notifications', error);
            }
        };

        window.toggleNotifications = function (event) {
            if (event) event.stopPropagation();
            const dropdown = document.getElementById('notification-dropdown');
            if (!dropdown) return;
            dropdown.hidden = !dropdown.hidden;
            if (!dropdown.hidden) window.loadNotifications();
        };

        window.readNotification = async function (id) {
            try {
                await fetch('/api/notifications/' + encodeURIComponent(id) + '/read', {
                    method: 'POST',
                    credentials: 'same-origin'
                });
                window.loadNotifications();
            } catch (error) {
                console.warn('Could not mark notification as read', error);
            }
        };

        window.markAllNotificationsRead = async function () {
            try {
                await fetch('/api/notifications/read-all', {
                    method: 'POST',
                    credentials: 'same-origin'
                });
                window.loadNotifications();
            } catch (error) {
                console.warn('Could not mark notifications as read', error);
            }
        };

        document.addEventListener('click', function (event) {
            const wrap = document.getElementById('notification-wrap');
            const dropdown = document.getElementById('notification-dropdown');
            if (wrap && dropdown && !wrap.contains(event.target)) dropdown.hidden = true;
        });

        document.addEventListener('DOMContentLoaded', function () {
            window.loadNotifications();
            setInterval(window.loadNotifications, 30000);
        });
    })();
    </script>
    """

    return nav_links + notification_ui

def load_contractor_login_page(message: str = "") -> str:
    return CONTRACTOR_LOGIN_PAGE_FILE.read_text(encoding="utf-8").replace("__MESSAGE__", message)
def load_contractor_register_page(message: str = "") -> str:
    page = CONTRACTOR_REGISTER_PAGE_FILE.read_text(encoding="utf-8")
    district_options = "".join(f"<option>{html.escape(d)}</option>" for d in JHARKHAND_DISTRICTS)
    return page.replace("__MESSAGE__", message).replace("__DISTRICTS__", district_options)

def render_contractor_dashboard(contact_email: str) -> str:
    """Build the HTML content injected into contractor_dashboard.html's __CONTENT__ slot."""
    contractor = _contractor_for_user_storage(contact_email)
    if not contractor:
        return "<p>Contractor profile not found.</p>"
    cid = contractor["id"]
    score = contractor.get("performance_score", 0)
    completed = contractor.get("completed_projects", 0)
    complaints_filed = contractor.get("complaint_count", 0)
    status = contractor.get("approval_status", "Pending")
    is_blocked = status == "Blocked"

    # Score banner
    neg_class = " negative" if score < 0 else ""
    block_html = ""
    if is_blocked:
        reason = html.escape(contractor.get("block_reason") or "Blocked by government administrator.")
        block_html = f"<div style='margin-bottom:18px;padding:14px 18px;background:#fce8e6;border:1px solid #f5c6c4;border-radius:10px;font:14px Arial,sans-serif;color:#b83226;'><strong>⛔ Your account has been blocked.</strong> {reason} Contact the government administrator for appeal.</div>"
    score_html = (
        f"{block_html}"
        f"<div class='score-banner'>"
        f"<div class='score-number{neg_class}'>{score}</div>"
        f"<div class='score-info'>"
        f"<h2>{html.escape(contractor['company_name'])}</h2>"
        f"<p>Owner: {html.escape(contractor['owner_name'])} &nbsp;·&nbsp; District: {html.escape(contractor['district'])}</p>"
        f"<div class='stat-chips'>"
        f"<span class='stat-chip chip-green'>✅ {completed} Completed</span>"
        f"<span class='stat-chip chip-red'>⚠️ {complaints_filed} Complaints</span>"
        f"<span class='stat-chip chip-blue'>📋 {contractor['specializations']}</span>"
        f"</div></div></div>"
    )

    # Assignments
    assignments = load_contractor_assignments(cid)
    if assignments:
        cards = []
        for a in assignments:
            s = a.get("status", "Assigned")
            css_cls = {"Assigned": "assigned", "In Progress": "in-progress", "Completed": "completed", "Rejected": "rejected"}.get(s, "assigned")
            badge_cls = {"Assigned": "badge-assigned", "In Progress": "badge-in-progress", "Completed": "badge-completed", "Rejected": "badge-rejected"}.get(s, "badge-assigned")
            note_val = html.escape(a.get("completion_note") or "")
            form_html = ""
            if s not in {"Completed", "Rejected"}:
                form_html = (
                    f"<form class='update-form' style='margin-top:12px'>"
                    f"<input type='hidden' name='assignment_id' value='{a.get('id')}'>"
                    f"<div class='action-row'>"
                    f"<select name='status'>"
                    f"<option value='In Progress'{' selected' if s=='In Progress' else ''}>In Progress</option>"
                    f"<option value='Completed'>Mark Completed</option>"
                    f"</select>"
                    f"</div>"
                    f"<div style='margin-top:8px'>"
                    f"<textarea name='note' placeholder='Completion note or progress update…' style='width:100%;min-height:60px;padding:9px 11px;border:1px solid var(--line);border-radius:8px;font:13px Arial,sans-serif;resize:vertical'>{note_val}</textarea>"
                    f"<label style='display:block;margin-top:8px;font:700 10px Arial,sans-serif;letter-spacing:1px;text-transform:uppercase;color:var(--muted)'>Progress image<input name='progress_image' type='file' accept='image/jpeg,image/png,image/webp' style='display:block;margin-top:6px;font:13px Arial,sans-serif'></label>"
                    f"</div>"
                    f"<button type='submit' class='action-btn' style='margin-top:8px'>Update Status</button>"
                    f"</form>"
                )
            progress_link = ""
            if a.get("progress_image_type"):
                progress_link = (
                    "<p style='margin:12px 0 0;font:13px Arial,sans-serif'>"
                    f"<a href='/contractor-progress/{a['id']}' target='_blank' rel='noopener'>View latest progress image</a>"
                    "</p>"
                )
            block_suffix = ""
            if a.get("block"):
                block_suffix = " · " + html.escape(a.get("block", ""))
            cards.append(
                f"<div class='project-card {css_cls}'>"
                f"<div class='project-header'><h3 class='project-title'>{html.escape(a.get('issue_title','Untitled'))}</h3>"
                f"<span class='status-badge {badge_cls}'>{s}</span></div>"
                f"<div class='project-meta'>📍 {html.escape(a.get('district',''))}{block_suffix} &nbsp;|&nbsp; 🏷️ {html.escape(a.get('category',''))}</div>"
                f"<p class='project-desc'>{html.escape(a.get('issue_description',''))[:300]}</p>"
                f"{form_html}"
                f"{progress_link}</div>"
            )
        assignments_html = "<div class='project-grid'>" + "".join(cards) + "</div>"
    else:
        assignments_html = "<div class='empty-state'><div class='icon'>📋</div><p>No projects assigned yet. Check back after the government assigns you a project.</p></div>"

    # Complaints
    c_list = load_contractor_complaints(cid)
    if c_list:
        cc_html = "".join(
            f"<div class='complaint-card'>"
            f"<h4>{html.escape(c.get('complaint_type',''))}</h4>"
            f"<p>Issue: <strong>{html.escape(c.get('issue_title',''))}</strong></p>"
            f"<p>{html.escape(c.get('description',''))}</p>"
            f"<p>Status: <span class='status-{'reviewed' if c.get('status')=='Reviewed' else 'dismissed'}'>{c.get('status','Pending')}</span></p>"
            f"<p style='color:var(--muted);font-size:11px'>Filed by: {html.escape(c.get('filed_by',''))}</p>"
            f"</div>"
            for c in c_list
        )
    else:
        cc_html = "<div class='empty-state'><p>No complaints filed against you.</p></div>"

    return (
        score_html
        + f"<h2 class='section-title'>Assigned Projects <span>{len(assignments)}</span></h2>" + assignments_html
        + f"<h2 class='section-title'>Complaints Filed Against You <span>{len(c_list)}</span></h2>" + cc_html
    )


def render_contractor_admin() -> str:
    """Build the HTML injected into contractor_admin.html's __CONTENT__ slot (5 tab panels)."""
    contractors = load_contractor_leaderboard()
    all_assignments = load_all_contractor_assignments()
    all_complaints = load_contractor_complaints()
    issues = ISSUES

    # --- TAB 1: Leaderboard ---
    lb_cards = []
    for rank, c in enumerate(contractors, 1):
        s = c.get("approval_status", "Pending")
        score = c.get("performance_score", 0)
        badge_cls = {"Active": "badge-active", "Blocked": "badge-blocked", "Pending": "badge-pending"}.get(s, "badge-pending")
        card_cls = {"Active": "active", "Blocked": "blocked", "Pending": "pending"}.get(s, "pending")
        rank_cls = " top" if rank <= 3 and s == "Active" else ""
        specs = [html.escape(sp.strip()) for sp in (c.get("specializations") or "").split(",") if sp.strip()]
        spec_tags = "".join(f"<span class='tag'>{sp}</span>" for sp in specs)
        score_cls = " neg" if score < 0 else ""
        # Action buttons
        if s == "Active":
            action = (
                f"<form class='block-form' style='margin-top:8px'>"
                f"<input type='hidden' name='contractor_id' value='{c.get('id')}'>"
                f"<input type='text' name='reason' placeholder='Reason for blocking…' required>"
                f"<button type='submit' class='block-btn'>Block</button>"
                f"</form>"
            )
        elif s == "Blocked":
            action = (
                f"<form class='activate-form' style='margin-top:8px'>"
                f"<input type='hidden' name='contractor_id' value='{c.get('id')}'>"
                f"<button type='submit' class='activate-btn'>✅ Reactivate</button>"
                f"</form>"
            )
        else:
            action = ""
        block_note = ""
        if s == "Blocked" and c.get("block_reason"):
            block_note = f"<p style='color:var(--danger);font:12px Arial,sans-serif;margin-top:4px'>⛔ {html.escape(c['block_reason'])}</p>"
        lb_cards.append(
            f"<div class='contractor-card {card_cls}'>"
            f"<div class='rank-badge{rank_cls}'>#{rank}</div>"
            f"<div class='contractor-info'>"
            f"<h3>{html.escape(c['company_name'])}</h3>"
            f"<p>{html.escape(c['owner_name'])} &nbsp;·&nbsp; {html.escape(c['district'])}</p>"
            f"<div class='tags'>{spec_tags}</div>"
            f"{block_note}{action}</div>"
            f"<div class='contractor-score-col'>"
            f"<div class='score-num{score_cls}'>{score}</div>"
            f"<div class='score-meta'>{c.get('completed_projects',0)} done · {c.get('complaint_count',0)} complaints</div>"
            f"<span class='status-badge {badge_cls}'>{s}</span>"
            f"</div></div>"
        )
    leaderboard_panel = (
        "<div id='panel-leaderboard' class='tab-panel active'>"
        + ("<div class='leaderboard-grid'>" + "".join(lb_cards) + "</div>" if lb_cards else "<div class='empty'>No contractors registered yet.</div>")
        + "</div>"
    )

    # --- TAB 2: Assign Issue ---
    active_contractors = [c for c in contractors if c.get("approval_status") == "Active"]
    contractor_options = "".join(
        f"<option value='{c['id']}'>{html.escape(c['company_name'])} (Score: {c.get('performance_score', 0)})</option>"
        for c in active_contractors
    )
    approved_issues = [i for i in issues if i.get("moderation_status") == "Approved"]
    issue_options = "".join(
        f"<option value='{i['id']}'>{html.escape(i.get('title',''))[:70]} — {html.escape(i.get('district',''))}</option>"
        for i in approved_issues
    )
    assign_panel = (
        "<div id='panel-assign' class='tab-panel'>"
        "<div class='assign-panel'>"
        "<h2>Assign an Issue to a Contractor</h2>"
        "<form id='assign-form'>"
        "<div class='assign-grid'>"
        "<div class='field'><label>Select Issue</label>"
        f"<select name='issue_id' required><option value='' disabled selected>Choose approved issue…</option>{issue_options}</select></div>"
        "<div class='field'><label>Select Contractor</label>"
        f"<select name='contractor_id' required><option value='' disabled selected>Choose active contractor…</option>{contractor_options}</select></div>"
        "</div>"
        "<button type='submit' class='submit-btn' style='margin-top:14px'>Assign to Contractor</button>"
        "</form></div></div>"
    )

    # --- TAB 3: Active Assignments ---
    if all_assignments:
        asn_cards = []
        for a in all_assignments:
            s = a.get("status", "Assigned")
            s_cls = {"Assigned": "asn-assigned", "In Progress": "asn-in-progress", "Completed": "asn-completed"}.get(s, "asn-assigned")
            asn_cards.append(
                f"<div class='assignment-card'>"
                f"<h4>{html.escape(a.get('issue_title',''))}</h4>"
                f"<p>Contractor: <strong>{html.escape(a.get('company_name',''))}</strong></p>"
                f"<p>District: {html.escape(a.get('district',''))} &nbsp;|&nbsp; Category: {html.escape(a.get('category',''))}</p>"
                f"<p>Assigned by: {html.escape(a.get('assigned_by',''))} &nbsp;|&nbsp; Score: {a.get('performance_score',0)}</p>"
                f"<p><span class='asn-status {s_cls}'>{s}</span></p>"
                + (f"<p style='color:var(--muted);font:12px Arial,sans-serif'>Note: {html.escape(a.get('completion_note') or '')}</p>" if a.get("completion_note") else "")
                + "</div>"
            )
        asn_html = "<div class='assignments-list'>" + "".join(asn_cards) + "</div>"
    else:
        asn_html = "<div class='empty'>No contractor assignments yet.</div>"
    assignments_panel = "<div id='panel-assignments' class='tab-panel'>" + asn_html + "</div>"

    # --- TAB 4: Complaints ---
    pending_complaints = [c for c in all_complaints if c.get("status") == "Pending"]
    reviewed_complaints = [c for c in all_complaints if c.get("status") != "Pending"]

    def _complaint_card(c: dict, show_actions: bool) -> str:
        actions = ""
        if show_actions:
            actions = (
                f"<div class='complaint-actions'>"
                f"<form class='complaint-review-form' style='display:inline'>"
                f"<input type='hidden' name='complaint_id' value='{c.get('id')}'>"
                f"<input type='hidden' name='action' value='confirm'>"
                f"<button type='submit' class='review-btn'>⚠️ Confirm (deduct score)</button></form>"
                f"<form class='complaint-review-form' style='display:inline'>"
                f"<input type='hidden' name='complaint_id' value='{c.get('id')}'>"
                f"<input type='hidden' name='action' value='dismiss'>"
                f"<button type='submit' class='dismiss-btn'>Dismiss</button></form>"
                f"</div>"
            )
        return (
            f"<div class='complaint-card'>"
            f"<h4>{html.escape(c.get('company_name',''))}</h4>"
            f"<span class='ctype'>{html.escape(c.get('complaint_type',''))}</span>"
            f"<p>Issue: <strong>{html.escape(c.get('issue_title',''))}</strong></p>"
            f"<p>{html.escape(c.get('description',''))}</p>"
            f"<p style='color:var(--muted);font:11px Arial,sans-serif'>Filed by: {html.escape(c.get('filed_by',''))} · Status: {c.get('status','')}</p>"
            f"{actions}</div>"
        )

    complaints_html = (
        ("<h3 style='margin:0 0 12px'>Pending Review</h3>" + "".join(_complaint_card(c, True) for c in pending_complaints) if pending_complaints else "<div class='empty'>No pending complaints.</div>")
        + ("<h3 style='margin:18px 0 12px'>Previously Reviewed</h3>" + "".join(_complaint_card(c, False) for c in reviewed_complaints) if reviewed_complaints else "")
    )
    complaints_panel = "<div id='panel-complaints' class='tab-panel'>" + complaints_html + "</div>"

    # --- TAB 5: Pending Approvals ---
    pending_contractors = [c for c in contractors if c.get("approval_status") == "Pending"]
    if pending_contractors:
        pend_cards = "".join(
            f"<div class='assign-panel'>"
            f"<h3 style='margin:0 0 8px'>{html.escape(p['company_name'])}</h3>"
            f"<p style='color:var(--muted);font:13px Arial,sans-serif'>Owner: {html.escape(p['owner_name'])} &nbsp;·&nbsp; License: {html.escape(p['license_no'])} &nbsp;·&nbsp; District: {html.escape(p['district'])}</p>"
            f"<p style='color:var(--muted);font:13px Arial,sans-serif'>Specializations: {html.escape(p.get('specializations',''))}</p>"
            f"<div class='contractor-actions'>"
            f"<form class='contractor-approval-form'><input type='hidden' name='contractor_id' value='{p['id']}'><input type='hidden' name='status' value='Active'><button type='submit' class='activate-btn'>✅ Approve</button></form>"
            f"<form class='contractor-approval-form'><input type='hidden' name='contractor_id' value='{p['id']}'><input type='hidden' name='status' value='Rejected'><button type='submit' class='block-btn'>❌ Reject</button></form>"
            f"</div></div>"
            for p in pending_contractors
        )
    else:
        pend_cards = "<div class='empty'>No pending contractor registrations.</div>"
    pending_panel = "<div id='panel-pending' class='tab-panel'>" + pend_cards + "</div>"

    return leaderboard_panel + assign_panel + assignments_panel + complaints_panel + pending_panel


DISTRICT_COORDS = {
    "Bokaro": (23.6693, 85.9563),
    "Chatra": (24.2120, 84.8715),
    "Deoghar": (24.4826, 86.6966),
    "Dhanbad": (23.7957, 86.4304),
    "Dumka": (24.2676, 87.2497),
    "East Singhbhum": (22.8046, 86.2029),
    "Garhwa": (24.1624, 83.8073),
    "Giridih": (24.1868, 86.3050),
    "Godda": (24.8267, 87.2132),
    "Gumla": (23.0448, 84.5422),
    "Hazaribagh": (23.9925, 85.3637),
    "Jamtara": (23.9629, 86.8000),
    "Khunti": (23.0763, 85.2787),
    "Koderma": (24.4678, 85.5938),
    "Latehar": (23.7454, 84.4632),
    "Lohardaga": (23.4377, 84.6806),
    "Pakur": (24.6341, 87.8488),
    "Palamu": (24.0326, 84.0722),
    "Ramgarh": (23.6288, 85.5173),
    "Ranchi": (23.3441, 85.3096),
    "Sahibganj": (25.2425, 87.6419),
    "Seraikela Kharsawan": (22.7001, 85.9298),
    "Simdega": (22.6148, 84.5074),
    "West Singhbhum": (22.5694, 85.8115),
}
def _keywords(value):
    return {word for word in "".join(ch.casefold() if ch.isalnum() else " " for ch in str(value)).split() if len(word) > 2}
def _issue_coords(issue):
    try:
        return float(issue["lat"]), float(issue["lng"])
    except (KeyError, TypeError, ValueError):
        return DISTRICT_COORDS.get(str(issue.get("district", "")))
def _university_coords(university):
    return DISTRICT_COORDS.get(str(university.get("district", "")))
def university_expertise_score(university, issue):
    category = str(issue.get("category", "")).casefold()
    issue_words = _keywords(" ".join(str(issue.get(field, "")) for field in ("title", "description", "category", "block", "area")))
    domain_words = _keywords(university.get("domains", ""))
    expertise_words = _keywords(university.get("expertise", ""))
    capability_words = _keywords(" ".join(str(university.get(field, "")) for field in ("departments", "laboratories", "incubation_facilities")))
    category_words = _keywords(category)
    score = len(issue_words & (domain_words | expertise_words | capability_words)) * 8
    score += len(category_words & domain_words) * 35
    score += len(category_words & expertise_words) * 35
    score += len(issue_words & expertise_words) * 12
    score += len(issue_words & capability_words) * 6
    return score
def university_location_score(university, issue):
    if str(issue.get("district", "")).casefold() == str(university.get("district", "")).casefold():
        return 45
    issue_coords = _issue_coords(issue)
    university_coords = _university_coords(university)
    if not issue_coords or not university_coords:
        return 0
    distance = distance_km(issue_coords[0], issue_coords[1], university_coords[0], university_coords[1])
    return max(1, int(35 - min(distance, 350) / 10))
def university_issue_score(university, issue):
    return university_expertise_score(university, issue) + university_location_score(university, issue)


def industry_match_score(partner, issue):
    issue_words = _keywords(" ".join(str(issue.get(field, "")) for field in ("title", "description", "category", "block", "area")))
    domain_words = _keywords(partner.get("domains", ""))
    expertise_matches = issue_words & domain_words
    location_match = str(issue.get("district", "")).casefold() == str(partner.get("district", "")).casefold()
    location_score = 45 if location_match else 0
    issue_coords = _issue_coords(issue)
    partner_coords = DISTRICT_COORDS.get(str(partner.get("district", "")))
    if not location_match and issue_coords and partner_coords:
        distance = distance_km(issue_coords[0], issue_coords[1], partner_coords[0], partner_coords[1])
        location_score = max(1, int(35 - min(distance, 350) / 10))
    expertise_score = len(expertise_matches) * 20
    return expertise_score + location_score, expertise_matches, location_match


def industry_match_markup(partner, issue):
    score, expertise_matches, location_match = industry_match_score(partner, issue)
    expertise_text = ", ".join(sorted(expertise_matches)) if expertise_matches else "No direct domain keyword overlap"
    location_text = "same district" if location_match else "nearest available location"
    return (
        f"<div style='background:#edf7f6;border-left:4px solid #317c91;border-radius:8px;padding:10px 12px;margin:10px 0;font-size:12px;'>"
        f"<strong>AI-assisted partner match: {score} points</strong><br>"
        f"Expertise signals: {html.escape(expertise_text)}  Location: {html.escape(location_text)}"
        f"</div>"
    )


def best_university_for_issue(issue, universities):
    universities = [university for university in universities if university.get("approval_status", "Active") == "Active"]
    ranked = sorted(
        universities,
        key=lambda university: (
            university_expertise_score(university, issue),
            university_location_score(university, issue),
            university_issue_score(university, issue),
        ),
        reverse=True,
    )
    if not ranked:
        return None, 0
    score = university_issue_score(ranked[0], issue)
    return (ranked[0], score) if score > 0 else (None, 0)
def auto_assign_tasks_to_university(university, assigned_by="ai-assignment"):
    assignments = load_assignments()
    universities = load_universities()
    assigned = []
    for issue in ISSUES:
        if issue.get("moderation_status", "Pending") != "Approved" or issue.get("id") in assignments:
            continue
        recommended, score = best_university_for_issue(issue, universities)
        if recommended and recommended["id"] == university["id"]:
            if assign_issue(issue["id"], university["id"], assigned_by):
                assigned.append({"issue": issue, "score": score})
    return assigned
def _cached_universities() -> list[dict]:
    global UNIVERSITY_CACHE
    with CACHE_LOCK:
        if UNIVERSITY_CACHE is None:
            UNIVERSITY_CACHE = [u for u in load_universities() if u.get("approval_status") == "Active"]
        return UNIVERSITY_CACHE

def auto_assign_issue_to_best_university(issue, assigned_by="ai-assignment"):
    if issue.get("id") in load_assignments():
        return None
    try:
        recommended, score = best_university_for_issue(issue, _cached_universities())
    except Exception as exc:
        logging.error(f"Ranking failed for issue {issue.get('id')}: {exc}")
        return None
    if not recommended:
        return None
    if not assign_issue(issue["id"], recommended["id"], assigned_by):
        return None
    if recommended.get("contact_email"):
        create_notification(
            recommended["contact_email"],
            f"AI assigned a matching challenge to {recommended['name']}: {issue.get('title', 'Civic issue')}.",
            "assignment",
            issue["id"],
        )
    return {"university": recommended, "score": score}
def render_dashboard_team(team):
    milestones = load_milestones(team["id"])
    history = load_status_history(team["id"])
    milestone_markup = "".join(f"<p>Milestone: {html.escape(milestone['title'])}  {html.escape(str(milestone['status']))}  {html.escape(str(milestone['due_date'] or 'No due date'))}</p><form data-endpoint='/api/university/milestone-status'><input type='hidden' name='milestone_id' value='{milestone['id']}'><select name='status'><option>Pending</option><option>In Progress</option><option>Completed</option></select><input name='testing_result' placeholder='Testing result'><button>Save milestone</button></form>" for milestone in milestones)
    history_markup = "".join(f"<p>History: {html.escape(item['status'])}  {html.escape(item['changed_by'])}  {html.escape(str(item['changed_at']))}</p>" for item in history)
    return f"<p><strong>{html.escape(team['name'])}</strong>  Mentor: <em>{html.escape(team['faculty_mentor'])}</em>  Stage: {html.escape(team['status'])}  Members: {html.escape(', '.join(team['members']))}</p><form data-endpoint='/api/university/team-status'><input type='hidden' name='team_id' value='{team['id']}'><select name='status'><option>Team Formed</option><option>Prototype</option><option>Pilot</option><option>Deployed</option><option>Impact Measured</option></select><input name='note' placeholder='Stage update note'><button>Update stage</button></form><form data-endpoint='/api/university/milestones'><input type='hidden' name='team_id' value='{team['id']}'><input name='title' placeholder='Milestone title' required><input name='due_date' type='date'><input name='deliverable' placeholder='Deliverable'><button>Add milestone</button></form>{milestone_markup}<h4>Status history</h4>{history_markup}<form data-endpoint='/api/university/team-outcomes'><input type='hidden' name='team_id' value='{team['id']}'><input name='ip_outcome' placeholder='IP or patent outcome'><input name='startup_outcome' placeholder='Startup outcome'><textarea name='impact_summary' placeholder='Community impact summary'></textarea><button>Save outcomes</button></form>"
def render_university_dashboard(user):
    page = UNIVERSITY_DASHBOARD_FILE.read_text(encoding="utf-8")

    def option_values(values, selected):
        return "".join(
            f"<option value='{html.escape(value)}'{' selected' if value == selected else ''}>{html.escape(value)}</option>"
            for value in values
        )

    def render_shell(content, hero, metrics="", teams="", milestones="", offers="", messages="", profile=""):
        return (
            page.replace("__USER__", html.escape(user))
            .replace("__UNIVERSITY_HERO__", hero)
            .replace("__METRICS_BAR__", metrics)
            .replace("__CHALLENGES_CONTENT__", content)
            .replace("__TEAMS_CONTENT__", teams)
            .replace("__MILESTONES_CONTENT__", milestones)
            .replace("__OFFERS_CONTENT__", offers)
            .replace("__MESSAGES_CONTENT__", messages)
            .replace("__PROFILE_CONTENT__", profile)
        )

    university = university_for_user(user)
    if university is None:
        error_hero = f"""
        <div class="hero-card">
          <span class="hero-eyebrow">Authentication Required</span>
          <h1 class="hero-title">University Account Required</h1>
          <p class="hero-desc">The signed-in account (<strong>{html.escape(user)}</strong>) is not associated with an accredited university or institution. Please log in with a registered university contact email (e.g. <code>innovation@bitmesra.ac.in</code>, <code>innovation@cuj.ac.in</code>, or <code>innovation@nitjsr.ac.in</code>) or contact the portal administrator.</p>
          <div style="margin-top:20px;">
            <a href="/logout" class="btn btn-accent">Sign In with University Account</a>
          </div>
        </div>
        """
        return render_shell("", error_hero)

    assignments = load_university_assignments(user)
    university_teams = [team for team in load_teams() if team["university_id"] == university["id"]]
    reports = load_university_reports()
    assignment_ids = {assignment["issue_id"] for assignment in assignments}
    university_milestones = [milestone for team in university_teams for milestone in load_milestones(team["id"])]
    university_offers = [offer for offer in load_all_partner_offers() if offer.get("issue_id") in assignment_ids]
    messages_for_user = load_messages(user)
    notifications = load_notifications(user)
    hero = f"""
    <section class='hero-card'>
      <span class='hero-eyebrow'>University project workspace</span>
      <h1 class='hero-title'>{html.escape(university['name'])}</h1>
      <p class='hero-desc'>Coordinate assigned civic challenges, student teams, milestones, reports, and industry collaboration from one workspace.</p>
    </section>
    """
    cards = []
    for assignment in assignments:
        issue_id = assignment["issue_id"]
        issue_teams = [team for team in university_teams if team["issue_id"] == issue_id]
        issue_reports = [r for r in reports if r["issue_id"] == issue_id and r["university_id"] == assignment["university_id"]]
        team_markup = "".join(render_dashboard_team(team) for team in issue_teams)
        if not team_markup:
            team_markup = "<p class='muted'>No faculty mentor or student team assigned yet.</p>"
        report_cards = []
        for r in issue_reports:
            deliv_text = html.escape(r['deliverables']) if r.get('deliverables') else ""
            deliv_html = f"<p><strong>Deliverables:</strong> {deliv_text}</p>" if deliv_text else ""
            report_cards.append(
                f"<div style='background:#eef6f8;padding:12px;border-radius:8px;margin-bottom:10px;'>"
                f"<strong>{html.escape(r['title'])}</strong><br>"
                f"<p>{html.escape(r['summary'])}</p>"
                f"{deliv_html}"
                f"<small style='color:#666;'>Submitted by {html.escape(r['submitted_by'])} on {r['created_at']}</small>"
                f"</div>"
            )
        reports_markup = "".join(report_cards)
        if not reports_markup:
            reports_markup = "<p class='muted'>No project reports submitted yet.</p>"
        status_badge = f"<span style='padding:4px 10px;border-radius:6px;font-weight:bold;font-size:12px;background:{'#d4edda' if assignment['status']=='Accepted' else '#f8d7da' if assignment['status']=='Rejected' else '#fff3cd'};color:{'#155724' if assignment['status']=='Accepted' else '#721c24' if assignment['status']=='Rejected' else '#856404'}'>{html.escape(assignment['status'])}</span>"
        cards.append(
            f"<article>"
            f"<h2>{html.escape(assignment['title'])}</h2>"
            f"<p>{html.escape(assignment['description'])}</p>"
            f"<p>District: <strong>{html.escape(assignment['district'])}</strong>  Block: <strong>{html.escape(assignment['block'])}</strong>  Category: <strong>{html.escape(assignment['category'])}</strong></p>"
            f"<p>Request Status: {status_badge}</p>"
            f"<h3>1. Accept or Reject Request (Passed to Government)</h3>"
            f"<form data-endpoint='/api/university/assignment-response'>"
            f"<input type='hidden' name='issue_id' value='{issue_id}'>"
            f"<select name='status'><option value='Accepted'>Accept Request</option><option value='Rejected'>Reject Request</option><option value='Needs clarification'>Needs Clarification</option></select>"
            f"<input name='reason' placeholder='Reason for government record' required style='width:60%;'>"
            f"<button type='submit'>Save & Transmit Decision to Government</button>"
            f"</form>"
            f"<h3>2. Student Project Teams</h3>"
            f"{team_markup}"
            f"<form class='team' data-endpoint='/api/university/teams' style='margin-top:12px;background:#fffdf8;padding:16px;border:1px solid #dedbd1;border-radius:10px;'>"
            f"<h4>Assign Project Team</h4>"
            f"<input type='hidden' name='issue_id' value='{issue_id}'>"
            f"<input type='hidden' name='university_id' value='{assignment['university_id']}'>"
            f"<input name='name' placeholder='Project Team Name (e.g. Smart Water Innovation Team)' required style='width:98%;'><br>"
            f"<input name='faculty_mentor' placeholder='Faculty Mentor Email (e.g. prof.sharma@bitmesra.ac.in)' required style='width:98%;'><br>"
            f"<input name='members' placeholder='Assigned Student Emails (comma separated: student1@bitmesra.ac.in, student2@bitmesra.ac.in)' required style='width:98%;'><br>"
            f"<button type='submit' style='margin-top:8px;'>Assign Faculty & Students</button>"
            f"</form>"
            f"<h3>3. Milestones & Testing</h3>"
            f"<h3>4. Submit University Project Report (Visible to All)</h3>"
            f"{reports_markup}"
            f"<form class='report-form' data-endpoint='/api/university/reports' style='margin-top:12px;background:#fffdf8;padding:16px;border:1px solid #dedbd1;border-radius:10px;'>"
            f"<h4>Submit Public Project Report</h4>"
            f"<input type='hidden' name='issue_id' value='{issue_id}'>"
            f"<input name='title' placeholder='Report Title (e.g. Water Treatment Pilot Phase 1 Report)' required style='width:98%;'><br>"
            f"<textarea name='summary' placeholder='Executive Summary & Key Findings (Visible to All)' required style='width:98%;min-height:70px;'></textarea><br>"
            f"<textarea name='deliverables' placeholder='Project Deliverables, Prototypes, & Outcomes' style='width:98%;min-height:50px;'></textarea><br>"
            f"<button type='submit' style='margin-top:8px;'>Submit Report to Public Record</button>"
            f"</form>"
            f"<h3>5. Solution Proposals</h3>"
            f"<form data-endpoint='/api/proposals'>"
            f"<input type='hidden' name='issue_id' value='{issue_id}'>"
            f"<input name='title' placeholder='Solution Proposal Title' required style='width:98%;'><br>"
            f"<textarea name='description' placeholder='Describe the technical solution proposal' required style='width:98%;'></textarea><br>"
            f"<button type='submit'>Submit Proposal</button>"
            f"</form>"
            f"</article>"
        )
    challenge_content = "".join(cards) or "<div class='empty-state'><h2>No assigned challenges yet</h2><p>No issues have been assigned to this university yet.</p></div>"

    def metric_card(icon, tone, label, value):
        return f"<div class='metric-card'><div class='metric-icon {tone}'>{icon}</div><div class='metric-info'><h4>{label}</h4><div class='val'>{value}</div></div></div>"

    metrics = "<div class='metrics-grid'>" + "".join([
        metric_card("◎", "blue", "Assigned challenges", len(assignments)),
        metric_card("◈", "gold", "Active teams", len(university_teams)),
        metric_card("✓", "green", "Completed milestones", sum(1 for item in university_milestones if item.get("status") == "Completed")),
        metric_card("✦", "coral", "Industry offers", len(university_offers)),
    ]) + "</div>"

    if university_teams:
        team_cards = []
        for team in university_teams:
            team_milestones = [item for item in university_milestones if item["team_id"] == team["id"]]
            team_cards.append(
                f"<div class='section-card'><div class='card-header-row'><div><h3>{html.escape(team['name'])}</h3><p class='muted'>Faculty mentor: {html.escape(team['faculty_mentor'])}</p></div><span class='status-pill assigned'>{html.escape(team['status'])}</span></div>"
                f"<p class='meta-row'><span class='meta-item'><strong>{len(team.get('members', []))}</strong> student members</span><span class='meta-item'><strong>{len(team_milestones)}</strong> milestones</span></p>"
                f"<form data-endpoint='/api/university/team-status' class='approval'><input type='hidden' name='team_id' value='{team['id']}'><label>Project stage<select name='status'>{option_values(['Team Formed', 'Prototype', 'Pilot', 'Deployed', 'Impact Measured'], team.get('status', 'Team Formed'))}</select></label><input name='note' placeholder='Stage update note'><button class='btn-primary'>Update stage</button></form></div>"
            )
        teams_content = "".join(team_cards)
    else:
        teams_content = "<div class='empty-state'><h3>No student teams yet</h3><p>Open an assigned challenge to create the first project team.</p></div>"

    if university_milestones:
        milestone_cards = []
        for milestone in university_milestones:
            team = next((item for item in university_teams if item["id"] == milestone["team_id"]), None)
            milestone_cards.append(
                f"<div class='section-card'><div class='card-header-row'><div><h3>{html.escape(milestone['title'])}</h3><p class='muted'>{html.escape(team['name'] if team else 'Project team')}</p></div><span class='status-pill {'accepted' if milestone.get('status') == 'Completed' else 'pending'}'>{html.escape(milestone.get('status', 'Pending'))}</span></div><p class='meta-row'><span class='meta-item'>Due: <strong>{html.escape(str(milestone.get('due_date') or 'No due date'))}</strong></span><span class='meta-item'>Deliverable: <strong>{html.escape(milestone.get('deliverable') or 'Not specified')}</strong></span></p><form data-endpoint='/api/university/milestone-status' class='approval'><input type='hidden' name='team_id' value='{milestone['team_id']}'><input type='hidden' name='milestone_id' value='{milestone['id']}'><label>Status<select name='status'>{option_values(['Pending', 'In Progress', 'Completed'], milestone.get('status', 'Pending'))}</select></label><input name='testing_result' value='{html.escape(milestone.get('testing_result') or '')}' placeholder='Testing result'><button class='btn-primary'>Save milestone</button></form></div>"
            )
        milestones_content = "".join(milestone_cards)
    else:
        milestones_content = "<div class='empty-state'><h3>No milestones yet</h3><p>Create milestones from a project team inside an assigned challenge.</p></div>"

    if university_offers:
        offers_content = "".join(f"<div class='section-card'><div class='card-header-row'><div><h3>{html.escape(offer.get('support_type', 'Industry support'))}</h3><p class='muted'>{html.escape(offer.get('partner_name', 'Industry partner'))} · {html.escape(offer.get('title', 'Assigned challenge'))}</p></div><span class='status-pill {'accepted' if offer.get('status') in {'Accepted', 'Delivered'} else 'pending'}'>{html.escape(offer.get('status', 'Offered'))}</span></div><p>{html.escape(offer.get('details', ''))}</p><p class='meta-row'><span class='meta-item'>Commitment: <strong>{html.escape(offer.get('commitment_note') or 'Awaiting review')}</strong></span></p></div>" for offer in university_offers)
    else:
        offers_content = "<div class='empty-state'><h3>No industry offers yet</h3><p>Industry support linked to your assigned challenges will appear here.</p></div>"

    message_cards = "".join(f"<div class='section-card'><div class='card-header-row'><div><h3>{html.escape('Message from ' + item['sender'] if item['recipient'].casefold() == user.casefold() else 'Message to ' + item['recipient'])}</h3><p class='muted'>{html.escape(str(item.get('created_at', '')))}</p></div></div><p>{html.escape(item['message'])}</p></div>" for item in messages_for_user[:12])
    notification_cards = "".join(f"<div class='final-report'><strong>{html.escape(item['message'])}</strong><br><small>{html.escape(str(item.get('created_at', '')))}</small></div>" for item in notifications[:8])
    empty_messages = "<div class=\"empty-state\"><h3>No messages yet</h3><p>Your project communication will appear here.</p></div>"
    messages_content = (
        "<div class='section-card'><h3>Send a project message</h3>"
        "<form data-endpoint='/api/messages'><label>Recipient"
        "<input name='recipient' type='email' value='admin@jharkhand.gov.in' required></label>"
        "<label>Message<textarea name='message' placeholder='Write an update or request' required></textarea>"
        "<button class='btn-primary'>Send message</button></form></div>"
        f"{notification_cards}{message_cards or empty_messages}"
    )

    profile_content = f"<div class='section-card'><p class='eyebrow'>Institutional profile</p><h2>{html.escape(university['name'])}</h2><p class='hero-desc'>Your university workspace is connected to the civic innovation network.</p><div class='inst-badges'><span class='inst-tag'>Contact: {html.escape(university.get('contact_email', user))}</span><span class='inst-tag'>District: {html.escape(university.get('district', 'Not specified'))}</span><span class='inst-tag'>Status: {html.escape(university.get('approval_status', 'Active'))}</span></div></div>"
    return render_shell(challenge_content, hero, metrics, teams_content, milestones_content, offers_content, messages_content, profile_content)
def industry_for_user(user):
    return next((partner for partner in load_industry_partners() if partner.get("approval_status", "Active") == "Active" and str(partner.get("contact_email", "")).casefold() == user.casefold()), None)
def render_industry_dashboard(user):
    partner = industry_for_user(user)
    if partner is None:
        return "<div class='section-card'><h1>Industry Partner Account Required</h1><p>This account is not linked to a registered industry partner profile.</p></div>"
    
    offers = load_partner_offers(user)
    assignments = load_assignments()
    universities = load_universities()
    teams = load_teams()
    reports = load_university_reports()
    approved_issues = sorted(
        (issue for issue in ISSUES if issue.get("moderation_status", "Pending") == "Approved"),
        key=lambda issue: industry_match_score(partner, issue)[0],
        reverse=True,
    )
    
    total_offers = len(offers)
    total_funding = sum(int(offer.get("funding_amount") or 0) for offer in offers)
    accepted_offers = sum(1 for offer in offers if offer.get("status") in {"Accepted", "Delivered"})
    
    # 1. Partner Profile & Metric Overview
    profile_html = (
        f"<div class='section-card' style='background:linear-gradient(135deg, #172b28 0%, #203f3a 100%);color:white;border-radius:16px;padding:26px;margin-bottom:26px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;'>"
        f"<div>"
        f"<span style='background:rgba(230,95,56,0.25);color:#ff9e80;border:1px solid #e65f38;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;'>{html.escape(partner['partner_type'])}</span>"
        f"<h2 style='margin:10px 0 4px;font-size:28px;color:#fff;'>{html.escape(partner['name'])}</h2>"
        f"<p style='color:#a3c2bc;font-size:13px;margin:0;'>District: <strong>{html.escape(partner['district'])}</strong> · Focus Domains: <strong>{html.escape(partner['domains'])}</strong> · Contact: <strong>{html.escape(partner['contact_email'])}</strong></p>"
        f"</div>"
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;'>"
        f"<div style='background:rgba(255,255,255,0.08);padding:12px 18px;border-radius:12px;text-align:center;min-width:110px;'>"
        f"<div style='font-size:22px;font-weight:bold;color:#ff9e80;'>{total_offers}</div><div style='font-size:11px;color:#a3c2bc;text-transform:uppercase;'>Support Offers</div>"
        f"</div>"
        f"<div style='background:rgba(255,255,255,0.08);padding:12px 18px;border-radius:12px;text-align:center;min-width:110px;'>"
        f"<div style='font-size:22px;font-weight:bold;color:#64d8cb;'>₹ {total_funding:,}</div><div style='font-size:11px;color:#a3c2bc;text-transform:uppercase;'>Funding Pledged</div>"
        f"</div>"
        f"<div style='background:rgba(255,255,255,0.08);padding:12px 18px;border-radius:12px;text-align:center;min-width:110px;'>"
        f"<div style='font-size:22px;font-weight:bold;color:#ffd54f;'>{accepted_offers}</div><div style='font-size:11px;color:#a3c2bc;text-transform:uppercase;'>Active Pledges</div>"
        f"</div>"
        f"</div>"
        f"</div>"
        f"</div>"
    )
    
    # 2. Active Pledges & Collaboration Feed
    offer_cards = []
    for offer in offers:
        issue_id = offer["issue_id"]
        issue_team = next((t for t in teams if t["issue_id"] == issue_id), None)
        team_markup = ""
        if issue_team:
            milestones = load_milestones(issue_team["id"])
            m_items = []
            for m in milestones:
                t_res = f"<br><em>Testing: {html.escape(m['testing_result'])}</em>" if m.get('testing_result') else ""
                m_items.append(f"<li style='margin:4px 0;'><span style='font-weight:bold;'>{html.escape(m['title'])}</span> [{html.escape(m['status'])}] &mdash; <small>{html.escape(str(m['due_date'] or 'No deadline'))}</small>{t_res}</li>")
            m_markup = "".join(m_items)
            team_markup = (
                f"<div style='background:#f4f8f7;border-left:4px solid #317c91;padding:12px 16px;border-radius:6px;margin-top:12px;'>"
                f"<p style='margin:0 0 6px;font-size:13px;'><strong>University Team:</strong> {html.escape(issue_team['name'])} (Mentor: <em>{html.escape(issue_team['faculty_mentor'])}</em>) &middot; Stage: <span style='font-weight:bold;color:#317c91;'>{html.escape(issue_team['status'])}</span></p>"
                f"<details><summary style='cursor:pointer;font-size:12px;color:#667773;'>View Active Milestones ({len(milestones)})</summary><ul style='font-size:12px;margin:6px 0 0 16px;padding:0;'>{m_markup or '<li>No milestones defined</li>'}</ul></details>"
                f"</div>"
            )
            
        status_color = "#2b7a4b" if offer["status"] == "Accepted" else "#317c91" if offer["status"] == "Delivered" else "#b83226" if offer["status"] == "Declined" else "#c48622"
        funding_badge = f"<span style='background:#e8f5e9;color:#2e7d32;padding:3px 8px;border-radius:4px;font-weight:bold;font-size:12px;margin-left:8px;'>₹ {int(offer.get('funding_amount') or 0):,}</span>" if offer.get('funding_amount') else ""
        resources_line = f"<p style='font-size:12px;color:#667773;margin:4px 0;'><strong>Committed Resources:</strong> {html.escape(str(offer.get('resources') or ''))}</p>" if offer.get('resources') else ""
        timeline_line = f"<p style='font-size:12px;color:#667773;margin:4px 0;'><strong>Target Timeline:</strong> {html.escape(str(offer.get('timeline') or ''))}</p>" if offer.get('timeline') else ""
        commitment_line = f"<p style='font-size:12px;color:#2e7d32;margin:6px 0;background:#f1f8e9;padding:6px 10px;border-radius:6px;'><strong>Nodal / University Response:</strong> {html.escape(str(offer.get('commitment_note') or ''))}</p>" if offer.get('commitment_note') else ""
        
        offer_cards.append(
            f"<article style='background:#fffdf8;border:1px solid #dedbd1;border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 4px 12px rgba(23,43,40,0.04);'>"
            f"<div style='display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:8px;'>"
            f"<div>"
            f"<h3 style='margin:0 0 4px;font-size:18px;'>{html.escape(offer['title'])} <small style='color:#667773;font-size:13px;'>({html.escape(str(offer.get('district', '')))} &middot; {html.escape(str(offer.get('category', 'Civic')))})</small></h3>"
            f"<p style='margin:4px 0 8px;font-size:13px;'>Support Type: <strong>{html.escape(offer['support_type'])}</strong> {funding_badge}</p>"
            f"</div>"
            f"<span style='background:{status_color}18;color:{status_color};border:1px solid {status_color}40;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:bold;'>{html.escape(offer['status'])}</span>"
            f"</div>"
            f"<p style='color:#444;font-size:13px;line-height:1.5;background:#faf8f2;padding:10px 14px;border-radius:8px;margin:8px 0;'><strong>Details:</strong> {html.escape(offer['details'])}</p>"
            f"{resources_line}"
            f"{timeline_line}"
            f"{commitment_line}"
            f"{team_markup}"
            f"</article>"
        )
    offers_feed = "".join(offer_cards) if offer_cards else "<p style='color:#667773;'>No support offers submitted yet. Browse the societal challenges below to pledge mentorship, funding, or testing support.</p>"
    
    # 3. Societal Challenge & University R&D Explorer
    challenge_cards = []
    for issue in approved_issues:
        issue_id = issue["id"]
        assignment = assignments.get(issue_id)
        issue_team = next((t for t in teams if t["issue_id"] == issue_id), None)
        issue_reports = [r for r in reports if r["issue_id"] == issue_id]
        
        academic_info = ""
        if assignment:
            assigned_university = next((u for u in universities if u["id"] == assignment["university_id"]), None)
            uni_name = html.escape((assigned_university or {}).get("name") or "Assigned University")
            team_info = f"<br><strong>Faculty Mentor / Team:</strong> {html.escape(issue_team['faculty_mentor'])} &middot; Stage: <span style='color:#317c91;font-weight:bold;'>{html.escape(issue_team['status'])}</span>" if issue_team else "<br><em style='color:#667773;'>Team forming in progress</em>"
            academic_info = (
                f"<div style='background:#edf7f6;border-radius:8px;padding:12px;margin:10px 0;font-size:13px;'>"
                f"<strong>Assigned Institution:</strong> {uni_name} &middot; Status: <strong>{html.escape(assignment['status'])}</strong>"
                f"{team_info}"
                f"</div>"
            )
            
        reports_markup = ""
        if issue_reports:
            r_list = "".join(f"<div style='margin-bottom:6px;'><strong>{html.escape(r['title'])}</strong>: {html.escape(r['summary'][:180])}...</div>" for r in issue_reports)
            reports_markup = f"<details style='font-size:12px;color:#333;margin:8px 0;'><summary style='cursor:pointer;color:#317c91;font-weight:bold;'>View Academic Pilot Reports ({len(issue_reports)})</summary><div style='padding:8px;background:#f9f9f9;border-radius:6px;margin-top:4px;'>{r_list}</div></details>"
            
        challenge_cards.append(
            f"<article style='background:#fffdf8;border:1px solid #dedbd1;border-radius:12px;padding:22px;margin-bottom:20px;box-shadow:0 4px 14px rgba(23,43,40,0.05);'>"
            f"<div style='display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;'>"
            f"<div>"
            f"<span style='background:#fbe9e7;color:#d84315;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;text-transform:uppercase;'>{html.escape(issue.get('category', 'Civic Issue'))}</span>"
            f"<h3 style='margin:8px 0 4px;font-size:20px;'>{html.escape(issue['title'])}</h3>"
            f"<p style='color:#667773;font-size:13px;margin:0 0 8px;'>Location: <strong>{html.escape(issue.get('district', 'Jharkhand'))}</strong> &middot; {html.escape(str(issue.get('block', '')))} &middot; <strong style='color:#e65f38;'>{issue.get('supporters', 0)} citizen supporters</strong></p>"
            f"</div>"
            f"</div>"
            f"<p style='color:#333;font-size:14px;line-height:1.5;margin:8px 0 12px;'>{html.escape(issue.get('description', ''))}</p>"
            f"{industry_match_markup(partner, issue)}"
            f"{academic_info}"
            f"{reports_markup}"
            f"<details style='margin-top:14px;background:#fff;border:1px solid #e0ded6;border-radius:10px;padding:14px;'>"
            f"<summary style='cursor:pointer;font-weight:bold;color:#172b28;font-size:14px;'>+ Submit Support Offer: Pledge Support & Co-Development for this Challenge</summary>"
            f"<form data-endpoint='/api/industry/offers' style='margin-top:14px;display:grid;gap:10px;'>"
            f"<input type='hidden' name='issue_id' value='{issue_id}'>"
            f"<div style='display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:10px;'>"
            f"<div><label>Support Category</label><select name='support_type' required><option>Mentorship</option><option>Funding</option><option>Prototyping</option><option>Testing</option><option>Deployment</option><option>Co-development</option><option>Technology Transfer</option><option>Pilot Implementation</option></select></div>"
            f"<div><label>CSR / Seed Funding (₹ Optional)</label><input type='number' name='funding_amount' placeholder='e.g. 150000' min='0'></div>"
            f"<div><label>Committed Resources / Equipment</label><input name='resources' placeholder='e.g. Maker lab access, hardware components'></div>"
            f"<div><label>Target Timeline</label><input name='timeline' placeholder='e.g. 3-month prototype, 6-month pilot'></div>"
            f"</div>"
            f"<div><label>Support & Implementation Scope</label><textarea name='details' placeholder='Describe how your organization will support the student/faculty team with technical expertise, testing, funding, or deployment...' required style='min-height:75px;'></textarea></div>"
            f"<button type='submit' style='width:fit-content;'>Submit Support Pledge</button>"
            f"</form>"
            f"</details>"
            f"</article>"
        )
    challenges_feed = "".join(challenge_cards) if challenge_cards else "<p style='color:#667773;'>No approved challenges are currently awaiting industry partnership.</p>"

    # 4. Direct Institutional Communication
    messages_feed = render_messages(user)
    
    return (
        f"{profile_html}"
        f"<section class='section-card'>"
        f"<h2>1. Active Support Pledges & Co-Development Feed</h2>"
        f"<p style='color:#667773;font-size:13px;margin-bottom:18px;'>Track the real-time status of your contributions, university team milestones, and government commitment acknowledgments.</p>"
        f"{offers_feed}"
        f"</section>"
        f"<section class='section-card'>"
        f"<h2>2. Explore Challenges</h2>"
        f"<h3>University Innovations & Prototypes</h3>"
        f"<p style='color:#667773;font-size:13px;margin-bottom:18px;'>Browse citizen challenges validated by government moderation and paired with university student/faculty teams ready for industry partnership.</p>"
        f"{challenges_feed}"
        f"</section>"
        f"<section class='section-card'>"
        f"<h2>3. Institutional Communications & Direct Messaging</h2>"
        f"<p style='color:#667773;font-size:13px;margin-bottom:18px;'>Communicate directly with University Faculty Mentors and Government Nodal Officers.</p>"
        f"{messages_feed}"
        f"</section>"
    )
def render_government_dashboard():
    metrics = load_dashboard_metrics()
    moderation = "".join(f"<li>{html.escape(str(row['status']))}: {row['total']}</li>" for row in metrics["moderation"])
    distribution = "".join(f"<li>{html.escape(str(row['district']))} · {html.escape(str(row['category']))}: {row['total']}</li>" for row in metrics["district_domains"])
    stages = "".join(f"<li>{html.escape(str(row['status']))}: {row['total']}</li>" for row in metrics["project_stages"])
    district_totals = {}
    domain_totals = {}
    for row in metrics["district_domains"]:
        district = str(row.get("district") or "Unknown")
        domain = str(row.get("category") or "General")
        total = int(row.get("total", 0))
        district_totals[district] = district_totals.get(district, 0) + total
        domain_totals[domain] = domain_totals.get(domain, 0) + total

    def chart_rows(totals, color):
        maximum = max(totals.values(), default=0)
        return "".join(
            f"<div class='chart-row'><div class='chart-label'><span>{html.escape(label)}</span><strong>{total}</strong></div><div class='chart-track'><span class='chart-bar' style='width:{(total / maximum * 100) if maximum else 0:.1f}%;background:{color}'></span></div></div>"
            for label, total in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        ) or "<p class='chart-empty'>No data</p>"

    def pie_chart(totals):
        ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        total = sum(totals.values())
        if not total:
            return "<p class='chart-empty'>No data</p>"
        colors = ["#e65f38", "#317c91", "#c48622", "#4b8f67", "#8b6f9f", "#d75b47", "#5d7891"]
        segments = []
        legend = []
        start = 0.0
        for index, (label, count) in enumerate(ordered):
            end = start + (count / total * 100)
            color = colors[index % len(colors)]
            segments.append(f"{color} {start:.2f}% {end:.2f}%")
            legend.append(f"<div class='pie-legend-row'><span class='pie-swatch' style='background:{color}'></span><span>{html.escape(label)}</span><strong>{count} ({count / total * 100:.0f}%)</strong></div>")
            start = end
        return f"<div class='pie-layout'><div class='pie-chart' style=\"background:conic-gradient({', '.join(segments)})\"></div><div class='pie-legend'>{''.join(legend)}</div></div>"

    distribution_chart = (
        "<div class='chart-grid'>"
        f"<div class='chart-panel'><h3>Issues by district</h3>{chart_rows(district_totals, 'var(--blue)')}</div>"
        f"<div class='chart-panel'><h3>Issues by domain</h3>{pie_chart(domain_totals)}</div>"
        "</div>"
    )
    stage_totals = {str(row.get("status") or "Unknown"): int(row.get("total", 0)) for row in metrics["project_stages"]}
    stages_chart = f"<div class='chart-panel'><h3>Teams by project stage</h3>{chart_rows(stage_totals, 'var(--gold)')}</div>"
    responses = load_university_assignment_responses()
    response_items = []
    for resp in responses:
        status_color = "#2b7a4b" if resp["status"] == "Accepted" else "#b83226" if resp["status"] == "Rejected" else "#c48622"
        response_items.append(
            f"<li style='margin-bottom:10px;padding:10px;border-bottom:1px solid #eee;'>"
            f"<strong>{html.escape(resp['university_name'])}</strong> "
            f"· Issue: <em>{html.escape(resp['issue_title'])}</em> ({html.escape(resp['issue_district'])})<br>"
            f"Request Status: <span style='color:{status_color};font-weight:bold;'>{html.escape(resp['status'])}</span> "
            f"· Decision Reason: <strong>{html.escape(str(resp.get('response_reason') or 'No reason provided'))}</strong> "
            f"<br><small style='color:#666;'>Assigned at: {resp['assigned_at']}</small></li>"
        )
    responses_markup = "".join(response_items) or "<li>No university assignment decisions logged yet</li>"
    return (
        f"<h1>Government Dashboard</h1><p>Jharkhand societal innovation overview and institutional response tracking.</p>"
        f"<section><h2>Totals</h2><p>Issues: {metrics['total_issues']} · Proposals: {metrics['proposals']} · Assignments: {metrics['assignments']} · Universities: {metrics['universities']} · Industry partners: {metrics['industry_partners']} · Support offers: {metrics['support_offers']}</p></section>"
        f"<section><h2>University Request Responses & Decisions (Accept/Reject Feed)</h2><ul>{responses_markup}</ul></section>"
        f"<section><h2>Moderation</h2><ul>{moderation or '<li>No issue data</li>'}</ul></section>"
        f"<section><h2>District and domain distribution</h2><div>{distribution_chart or '<p>No issue data</p>'}</div><details><summary>View data list</summary><ul>{distribution or '<li>No issue data</li>'}</ul></details></section>"
        f"<section><h2>Project progress</h2><div>{stages_chart or '<p>No project teams</p>'}</div><details><summary>View data list</summary><ul>{stages or '<li>No project teams</li>'}</ul></details></section>"
    )
def notification_markup(user):
    notifications = load_notifications(user)
    if not notifications:
        return "<h2>Notifications</h2><p>No notifications.</p>"
    return "<h2>Notifications</h2>" + "".join(f"<p>{html.escape(item['message'])}  {html.escape(str(item['created_at']))}</p>" for item in notifications)
def known_recipients():
    return {"admin@jharkhand.gov.in", "citizen@example.com", "engineer@example.gov"} | {str(item.get("contact_email")) for item in load_universities() if item.get("contact_email")} | {str(item.get("contact_email")) for item in load_industry_partners() if item.get("contact_email")}
def render_messages(user):
    messages = load_messages(user)
    history = "".join(f"<article><p><strong>{html.escape(item['sender'])}</strong> to <strong>{html.escape(item['recipient'])}</strong></p><p>{html.escape(item['message'])}</p><small>{html.escape(str(item['created_at']))}</small></article>" for item in messages) or "<p>No messages yet.</p>"
    return f"<h1>Project messages</h1>{history}<form id='message-form'><input name='recipient' placeholder='Recipient email' required><textarea name='message' placeholder='Write a project message' required></textarea><input name='related_id' type='number' placeholder='Issue or project ID'><button>Send message</button></form>"
def render_user_issues(user):
    issues = load_user_issues(user)
    if not issues:
        return '<div class="empty-state"><h3>No Civic Issues Reported</h3><p>You have not submitted any issue reports yet. Use the Live Map to report local problems.</p></div>'
    cards = []
    for issue in issues:
        proposals = [proposal for proposal in PROPOSALS if proposal.get("issue_id") == issue["id"]]
        proposal_text = ", ".join(f"{proposal['title']} ({proposal['status']})" for proposal in proposals) or "No proposals submitted"
        mod_status = str(issue.get("moderation_status", "Pending"))
        status_class = f"badge-{mod_status.lower()}" if mod_status in {"Approved", "Pending", "Rejected", "Archived"} else "badge-pending"
        contractor_image = ""
        if issue.get("contractor_assignment_id") and issue.get("contractor_progress_image_type"):
            assignment_id = issue["contractor_assignment_id"]
            contractor_image = (
                f"<div class='contractor-progress' style='margin-top:16px;padding-top:14px;border-top:1px solid var(--line)'>"
                f"<strong>Contractor progress photo</strong>"
                f"<a href='/public-contractor-progress/{assignment_id}' target='_blank' rel='noopener'>"
                f"<img src='/public-contractor-progress/{assignment_id}' alt='Latest progress photo for {html.escape(issue['title'])}' style='display:block;max-width:100%;width:420px;margin-top:10px;border-radius:8px;border:1px solid var(--line)'>"
                f"</a></div>"
            )
        contractor_update = ""
        if issue.get("contractor_assignment_id"):
            contractor_status = html.escape(str(issue.get("contractor_assignment_status") or "Assigned"))
            contractor_name = html.escape(str(issue.get("contractor_name") or "Assigned contractor"))
            contractor_note = issue.get("contractor_completion_note")
            note_markup = f"<p><strong>Update:</strong> {html.escape(str(contractor_note))}</p>" if contractor_note else ""
            contractor_update = (
                f"<div class='contractor-progress' style='margin-top:16px;padding-top:14px;border-top:1px solid var(--line)'>"
                f"<strong>Contractor progress: {contractor_name} · {contractor_status}</strong>{note_markup}</div>"
            )
        cards.append(
            f'<article class="issue-card">'
            f'<div class="issue-top"><h3 class="issue-title">{html.escape(issue["title"])}</h3>'
            f'<span class="badge {status_class}">{html.escape(mod_status)}</span></div>'
            f'<p class="issue-desc">{html.escape(issue.get("description", ""))}</p>'
            f'<div class="issue-meta">'
            f'<span class="issue-meta-item">District: <strong>{html.escape(issue.get("district", "Ranchi"))}</strong></span>'
            f'<span class="issue-meta-item">Block: <strong>{html.escape(issue.get("block", "N/A"))}</strong></span>'
            f'<span class="issue-meta-item">Category: <strong>{html.escape(issue.get("category", ""))}</strong></span>'
            f'<span class="issue-meta-item">University: <strong>{html.escape(issue.get("university_name") or "Not assigned")}</strong></span>'
            f'<span class="issue-meta-item">Stage: <strong>{html.escape(issue.get("team_status") or "Pending assignment")}</strong></span>'
            f'<span class="issue-meta-item">Solutions: <strong>{html.escape(proposal_text)}</strong></span>'
            f'</div>'
            f'{contractor_update}'
            f'{contractor_image}'
            + (f"<form class='contractor-complaint-form' data-issue-id='{issue['id']}' data-contractor-id='{issue['contractor_id']}' style='margin-top:16px;padding-top:14px;border-top:1px solid var(--line)'>"
               f"<strong>Report this contractor</strong> <span style='color:var(--muted);font:12px Arial,sans-serif'>Your complaint will be reviewed by contractor administration.</span>"
               f"<select name='complaint_type' required><option value='' disabled selected>Choose complaint type</option><option>Poor quality work</option><option>Incomplete work</option><option>Unsafe work</option><option>Delay</option><option>Other</option></select>"
               f"<textarea name='description' required minlength='10' placeholder='Describe the problem with this road/project'></textarea>"
               f"<button type='submit'>File Complaint</button></form>" if issue.get('contractor_id') else '')
            + f'</article>'
        )
    return "".join(cards) + "<script>document.querySelectorAll('.contractor-complaint-form').forEach(form=>form.addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));data.issue_id=form.dataset.issueId;data.contractor_id=form.dataset.contractorId;const response=await fetch('/api/complaints/contractor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(response.ok){alert('Complaint filed for contractor administration review.');location.reload();}else{alert((await response.json()).message||'Complaint failed');}}));</script>"
def render_admin_proposals():
    pending = [proposal for proposal in PROPOSALS if proposal.get("moderation_status", "Pending") == "Pending"]
    if not pending:
        return "<h2>Proposal moderation</h2><p>No pending proposals.</p>"
    cards = ["<h2>Proposal moderation</h2>"]
    for proposal in pending:
        cards.append(
            f"<article class='moderation-card'><h3>{html.escape(str(proposal.get('title', 'Untitled proposal')))}</h3>"
            f"<p>{html.escape(str(proposal.get('description', '')))}</p>"
            f"<form class='proposal-moderation'><input type='hidden' name='proposal_id' value='{proposal['id']}'>"
            f"<textarea name='reason' placeholder='Reason for this decision' required></textarea>"
            f"<button name='status' value='Approved'>Approve</button><button name='status' value='Rejected'>Reject</button><button name='status' value='Archived'>Archive</button></form></article>"
        )
    return "".join(cards)

def render_admin_issues():
    pending = [issue for issue in ISSUES if issue.get("moderation_status", "Pending") == "Pending"]
    if not pending:
        return "<p>No pending issues.</p>" + render_admin_proposals()
    return "".join(
        f"<article class='moderation-card'><h2>{html.escape(str(issue.get('title', 'Untitled issue')))}</h2><p>{html.escape(str(issue.get('description', '')))}</p><p>{html.escape(str(issue.get('district', 'Ranchi')))} {html.escape(str(issue.get('block', '')))} {html.escape(str(issue.get('category', '')))}</p><form><input type='hidden' name='issue_id' value='{issue['id']}'><textarea name='reason' placeholder='Reason for this decision' required></textarea><button name='status' value='Approved'>Approve</button><button name='status' value='Rejected'>Reject</button></form></article>"
        for issue in pending
    ) + render_admin_proposals()

def render_industry_admin():
    partners = load_industry_partners()
    offers = load_all_partner_offers()
    pending_count = sum(1 for partner in partners if partner.get('approval_status', 'Active') == 'Pending')
    partner_markup = "".join(f"<article class='partner-card'><div class='partner-heading'><div><p class='eyebrow'>Partner request</p><h3>{html.escape(partner['name'])}</h3><p>{html.escape(partner['partner_type'])} · {html.escape(partner['district'])}</p></div><span class='approval-badge approval-{str(partner.get('approval_status', 'Active')).lower()}'>{html.escape(partner.get('approval_status', 'Active'))}</span></div><p class='partner-meta'><strong>Domains:</strong> {html.escape(partner['domains'])}<br><strong>Contact:</strong> {html.escape(partner['contact_email'])}</p><form class='approval' data-kind='industry' data-id='{partner['id']}'><label>Decision<select name='status'><option {'selected' if partner.get('approval_status', 'Active') == 'Active' else ''}>Active</option><option {'selected' if partner.get('approval_status') == 'Rejected' else ''}>Rejected</option><option {'selected' if partner.get('approval_status') == 'Pending' else ''}>Pending</option></select></label><button type='submit'>Save decision</button></form></article>" for partner in partners) or "<p class='empty-state'>No industry partner registrations yet.</p>"
    offer_markup = "".join(f"<article class='commitment-card'><p><strong>{html.escape(offer['partner_name'])}</strong> offered {html.escape(offer['support_type'])} for {html.escape(offer['title'])}</p><form class='offer-update'><input type='hidden' name='offer_id' value='{offer['id']}'><select name='status'><option>Offered</option><option>Accepted</option><option>Delivered</option><option>Declined</option></select><input name='note' placeholder='Commitment note'><button type='submit'>Update commitment</button></form></article>" for offer in offers) or "<p class='empty-state'>No support offers yet.</p>"
    return f"<div class='industry-admin-shell'><div class='admin-portal-bar'><div class='admin-portal-title'>Government workspace</div><nav class='admin-portal-links'><a href='/admin'>Moderation</a><a class='active' href='/industry-admin'>Industry partners</a><a href='/universities'>Universities</a><a href='/government-dashboard'>Analytics</a></nav></div><div class='admin-intro'><p class='eyebrow'>Industry verification</p><h1>Review industry partner requests.</h1><p>Approve organizations before they access approved civic challenges and submit support commitments.</p></div><div class='admin-stats'><div><strong>{pending_count}</strong><span>Pending requests</span></div><div><strong>{len(partners)}</strong><span>Total partners</span></div><div><strong>{len(offers)}</strong><span>Support offers</span></div></div><section class='admin-section'><div class='section-heading'><div><p class='eyebrow'>Onboarding queue</p><h2>Partner registrations</h2></div><span class='queue-label'>{pending_count} awaiting review</span></div><div class='partner-grid'>{partner_markup}</div></section><section class='admin-section'><p class='eyebrow'>Collaboration monitoring</p><h2>Support commitments</h2><div class='commitment-list'>{offer_markup}</div></section><section class='admin-section'><p class='eyebrow'>Manual onboarding</p><h2>Register a partner</h2><form class='industry-create admin-form'><input name='name' placeholder='Organization name' required><select name='partner_type'><option>Industry</option><option>Startup</option><option>MSME</option><option>CSR Organization</option><option>Research Laboratory</option></select><input name='district' placeholder='District' required><input name='domains' placeholder='Domains' required><input name='contact_email' type='email' placeholder='Contact email' required><button type='submit'>Register partner</button></form></section></div>"
def render_university_issues():
    universities = load_universities()
    assignments = load_assignments()
    directory = "<h2>University registration</h2><form class='university-create'><input name='name' placeholder='University name' required><input name='district' placeholder='District' required><input name='domains' placeholder='Domains' required><input name='expertise' placeholder='Expertise keywords' required><input name='departments' placeholder='Departments'><input name='laboratories' placeholder='Laboratories'><input name='incubation_facilities' placeholder='Incubation facilities'><input name='contact_email' placeholder='Contact email' required><button type='submit'>Register university</button></form><h2>University profiles</h2>" + "".join(
        f"<form class='university-profile'><input type='hidden' name='university_id' value='{university['id']}'><input name='name' value='{html.escape(university['name'])}' required><input name='district' value='{html.escape(university['district'])}' required><input name='domains' value='{html.escape(university['domains'])}' required><input name='expertise' value='{html.escape(university.get('expertise') or '')}' placeholder='Expertise keywords'><input name='departments' value='{html.escape(university.get('departments') or '')}' placeholder='Departments'><input name='laboratories' value='{html.escape(university.get('laboratories') or '')}' placeholder='Laboratories'><input name='incubation_facilities' value='{html.escape(university.get('incubation_facilities') or '')}' placeholder='Incubation facilities'><input name='contact_email' value='{html.escape(university.get('contact_email') or '')}'><button type='submit'>Save profile</button></form><form class='approval' data-kind='university' data-id='{university['id']}'><span>Approval: {html.escape(university.get('approval_status', 'Active'))}</span><select name='status'><option>Active</option><option>Rejected</option><option>Pending</option></select><button>Save approval</button></form>"
        for university in universities
    )
    approved = [issue for issue in ISSUES if issue.get("moderation_status", "Pending") == "Approved"]
    if not approved:
        return directory + "<p>No approved issues are ready for university assignment.</p>"
    options = "".join(f"<option value='{university['id']}'>{html.escape(university['name'])} ({html.escape(university['district'])})</option>" for university in universities)
    cards = []
    teams = load_teams()
    for issue in approved:
        assignment = assignments.get(issue["id"])
        issue_district = str(issue.get("district", "")).casefold()
        issue_domain = str(issue.get("category", "")).casefold()
        ranked_universities = sorted(universities, key=lambda university: university_issue_score(university, issue), reverse=True)
        recommended = ranked_universities[0] if ranked_universities and university_issue_score(ranked_universities[0], issue) > 0 else None
        recommendation = f"<p><strong>AI recommended:</strong> {html.escape(recommended['name'])} based on district, domain, and expertise match.</p>" if recommended else ""
        current = f"<p>Assigned to university ID {assignment['university_id']} ({html.escape(assignment['status'])}).</p><p>{html.escape(str(assignment.get('response_reason') or ''))}</p><form class='response'><input type='hidden' name='issue_id' value='{issue['id']}'><select name='status'><option>Accepted</option><option>Rejected</option><option>Needs clarification</option></select><input name='reason' placeholder='University response' required><button type='submit'>Save response</button></form>" if assignment else "<p>Not assigned.</p>"
        issue_teams = [team for team in teams if team["issue_id"] == issue["id"]]
        team_markup = "".join(render_dashboard_team(team) for team in issue_teams)
        cards.append(f"<article><h2>{html.escape(str(issue['title']))}</h2><p>{html.escape(str(issue.get('description', '')))}</p><p>{html.escape(str(issue.get('district', 'Ranchi')))} {html.escape(str(issue.get('block', '')))} {html.escape(str(issue.get('category', '')))}</p>{recommendation}{current}<form class='assignment'><input type='hidden' name='issue_id' value='{issue['id']}'><select name='university_id' required>{options}</select><button type='submit'>Assign university</button></form>{team_markup}<form class='team'><input type='hidden' name='issue_id' value='{issue['id']}'><input type='hidden' name='university_id' value='{assignment['university_id'] if assignment else ''}'><input name='name' placeholder='Team name' required><input name='faculty_mentor' placeholder='Faculty mentor email' required><input name='members' placeholder='Student emails, comma separated' required><button type='submit'>Create project team</button></form></article>")
    return directory + "".join(cards)
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
    "<label>Photo proof<input name=\"proof_image\" type=\"file\" accept=\"image/jpeg,image/png,image/webp\"><small>Geotagged photos receive a location verification badge.</small></label>",
    "<label>Geotagged photo<input name=\"proof_image\" type=\"file\" accept=\"image/jpeg,image/png,image/webp\"><small>Optional JPEG, PNG, or WebP. GPS in the photo verifies the map pin.</small></label><label>Video evidence<input name=\"proof_video\" type=\"file\" accept=\"video/mp4,video/webm\"><small>Optional MP4 or WebM. Not geotagged. Used as evidence; CLIP ViT reads the problem type from sampled frames.</small></label>",
).replace(
    "description:form.get('description'),area:'New report',lat:reportLocation.lat,lng:reportLocation.lng,proof_image:proofImage",
    "description:form.get('description'),area:form.get('block')||form.get('district'),district:form.get('district'),block:form.get('block'),lat:reportLocation.lat,lng:reportLocation.lng,proof_image:proofImage",
).replace(
    "alert('Your issue was added to the map.')",
    "alert(result.assignment?`Your issue was added and matched with ${result.assignment.university_name}.`:'Your issue was added to the map. AI will match it when a suitable university is available.')",
)
PAGE = PAGE.replace(
    "document.getElementById('report').onsubmit=async event=>{event.preventDefault();",
    "document.getElementById('report').onsubmit=async event=>{event.preventDefault();fetch('http://127.0.0.1:7702/ingest/a50f380c-436d-456f-97e8-f1ef4c5069f0',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'0d8a0a'},body:JSON.stringify({sessionId:'0d8a0a',hypothesisId:'C',location:'map.py:report.onsubmit',message:'report form submit',data:{hasProof:!!(event.target.proof_image&&event.target.proof_image.files&&event.target.proof_image.files[0]),proofType:(event.target.proof_image&&event.target.proof_image.files[0]&&event.target.proof_image.files[0].type)||'',proofSize:(event.target.proof_image&&event.target.proof_image.files[0]&&event.target.proof_image.files[0].size)||0,hasVideoField:!!event.target.proof_video,videoType:(event.target.proof_video&&event.target.proof_video.files&&event.target.proof_video.files[0]&&event.target.proof_video.files[0].type)||''},timestamp:Date.now(),runId:'pre-fix'})}).catch(()=>{});",
    1,
)
PAGE = PAGE.replace(
    "</style>",
    ".map-search{display:grid;gap:6px;margin:0 0 14px;padding:12px;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,.65)}.map-search label{font:700 11px Arial,sans-serif;letter-spacing:.8px;text-transform:uppercase;color:var(--muted)}.map-search input{margin:0;background:var(--card)}.search-hint{font:11px Arial,sans-serif;color:var(--muted)}</style>",
    1,
)
PAGE = PAGE.replace(
    '<h2>Browse issues</h2><div id="filters" class="filters"></div>',
    '<h2>Browse issues</h2><div class="map-search"><label for="map-search">Search the map</label><input id="map-search" type="search" placeholder="Issue, district, category..." autocomplete="off"><div id="search-hint" class="search-hint">Search results update as you type.</div></div><div id="filters" class="filters"></div>',
    1,
)
PAGE = PAGE.replace("let selectedCategory='All';", "let selectedCategory='All';let searchQuery='';", 1)
PAGE = PAGE.replace(
    "const visible=issues.filter(i=>selectedCategory==='All'||i.category===selectedCategory);",
    "const visible=issues.filter(i=>(selectedCategory==='All'||i.category===selectedCategory)&&(!searchQuery||[i.title,i.description,i.category,i.district,i.block,i.area].some(value=>String(value||'').toLowerCase().includes(searchQuery))));",
    1,
)
PAGE = PAGE.replace(
    "document.getElementById('supporters').textContent=visible.reduce((sum,i)=>sum+(i.supporters||0),0)}",
    "document.getElementById('supporters').textContent=visible.reduce((sum,i)=>sum+(i.supporters||0),0);document.getElementById('search-hint').textContent=searchQuery?`${visible.length} matching issue${visible.length===1?'':'s'}`:'Search results update as you type.'}",
    1,
)
PAGE = PAGE.replace(
    "function buildFilters(){",
    "document.getElementById('map-search').addEventListener('input',event=>{searchQuery=event.target.value.trim().toLowerCase();render()});function buildFilters(){",
    1,
)
# #region agent log
try:
    import time
    with open(BASE_DIR / "debug-0d8a0a.log", "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"sessionId":"0d8a0a","hypothesisId":"C","location":"map.py:PAGE","message":"report form fields after replace","data":{"has_proof_image":"name=\"proof_image\"" in PAGE,"has_proof_video":"name=\"proof_video\"" in PAGE,"mixed_accept":"video/mp4" in PAGE and "name=\"proof_video\"" not in PAGE,"popup_has_video_tag":"<video src=" in PAGE},"timestamp":int(time.time()*1000),"runId":"pre-fix"})+"\n")
except Exception:
    pass
# #endregion
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
        output.append(f'<article class="issue"><div class="rank">#{index} {html.escape(str(issue.get("category","Other")))}</div><h2>{html.escape(str(issue.get("title","Untitled issue")))}</h2><p>{html.escape(str(issue.get("description","")))}</p><p><strong>{issue.get("supporters",0)} supporters</strong> {html.escape(str(issue.get("area","Nearby")))}</p><small>Issue ID: {issue_id}</small></article>')
    return "".join(output)
def render_proposal_options():
    if not ISSUES:
        return '<option value="">No issues available</option>'
    ranked = sorted(ISSUES,key=lambda issue: issue.get("supporters",0),reverse=True)
    options = []
    for index, issue in enumerate(ranked, start=1):
        issue_id = issue.get("id", index)
        options.append(f'<option value="{issue_id}">{html.escape(str(issue.get("title","Untitled issue")))} {issue.get("supporters",0)} supporters</option>')
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
    page = page.replace("__USER__", html.escape(user))
    page = page.replace("__ISSUES__", render_proposal_issues())
    page = page.replace("__OPTIONS__", render_proposal_options())
    page = page.replace("__PROPOSALS__", render_proposals())
    page = page.replace("__MESSAGE__", "")
    page = page.replace("__NAV__", render_role_nav(user, "proposals"))
    return page
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
        if path == "/templates/shared.css":
            self.send_payload((BASE_DIR / "templates" / "shared.css").read_bytes(), content_type="text/css; charset=utf-8")
            return
        if path == "/login":
            self.send_html(load_login_page(""))
            return
        if path == "/industry/login" or path == "/industry-login":
            self.send_html(load_industry_login_page(""))
            return
        if path == "/industry/register" or path == "/industry-register":
            self.send_html(load_industry_register_page(""))
            return
        if path == "/contractor/login" or path == "/contractor-login":
            self.send_html(load_contractor_login_page(""))
            return
        if path == "/contractor/register" or path == "/contractor-register":
            self.send_html(load_contractor_register_page(""))
            return
        if path == "/university/login" or path == "/university-login":
            self.send_html(load_university_login_page(""))
            return
        if path == "/university/register" or path == "/university-register":
            self.send_html(load_university_register_page(""))
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
        if path.startswith("/video/"):
            video_id = path.split("/",2)[2]
            video = get_video(video_id)
            if video is None:
                self.send_error(404)
                return
            self.send_payload(video[1],content_type=video[0])
            return
        if path.startswith("/public-contractor-progress/"):
            try:
                assignment_id = int(path.split("/", 2)[2])
            except (IndexError, ValueError):
                self.send_error(404)
                return
            image = get_contractor_progress_image(assignment_id)
            if image is None:
                self.send_error(404)
                return
            self.send_payload(image[1], content_type=image[0])
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
            user = self.session_user() or ""
            community_page = render_page(user, latitude, longitude)
            community_page = community_page.replace("__NAV__", render_role_nav(user, "community"))
            self.send_html(community_page)
            return
        if path == "/api/notifications":
            user = self.session_user()
            if user is None:
                self.send_json({"message": "Authentication required."}, status=401)
                return
            notifications = load_notifications(user)
            safe_notifications = [
                {
                    "id": item.get("id"),
                    "message": str(item.get("message", "")),
                    "related_type": item.get("related_type", ""),
                    "related_id": item.get("related_id"),
                    "is_read": bool(item.get("is_read", False)),
                    "created_at": str(item.get("created_at", "")),
                }
                for item in notifications
            ]
            unread_count = sum(1 for item in safe_notifications if not item["is_read"])
            self.send_json({
                "notifications": safe_notifications,
                "unread_count": unread_count,
            })
            return
        if path == "/notifications":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            notifications = load_notifications(user)
            cards = []
            for item in notifications:
                unread_class = " unread" if not item.get("is_read", False) else ""
                cards.append(
                    f"<div class='section-card notification-page-item{unread_class}'>"
                    f"<strong>{html.escape(str(item.get('message', '')))}</strong>"
                    f"<p class='muted'>{html.escape(str(item.get('created_at', '')))}</p>"
                    f"</div>"
                )
            content = "".join(cards) or (
                "<div class='empty-state'><h3>No notifications yet</h3>"
                "<p>Project and collaboration updates will appear here.</p></div>"
            )
            page = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Notifications</title>"
                "<link rel='stylesheet' href='/templates/shared.css'>"
                "<style>.notification-page{max-width:1100px;margin:30px auto;padding:0 18px}"
                ".notification-page .top-nav{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:22px}"
                ".notification-page-item.unread{border-left:4px solid #2b6cb0}</style>"
                "</head><body><main class='notification-page'>"
                f"<nav class='top-nav'>{render_role_nav(user, 'notifications')}</nav>"
                "<div class='section-card'><p class='eyebrow'>Updates</p>"
                "<h1>Notifications</h1><p class='muted'>Project and collaboration activity for your account.</p>"
                f"{content}</div></main></body></html>"
            )
            self.send_html(page)
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
            admin_page = ADMIN_PAGE_FILE.read_text(encoding="utf-8")
            content = render_admin_issues() + render_industry_admin()
            self.send_html(admin_page.replace("__ISSUES__", content))
            return
        if path == "/industry-admin":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            template = INDUSTRY_ADMIN_PAGE_FILE.read_text(encoding="utf-8")
            template = template.replace("__USER__", html.escape(user))
            self.send_html(template)
            return
            return
        if path == "/universities":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not is_admin(user):
                self.send_error(403)
                return
            template = UNIVERSITY_ADMIN_PAGE_FILE.read_text(encoding="utf-8")
            self.send_html(template.replace("__ISSUES__", render_university_issues()))
            return
        if path == "/citizen-dashboard" or path == "/my-issues":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not user_can_access_portal(user, "citizen"):
                self.send_error(403)
                return
            template = CITIZEN_PAGE_FILE.read_text(encoding="utf-8")
            self.send_html(
                template.replace("__USER__", html.escape(user))
                .replace("__ISSUES__", render_user_issues(user))
                .replace("__NAV__", render_role_nav(user, "citizen"))
            )
            return
        if path == "/university-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not user_can_access_portal(user, "university"):
                self.send_error(403)
                return
            self.send_html(render_university_dashboard(user).replace("__NAV__", render_role_nav(user, "university")))
            return
        if path == "/industry-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not user_can_access_portal(user, "industry"):
                self.send_error(403)
                return
            self.send_html(render_industry_dashboard(user).replace("__NAV__", render_role_nav(user, "industry")))
            return
        if path == "/contractor-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/contractor/login")
                return
            if not user_can_access_portal(user, "contractor"):
                self.send_error(403)
                return
            template = CONTRACTOR_DASHBOARD_FILE.read_text(encoding="utf-8")
            self.send_html(
                template.replace("__CONTENT__", render_contractor_dashboard(user))
                .replace("__NAV__", render_role_nav(user, "contractor"))
            )
            return
        if path == "/contractor-admin":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not is_admin(user):
                self.send_error(403)
                return
            template = CONTRACTOR_ADMIN_FILE.read_text(encoding="utf-8")
            self.send_html(template.replace("__CONTENT__", render_contractor_admin()))
            return
        if path == "/government-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not user_can_access_portal(user, "government"):
                self.send_error(403)
                return
            template = GOVERNMENT_DASHBOARD_FILE.read_text(encoding="utf-8")
            self.send_html(
                template.replace("__CONTENT__", render_government_dashboard())
                .replace("__NAV__", render_role_nav(user, "government"))
            )
            return
        if path not in ("/","/index.html"):
            self.send_error(404)
            return
        user = self.session_user()
        if user is None:
            self.redirect("/login")
            return
        issues_json = json.dumps(ISSUES).replace("</", "<\\/")
        template = MAIN_MAP_PAGE_FILE.read_text(encoding="utf-8")
        district_options = "".join(f"<option>{html.escape(district)}</option>" for district in JHARKHAND_DISTRICTS)
        domain_options = "".join(f"<option>{html.escape(domain)}</option>" for domain in JHARKHAND_DOMAINS)
        payload = (
            template
            .replace("__ISSUES__", issues_json)
            .replace("__USER__", html.escape(user))
            .replace("__DISTRICT_OPTIONS__", district_options)
            .replace("__DOMAIN_OPTIONS__", domain_options)
            .replace("__NAV__", render_role_nav(user, "map"))
            .encode("utf-8")
        )
        self.send_payload(payload)
    def do_POST(self) -> None:
        global NEXT_PROPOSAL_ID
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        if not check_rate_limit(client_ip, max_requests=60, window_seconds=60):
            self.send_json({"message": "Rate limit exceeded. Please wait a minute."}, status=429)
            return
        path = urlsplit(self.path).path
        if path == "/university/login" or path == "/university-login":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = parse_qs(body)
            email = data.get("email", [""])[0].strip().lower()
            password = data.get("password", [""])[0]
            if not authenticate(email, password):
                self.send_html(load_university_login_page("Email or password is incorrect."), status=401)
                return
            university = next((item for item in load_universities() if str(item.get("contact_email", "")).casefold() == email.casefold()), None)
            if university is None:
                self.send_html(load_university_login_page("This account is not linked to a registered university profile."), status=403)
                return
            if university.get("approval_status", "Active") != "Active":
                status = university.get("approval_status", "Pending").lower()
                self.send_html(load_university_login_page(f"Your university registration is {status}. An administrator must approve it before dashboard access."), status=403)
                return
            session_id = create_session_record(email)
            SESSIONS[session_id] = email
            self.redirect("/university-dashboard", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
            return
        if path == "/industry/login" or path == "/industry-login":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            email = form.get("email", [""])[0].strip().lower()
            password = form.get("password", [""])[0]
            if not authenticate(email, password):
                self.send_html(load_industry_login_page('<p class="error">Email or password is incorrect.</p>'), status=401)
                return
            if industry_for_user(email) is None:
                self.send_html(load_industry_login_page('<p class="error">This account is not linked to an approved industry partner profile. Registration must be approved by an administrator.</p>'), status=403)
                return
            session_id = create_session_record(email)
            SESSIONS[session_id] = email
            self.redirect("/industry-dashboard", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
            return
        if path == "/industry/register" or path == "/industry-register":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            email = form.get("email", [""])[0].strip().lower()
            password = form.get("password", [""])[0]
            confirm_password = form.get("confirm_password", [""])[0]
            values = {"name": form.get("name", [""])[0].strip()[:255], "partner_type": form.get("partner_type", [""])[0].strip()[:50], "district": form.get("district", [""])[0].strip()[:100], "domains": form.get("domains", [""])[0].strip()[:1000], "contact_email": email}
            if password != confirm_password:
                self.send_html(load_industry_register_page('<p class="error">Passwords do not match.</p>'), status=400)
                return
            if not all(values.values()) or "@" not in email:
                self.send_html(load_industry_register_page('<p class="error">Organization, type, district, domains, and a valid email are required.</p>'), status=400)
                return
            if any(str(partner.get("contact_email", "")).casefold() == email.casefold() for partner in load_industry_partners()):
                self.send_html(load_industry_register_page('<p class="error">An industry profile already uses this email.</p>'), status=400)
                return
            created, message = create_account(email, password)
            if not created:
                self.send_html(load_industry_register_page(f'<p class="error">{html.escape(message)}</p>'), status=400)
                return
            try:
                create_industry_partner(**values)
            except Exception:
                self.send_html(load_industry_register_page('<p class="error">The organization profile could not be created.</p>'), status=400)
                return
            self.send_html(load_industry_register_page('<p class="success">Registration submitted. An administrator must approve your organization before you can sign in.</p>'))
            return
        if path == "/contractor/login" or path == "/contractor-login":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            email = form.get("email", [""])[0].strip().lower()
            password = form.get("password", [""])[0]
            if not authenticate(email, password):
                self.send_html(load_contractor_login_page('<p class="message error">Email or password is incorrect.</p>'), status=401)
                return
            contractor = contractor_for_user(email)
            if contractor is None:
                self.send_html(load_contractor_login_page('<p class="message error">This account is not linked to a registered contractor profile.</p>'), status=403)
                return
            if contractor.get("approval_status") == "Pending":
                self.send_html(load_contractor_login_page('<p class="message error">Your registration is pending administrator approval.</p>'), status=403)
                return
            if contractor.get("approval_status") == "Blocked":
                reason = html.escape(contractor.get("block_reason") or "Your account has been blocked.")
                self.send_html(load_contractor_login_page(f'<p class="message error">⛔ Account blocked: {reason}</p>'), status=403)
                return
            session_id = create_session_record(email)
            SESSIONS[session_id] = email
            self.redirect("/contractor-dashboard", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
            return
        if path == "/contractor/register" or path == "/contractor-register":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            email = form.get("email", [""])[0].strip().lower()
            password = form.get("password", [""])[0]
            confirm_password = form.get("confirm_password", [""])[0]
            values = {
                "company_name": form.get("company_name", [""])[0].strip()[:255],
                "owner_name": form.get("owner_name", [""])[0].strip()[:255],
                "license_no": form.get("license_no", [""])[0].strip()[:100],
                "district": form.get("district", [""])[0].strip()[:100],
                "specializations": form.get("specializations", [""])[0].strip()[:500],
                "contact_email": email,
                "phone": form.get("phone", [""])[0].strip()[:20],
            }
            if password != confirm_password:
                self.send_html(load_contractor_register_page('<p class="message error">Passwords do not match.</p>'), status=400)
                return
            if not all(values.values()) or "@" not in email:
                self.send_html(load_contractor_register_page('<p class="message error">All fields including a valid email are required.</p>'), status=400)
                return
            if any(str(contractor.get("contact_email", "")).casefold() == email.casefold() for contractor in load_contractors()):
                self.send_html(load_contractor_register_page('<p class="message error">A contractor profile already uses this email.</p>'), status=400)
                return
            created, message = create_account(email, password)
            if not created:
                self.send_html(load_contractor_register_page(f'<p class="message error">{html.escape(message)}</p>'), status=400)
                return
            try:
                create_contractor(**values)
            except Exception:
                self.send_html(load_contractor_register_page('<p class="message error">The contractor profile could not be created. License number may already be registered.</p>'), status=400)
                return
            self.send_html(load_contractor_register_page('<p class="message success"><strong>Registration submitted.</strong> A government administrator must approve your application before you can sign in.</p>'))
            return
        if path == "/university/register" or path == "/university-register":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            email = form.get("email", [""])[0].strip().lower()
            password = form.get("password", [""])[0]
            confirm_password = form.get("confirm_password", [""])[0]
            values = {
                "name": form.get("name", [""])[0].strip()[:255],
                "district": form.get("district", [""])[0].strip()[:100],
                "domains": form.get("domains", [""])[0].strip()[:1000],
                "departments": form.get("departments", [""])[0].strip()[:1000],
                "laboratories": form.get("laboratories", [""])[0].strip()[:1000],
                "incubation_facilities": form.get("incubation_facilities", [""])[0].strip()[:1000],
                "contact_email": email,
                "expertise": form.get("expertise", [""])[0].strip()[:1500],
            }
            if password != confirm_password:
                self.send_html(load_university_register_page('<p class="error">Passwords do not match.</p>'), status=400)
                return
            if not values["name"] or not values["district"] or not values["domains"] or not values["expertise"] or "@" not in email:
                self.send_html(load_university_register_page('<p class="error">University name, district, domains, expertise, and valid email are required.</p>'), status=400)
                return
            existing_university = next((item for item in load_universities() if str(item.get("contact_email", "")).casefold() == email.casefold()), None)
            if existing_university is not None:
                status = existing_university.get("approval_status", "Active").lower()
                self.send_html(load_university_register_page(f'<p class="success">A university registration already exists for this email. Current approval status: <strong>{html.escape(status.title())}</strong>. Please use the university login after administrator approval.</p>'))
                return
            created, message = create_account(email, password)
            if not created:
                self.send_html(load_university_register_page(f'<p class="error">{html.escape(message)}</p>'), status=400)
                return
            university = create_university(**values)
            self.send_html(load_university_register_page(f'<p class="success"><strong>Registration acknowledged.</strong> {html.escape(university["name"])} has been submitted for administrator approval. Reference email: <strong>{html.escape(email)}</strong>. You can sign in after the approval status becomes Active.</p>'))
            return
        if path == "/api/admin/contractor-assignments":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data.get("issue_id", 0))
                contractor_id = int(data.get("contractor_id", 0))
            except (TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid assignment data."}, status=400)
                return
            issue = next((item for item in ISSUES if item.get("id") == issue_id), None)
            contractor = next((item for item in load_contractors() if item.get("id") == contractor_id), None)
            if issue is None or issue.get("moderation_status") != "Approved":
                self.send_json({"message": "Only approved issues can be assigned."}, status=400)
                return
            if contractor is None or contractor.get("approval_status") != "Active":
                self.send_json({"message": "Only active contractors can receive assignments."}, status=400)
                return
            if not assign_issue_to_contractor(issue_id, contractor_id, user):
                self.send_json({"message": "Failed to assign issue to contractor."}, status=500)
                return
            create_notification(contractor.get("contact_email", ""), f"A civic issue was assigned to {contractor.get('company_name', 'your company')}: {issue.get('title', 'New project')}.", "contractor_assignment", issue_id)
            self.send_json({"message": "Issue assigned successfully."})
            return
        if path == "/api/contractor/assignment-status":
            user = self.session_user()
            contractor = _contractor_for_user_storage(user) if user else None
            if contractor is None:
                self.send_json({"message": "Contractor account required."}, status=403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                form, upload = parse_multipart_form(self.headers, self.rfile.read(length))
                assignment_id = int(form.get("assignment_id", "0"))
                status = str(form.get("status", "")).strip()
                note = str(form.get("note", "")).strip()[:4000]
                image_type = ""
                image_data = b""
                if upload is not None and upload[0]:
                    image_type = upload[1]
                    if image_type not in {"image/jpeg", "image/png", "image/webp"}:
                        self.send_json({"message": "Progress image must be JPEG, PNG, or WebP."}, status=400)
                        return
                    image_data = upload[2]
                    if len(image_data) > 8 * 1024 * 1024:
                        self.send_json({"message": "Progress image is larger than 8 MB."}, status=413)
                        return
            except (TypeError, ValueError):
                self.send_json({"message": "Invalid update data."}, status=400)
                return
            if status not in {"Assigned", "In Progress", "Completed", "Rejected"}:
                self.send_json({"message": "Invalid assignment status."}, status=400)
                return
            assignments = load_contractor_assignments(contractor["id"])
            if not any(item.get("id") == assignment_id for item in assignments):
                self.send_json({"message": "Not authorized to update this assignment."}, status=403)
                return
            try:
                updated = update_contractor_assignment(assignment_id, status, note, image_type, image_data)
            except Exception:
                self.send_json({"message": "Could not save the status update and image."}, status=500)
                return
            if not updated:
                self.send_json({"message": "Failed to update assignment."}, status=500)
                return
            self.send_json({"message": "Assignment updated."})
            return
        if path == "/api/complaints/contractor":
            user = self.session_user()
            if user is None:
                self.send_json({"message": "You must be signed in."}, status=401)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                contractor_id = int(data.get("contractor_id", 0))
                issue_id = int(data.get("issue_id", 0))
                complaint_type = str(data.get("complaint_type", "")).strip()[:50]
                description = str(data.get("description", "")).strip()[:3000]
            except (TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid complaint data."}, status=400)
                return
            if not complaint_type or len(description) < 10:
                self.send_json({"message": "Complaint type and at least 10 characters of detail are required."}, status=400)
                return
            assignment = next((item for item in load_all_contractor_assignments() if item.get("issue_id") == issue_id and item.get("contractor_id") == contractor_id), None)
            if assignment is None:
                self.send_json({"message": "That contractor is not assigned to this issue."}, status=400)
                return
            complaint = create_contractor_complaint(contractor_id, issue_id, user, complaint_type, description)
            create_notification("admin@jharkhand.gov.in", f"Citizen complaint filed against contractor '{assignment.get('company_name', 'contractor')}' for Issue #{issue_id}; review required.", "contractor_complaint", complaint["id"])
            self.send_json({"message": "Complaint filed for contractor administration review.", "complaint_id": complaint["id"]}, status=201)
            return
        if path.startswith("/api/admin/contractor-complaints/") and path.endswith("/review"):
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_json({"message": "Admin authorization required."}, status=403)
                return
            parts = path.strip("/").split("/")
            try:
                complaint_id = int(parts[3])
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                status = str(data.get("status", "")).strip()
            except (IndexError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid review data."}, status=400)
                return
            if status not in {"Reviewed", "Dismissed"}:
                self.send_json({"message": "Invalid complaint review status."}, status=400)
                return
            try:
                reviewed = review_contractor_complaint(complaint_id, status, user)
            except Exception:
                self.send_json({"message": "Could not update complaint status."}, status=500)
                return
            if not reviewed:
                self.send_json({"message": "Complaint not found."}, status=404)
                return
            self.send_json({"message": "Complaint reviewed."})
            return
        if path == "/api/admin/proposals":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                proposal_id = int(data["proposal_id"])
                status = str(data["status"])
                reason = str(data.get("reason", "")).strip()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid proposal moderation data."}, status=400)
                return
            if status not in {"Approved", "Rejected", "Archived"} or not reason or len(reason) > 1000:
                self.send_json({"message": "Choose a valid decision and provide a reason."}, status=400)
                return
            proposal = next((item for item in PROPOSALS if item.get("id") == proposal_id), None)
            if proposal is None:
                self.send_json({"message": "Proposal not found."}, status=404)
                return
            proposal["status"] = status
            proposal["review"] = {"decision": status, "explanation": reason, "reviewer": user}
            update_proposal(proposal)
            self.send_json({"proposal_id": proposal_id, "status": status})
            return
        if path == "/api/admin/issues":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                status = str(data["status"])
                reason = str(data.get("reason", "")).strip()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid moderation data."}, status=400)
                return
            if status not in {"Approved", "Rejected", "Archived"} or not reason or len(reason) > 1000:
                self.send_json({"message": "Choose a valid decision and provide a reason."}, status=400)
                return
            if not moderate_issue(issue_id, status, reason, user):
                self.send_json({"message": "Issue not found."}, status=404)
                return
            issue = next((item for item in ISSUES if item.get("id") == issue_id), None)
            if issue is not None:
                issue.update({"moderation_status": status, "moderation_reason": reason, "moderated_by": user})
                create_notification(issue.get("reporter", ""), f"Your issue '{issue.get('title', 'issue')}' was {status.lower()}.", "issue", issue_id) if issue.get("reporter") else None
                if status == "Approved":
                    auto_assign_issue_to_best_university(issue)
            self.send_json({"status": status, "issue_id": issue_id})
            return
        if path == "/api/admin/assignments":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                university_id = int(data["university_id"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid assignment data."}, status=400)
                return
            if not assign_issue(issue_id, university_id, user):
                self.send_json({"message": "Issue or university not found."}, status=404)
                return
            university = next((item for item in load_universities() if item["id"] == university_id), None)
            if university and university.get("contact_email"):
                create_notification(university["contact_email"], f"A challenge was assigned to {university['name']}.", "assignment", issue_id)
            self.send_json({"issue_id": issue_id, "university_id": university_id, "status": "Assigned"})
            return
        if path == "/api/admin/assignment-response":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                status = str(data["status"])
                reason = str(data.get("reason", "")).strip()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid university response."}, status=400)
                return
            if status not in {"Accepted", "Rejected", "Needs clarification"} or not reason or len(reason) > 1000:
                self.send_json({"message": "Choose a valid response and provide a reason."}, status=400)
                return
            if not update_assignment(issue_id, status, reason):
                self.send_json({"message": "Assignment not found."}, status=404)
                return
            self.send_json({"issue_id": issue_id, "status": status})
            return
        if path == "/api/university/assignment-response":
            user = self.session_user()
            university = university_for_user(user or "")
            if university is None:
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                status = str(data["status"])
                reason = str(data.get("reason", "")).strip()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid university response."}, status=400)
                return
            assignments = load_university_assignments(user or "")
            if issue_id not in {assignment["issue_id"] for assignment in assignments}:
                self.send_error(403)
                return
            if status not in {"Accepted", "Rejected", "Needs clarification"} or not reason or len(reason) > 1000:
                self.send_json({"message": "Choose a valid response and provide a reason."}, status=400)
                return
            update_assignment(issue_id, status, reason)
            create_notification("admin@jharkhand.gov.in", f"University '{university['name']}' has {status.upper()} assignment for Issue #{issue_id}. Reason: {reason}", "assignment_response", issue_id)
            self.send_json({"issue_id": issue_id, "status": status})
            return
        if path == "/api/university/reports":
            user = self.session_user()
            university = university_for_user(user or "")
            if university is None:
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                title = str(data["title"]).strip()
                summary = str(data["summary"]).strip()
                deliverables = str(data.get("deliverables", "")).strip()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid report data."}, status=400)
                return
            if not title or not summary:
                self.send_json({"message": "Title and summary are required."}, status=400)
                return
            report = create_university_report(issue_id, university["id"], user or "", title, summary, deliverables)
            create_notification("admin@jharkhand.gov.in", f"University '{university['name']}' submitted a project report: '{title}'", "report", issue_id)
            self.send_json({"message": "Report submitted successfully.", "report": report}, status=201)
            return
        if path == "/api/university/teams":
            user = self.session_user()
            university = university_for_user(user or "")
            if university is None:
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                university_id = int(data["university_id"])
                name = str(data["name"]).strip()[:150]
                mentor = str(data["faculty_mentor"]).strip()[:255]
                members = [str(member).strip()[:255] for member in data.get("members", []) if str(member).strip()]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid team data."}, status=400)
                return
            if university_id != university["id"] or issue_id not in {assignment["issue_id"] for assignment in load_university_assignments(user or "")}:
                self.send_error(403)
                return
            if not name or not mentor or not members:
                self.send_json({"message": "Team name, faculty mentor, and students are required."}, status=400)
                return
            team = create_team(issue_id, university_id, name, mentor, members)
            self.send_json({"message": "Project team created.", "team": team}, status=201)
            return
        if path in {"/api/university/team-status", "/api/university/milestones", "/api/university/milestone-status", "/api/university/team-outcomes"}:
            user = self.session_user()
            university = university_for_user(user or "")
            if university is None:
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                team_id = int(data["team_id"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid project data."}, status=400)
                return
            team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
            if team is None:
                self.send_error(403)
                return
            if path.endswith("team-status"):
                status = str(data.get("status", ""))
                if status not in {"Team Formed", "Prototype", "Pilot", "Deployed", "Impact Measured"}:
                    self.send_json({"message": "Invalid project stage."}, status=400)
                    return
                note = str(data.get("note", "")).strip()[:1000]
                update_team_status(team_id, status, user or "", note)
                self.send_json({"team_id": team_id, "status": status})
                return
            if path.endswith("milestone-status"):
                status = str(data.get("status", ""))
                testing_result = str(data.get("testing_result", "")).strip()[:2000]
                if status not in {"Pending", "In Progress", "Completed"}:
                    self.send_json({"message": "Invalid milestone status."}, status=400)
                    return
                milestone_id = int(data.get("milestone_id"))
                if not any(milestone["id"] == milestone_id for milestone in load_milestones(team_id)):
                    self.send_error(403)
                    return
                update_milestone(milestone_id, status, testing_result)
                self.send_json({"milestone_id": milestone_id, "status": status})
                return
            if path.endswith("team-outcomes"):
                ip_outcome = str(data.get("ip_outcome", "")).strip()[:2000]
                startup_outcome = str(data.get("startup_outcome", "")).strip()[:2000]
                impact_summary = str(data.get("impact_summary", "")).strip()[:3000]
                update_team_outcomes(team_id, ip_outcome, startup_outcome, impact_summary)
                self.send_json({"team_id": team_id, "status": "saved"})
                return
            title = str(data.get("title", "")).strip()[:200]
            due_date = str(data.get("due_date", "")).strip()
            deliverable = str(data.get("deliverable", "")).strip()[:1000]
            if not title:
                self.send_json({"message": "Milestone title is required."}, status=400)
                return
            milestone = create_milestone(team_id, title, due_date, deliverable)
            self.send_json({"message": "Milestone added.", "milestone": milestone}, status=201)
            return
        if path == "/api/industry/offers":
            user = self.session_user()
            partner = industry_for_user(user or "")
            if partner is None:
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                support_type = str(data["support_type"]).strip()
                details = str(data["details"]).strip()[:3000]
                funding_amount = int(data.get("funding_amount") or 0)
                resources = str(data.get("resources", "")).strip()[:1000]
                timeline = str(data.get("timeline", "")).strip()[:100]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid support offer."}, status=400)
                return
            allowed_types = {
                "Mentorship", "Funding", "Prototyping", "Testing", "Deployment",
                "Co-development", "Technology Transfer", "Pilot Implementation",
                "CSR / Seed Funding", "Prototyping Facility", "Testing & Validation", "Deployment & Scaling"
            }
            if support_type not in allowed_types or not details:
                self.send_json({"message": "Choose a valid support type and provide details."}, status=400)
                return
            if not any(issue.get("id") == issue_id and issue.get("moderation_status", "Pending") == "Approved" for issue in ISSUES):
                self.send_json({"message": "Only approved issues can receive offers."}, status=400)
                return
            offer = create_support_offer(issue_id, partner["id"], support_type, details, funding_amount, resources, timeline)
            issue = next((item for item in ISSUES if item.get("id") == issue_id), None)
            if issue and issue.get("reporter"):
                create_notification(issue["reporter"], f"Industry partner '{partner['name']}' pledged {support_type} support for your issue.", "offer", offer["id"])
            create_notification("admin@jharkhand.gov.in", f"Industry partner '{partner['name']}' pledged {support_type} for Issue #{issue_id}.", "offer", offer["id"])
            self.send_json({"message": "Support offer submitted.", "offer": offer}, status=201)
            return
        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = self.session_user()
            if user is None:
                self.send_json({"message": "Authentication required."}, status=401)
                return
            try:
                notification_id = int(path.split("/")[3])
            except (IndexError, ValueError):
                self.send_json({"message": "Invalid notification ID."}, status=400)
                return
            if mark_notification_read(notification_id, user):
                self.send_json({"message": "Notification marked as read."})
            else:
                self.send_json({"message": "Notification not found."}, status=404)
            return

        if path == "/api/notifications/read-all":
            user = self.session_user()
            if user is None:
                self.send_json({"message": "Authentication required."}, status=401)
                return
            mark_all_notifications_read(user)
            self.send_json({"message": "All notifications marked as read."})
            return

        if path == "/api/messages":
            user = self.session_user()
            if user is None:
                self.send_error(401)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                recipient = str(data["recipient"]).strip().lower()
                message = str(data["message"]).strip()[:3000]
                related_id = int(data["related_id"]) if data.get("related_id") else None
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid message."}, status=400)
                return
            if recipient not in known_recipients() or not message:
                self.send_json({"message": "Choose a known recipient and provide a message."}, status=400)
                return
            sent = create_message(user, recipient, message, "project" if related_id else "", related_id)
            create_notification(recipient, f"New project message from {user}.", "message", sent["id"])
            self.send_json({"message": "Message sent.", "message_id": sent["id"]}, status=201)
            return
        if path == "/api/admin/universities":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                university_id = int(data["university_id"])
                name = str(data["name"]).strip()[:255]
                district = str(data["district"]).strip()[:100]
                domains = str(data["domains"]).strip()[:1000]
                expertise = str(data.get("expertise", "")).strip()[:1500]
                departments = str(data.get("departments", "")).strip()[:1000]
                laboratories = str(data.get("laboratories", "")).strip()[:1000]
                incubation_facilities = str(data.get("incubation_facilities", "")).strip()[:1000]
                contact_email = str(data.get("contact_email", "")).strip()[:255]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid university profile."}, status=400)
                return
            if not name or not district or not domains:
                self.send_json({"message": "Name, district, and domains are required."}, status=400)
                return
            if not update_university(university_id, name, district, domains, departments, laboratories, incubation_facilities, contact_email, expertise):
                self.send_json({"message": "University not found."}, status=404)
                return
            self.send_json({"message": "University profile updated.", "university_id": university_id})
            return
        if path == "/api/admin/universities/create":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                values = {field: str(data.get(field, "")).strip()[:limit] for field, limit in {"name": 255, "district": 100, "domains": 1000, "expertise": 1500, "departments": 1000, "laboratories": 1000, "incubation_facilities": 1000, "contact_email": 255}.items()}
            except (TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid university profile."}, status=400)
                return
            if not values["name"] or not values["district"] or not values["domains"] or not values["expertise"] or "@" not in values["contact_email"]:
                self.send_json({"message": "Name, district, domains, expertise, and a valid contact email are required."}, status=400)
                return
            try:
                university = create_university(**values, approval_status="Active")
            except Exception:
                self.send_json({"message": "A university with this contact email may already exist."}, status=400)
                return
            self.send_json({"message": "University registered.", "university": university}, status=201)
            return
        if path.startswith("/api/admin/institutions/") and path.endswith("/approval"):
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            parts = path.strip("/").split("/")
            if len(parts) != 6 or parts[3] not in {"university", "industry", "contractor"} or parts[5] != "approval":
                self.send_json({"message": "Invalid institution approval path."}, status=400)
                return
            try:
                institution_id = int(parts[4])
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                status = str(data["status"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid approval data."}, status=400)
                return
            if status not in {"Active", "Rejected", "Pending"}:
                self.send_json({"message": "Invalid approval status."}, status=400)
                return
            if not update_institution_approval(parts[3], institution_id, status):
                self.send_json({"message": "Institution not found."}, status=404)
                return
            self.send_json({"kind": parts[3], "institution_id": institution_id, "status": status})
            return
        if path == "/api/admin/industry-partners":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                values = {field: str(data.get(field, "")).strip()[:limit] for field, limit in {"name": 255, "partner_type": 50, "district": 100, "domains": 1000, "contact_email": 255}.items()}
            except (TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid industry partner profile."}, status=400)
                return
            if not all(values.values()) or "@" not in values["contact_email"]:
                self.send_json({"message": "All partner fields and a valid contact email are required."}, status=400)
                return
            try:
                partner = create_industry_partner(**values)
            except Exception:
                self.send_json({"message": "A partner with this email may already exist."}, status=400)
                return
            self.send_json({"message": "Industry partner registered.", "partner": partner}, status=201)
            return
        if path == "/api/admin/offer-commitments":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                offer_id = int(data["offer_id"])
                status = str(data["status"])
                note = str(data.get("note", "")).strip()[:2000]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid commitment update."}, status=400)
                return
            if status not in {"Offered", "Accepted", "Delivered", "Declined"}:
                self.send_json({"message": "Invalid commitment status."}, status=400)
                return
            if not update_offer_commitment(offer_id, status, note):
                self.send_json({"message": "Support offer not found."}, status=404)
                return
            self.send_json({"offer_id": offer_id, "status": status})
            return
        if path == "/api/admin/teams":
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                issue_id = int(data["issue_id"])
                university_id = int(data["university_id"])
                name = str(data["name"]).strip()[:150]
                mentor = str(data["faculty_mentor"]).strip()[:255]
                members = [str(member).strip()[:255] for member in data.get("members", []) if str(member).strip()]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid team data."}, status=400)
                return
            if not name or not mentor or not members or not university_id:
                self.send_json({"message": "Team name, faculty mentor, and students are required."}, status=400)
                return
            try:
                team = create_team(issue_id, university_id, name, mentor, members)
            except Exception:
                self.send_json({"message": "The issue or university assignment is invalid."}, status=400)
                return
            self.send_json({"message": "Project team created.", "team": team}, status=201)
            return
        if path.startswith("/api/admin/contractors/") and path.endswith("/status"):
            user = self.session_user()
            if user is None or not is_admin(user):
                self.send_json({"message": "Admin authorization required."}, status=403)
                return
            parts = path.strip("/").split("/")
            try:
                contractor_id = int(parts[3])
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                status = str(data.get("status", "")).strip()
                reason = str(data.get("reason", "")).strip()[:2000]
            except (IndexError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid contractor status data."}, status=400)
                return
            if status not in {"Active", "Blocked", "Pending"}:
                self.send_json({"message": "Invalid contractor status."}, status=400)
                return
            try:
                updated = update_contractor_status(contractor_id, status, reason)
            except Exception:
                self.send_json({"message": "Could not update contractor status. Check the database schema and try again."}, status=500)
                return
            if not updated:
                self.send_json({"message": "Contractor not found."}, status=404)
                return
            self.send_json({"message": "Contractor status updated."})
            return
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
            proof_bytes = b""
            video_bytes = b""
            proof_id = ""
            video_id = ""
            try:
                issue = json.loads(self.rfile.read(length).decode("utf-8"))
                issue["lat"] = float(issue["lat"])
                issue["lng"] = float(issue["lng"])
                issue["district"] = str(issue.get("district", "Ranchi")).strip() or "Ranchi"
                issue["block"] = str(issue.get("block", "")).strip()
                issue["reporter"] = self.session_user() or ""
                encoded_proof = issue.pop("proof_image","")
                proof_type = issue.pop("proof_type","image/jpeg")
                encoded_video = issue.pop("proof_video","")
                video_type = issue.pop("proof_video_type","video/mp4")
                allowed_proof_types = {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
                allowed_video_types = {"video/mp4", "video/webm"}
                if proof_type not in allowed_proof_types:
                    self.send_error(415,"Unsupported proof file type")
                    return
                if encoded_video and video_type not in allowed_video_types:
                    self.send_error(415,"Unsupported video file type")
                    return
                proof_bytes = base64.b64decode(encoded_proof,validate=True) if encoded_proof else b""
                video_bytes = base64.b64decode(encoded_video,validate=True) if encoded_video else b""
                if proof_bytes and str(proof_type).startswith("video/") and not video_bytes:
                    video_bytes, video_type = proof_bytes, proof_type
                    proof_bytes, proof_type = b"", "image/jpeg"
                # #region agent log
                try:
                    import time
                    with open(BASE_DIR / "debug-0d8a0a.log", "a", encoding="utf-8") as handle:
                        handle.write(json.dumps({"sessionId":"0d8a0a","hypothesisId":"C","location":"map.py:/api/issues","message":"incoming media","data":{"proof_type":proof_type,"video_type":video_type,"proof_len":len(proof_bytes),"video_len":len(video_bytes),"encoded_video":bool(encoded_video)},"timestamp":int(time.time()*1000),"runId":"post-fix"})+"\n")
                except Exception:
                    pass
                # #endregion
                if len(proof_bytes) > 25 * 1024 * 1024 or len(video_bytes) > 25 * 1024 * 1024:
                    self.send_error(413,"Proof file is larger than 25 MB")
                    return
                if proof_bytes:
                    if proof_type.startswith("image/"):
                        proof_bytes, proof_type = sanitize_and_reencode_image(proof_bytes, proof_type)
                        proof = inspect_image_proof(proof_bytes,issue["lat"],issue["lng"])
                        if proof["status"] == "mismatch":
                            self.send_json(proof,status=422)
                            return
                        issue.update({"proof_status":proof["status"],"proof_message":proof["message"]})
                    else:
                        issue.update({"proof_status":"unverified","proof_message":"Supporting file uploaded; location verification is available for geotagged photos."})
                    proof_id = secrets.token_urlsafe(12)
                    issue["proof_id"] = proof_id
                    issue["_proof_type"] = proof_type
                    issue["_proof_data"] = proof_bytes
                if video_bytes:
                    video_id = secrets.token_urlsafe(12)
                    issue["video_id"] = video_id
                    issue["_video_type"] = video_type
                    issue["_video_data"] = video_bytes
                created = add_issue(issue)
            except (ValueError,KeyError,json.JSONDecodeError):
                self.send_error(400)
                return
            if created.get("issue") and created["result"] != "possible_duplicate":
                if proof_bytes:
                    created["issue"]["proof_id"] = proof_id
                if video_bytes:
                    created["issue"]["video_id"] = video_id
            if created.get("result") == "new" and created.get("issue"):
                assignment = auto_assign_issue_to_best_university(created["issue"])
                if assignment:
                    created["assignment"] = {
                        "university_id": assignment["university"]["id"],
                        "university_name": assignment["university"]["name"],
                        "score": assignment["score"],
                    }
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
            result, votes, previous_proposal_id = cast_proposal_vote(proposal_id, self.session_user() or "")
            if result == "missing":
                self.send_json({"message": "Proposal not found."}, status=404)
                return
            if result == "ineligible":
                self.send_json({"message": "Support the related issue before voting."}, status=403)
                return
            if result == "already_voted":
                self.send_json({"votes": votes, "result": result}, status=409)
                return
            proposal["votes"] = votes
            if previous_proposal_id is not None:
                previous = next((item for item in PROPOSALS if item["id"] == previous_proposal_id), None)
                if previous is not None:
                    previous["votes"] = max(0, previous["votes"] - 1)
            self.send_json({"votes": votes, "result": result})
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
        portal_role = form.get("portal_role", ["citizen"])[0].strip().lower()
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
        allowed_roles = {"citizen", "government", "university", "industry", "contractor"}
        if portal_role not in allowed_roles:
            self.send_html(
                load_login_page('<p class="error">Please select a valid portal.</p>', portal_role=portal_role),
                status=400,
            )
            return

        if not authenticate(email,password):
            self.send_html(
                load_login_page(
                    '<p class="error">Email or password is incorrect.</p>',
                    portal_role=portal_role,
                ),
                status=401,
            )
            return

        actual_role = portal_role_for_user(email)
        if portal_role != actual_role:
            role_names = {
                "citizen": "Citizen",
                "government": "Government",
                "university": "University",
                "industry": "Industry",
                "contractor": "Contractor",
            }
            actual_role_name = role_names.get(actual_role, actual_role.title())
            selected_role_name = role_names.get(portal_role, portal_role.title())
            error = (
                '<p class="error">'
                f'Wrong portal selected. You selected <strong>{html.escape(selected_role_name)}</strong>, '
                f'but this account belongs to the <strong>{html.escape(actual_role_name)}</strong> portal. '
                f'Please select {html.escape(actual_role_name)} and try again.'
                '</p>'
            )
            self.send_html(
                load_login_page(error, portal_role=portal_role),
                status=403,
            )
            return

        session_id = secrets.token_urlsafe(32)
        SESSIONS[session_id] = email
        destination = {
            "citizen": "/citizen-dashboard",
            "government": "/government-dashboard",
            "university": "/university-dashboard",
            "industry": "/industry-dashboard",
            "contractor": "/contractor-dashboard",
        }[portal_role]
        self.redirect(destination,f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
    def send_html(self,page,status=200):
        self.send_payload(page.encode("utf-8"),status)
    def send_json(self,data,status=200):
        self.send_payload(json.dumps(data).encode("utf-8"),status,"application/json")
    def send_payload(self,payload,status=200,content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        if self.path.split("?", 1)[0] == "/api/notifications":
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
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