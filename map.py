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
CITIZEN_PAGE_FILE = BASE_DIR / "templates" / "citizen.html"
UNIVERSITY_DASHBOARD_FILE = BASE_DIR / "templates" / "university.html"
INDUSTRY_DASHBOARD_FILE = BASE_DIR / "templates" / "industry.html"
GOVERNMENT_DASHBOARD_FILE = BASE_DIR / "templates" / "government.html"
try:
    from .login_users import authenticate, create_account, is_admin, professional_profile
    from .community import JHARKHAND_DISTRICTS, JHARKHAND_DOMAINS, ISSUES, add_issue, nearby_issues, render_page, upvote_issue
    from .storage import (
        assign_issue, check_rate_limit, create_account_record, create_industry_partner,
        create_message, create_milestone, create_notification, create_session_record,
        create_support_offer, create_team, create_university, delete_session_record,
        get_proof, get_proposal_visual, get_session_user, insert_proposal,
        load_all_partner_offers, load_all_teams_with_details, load_assignments,
        load_dashboard_metrics, load_industry_partners, load_milestones,
        load_notifications, load_messages, load_partner_offers, load_proposals,
        load_status_history, load_teams, load_university_assignments,
        load_university_issue_offers, load_universities, load_user_issues,
        moderate_issue, update_assignment, update_milestone, update_offer_commitment,
        update_proposal, update_team_outcomes, update_team_status, update_university
    )
    from .AI_model import inspect_image_proof, sanitize_and_reencode_image
    from .evidence_review import review_issue_evidence
except ImportError:
    from login_users import authenticate, create_account, is_admin, professional_profile
    from community import JHARKHAND_DISTRICTS, JHARKHAND_DOMAINS, ISSUES, add_issue, nearby_issues, render_page, upvote_issue
    from storage import (
        assign_issue, check_rate_limit, create_account_record, create_industry_partner,
        create_message, create_milestone, create_notification, create_session_record,
        create_support_offer, create_team, create_university, delete_session_record,
        get_proof, get_proposal_visual, get_session_user, insert_proposal,
        load_all_partner_offers, load_all_teams_with_details, load_assignments,
        load_dashboard_metrics, load_industry_partners, load_milestones,
        load_notifications, load_messages, load_partner_offers, load_proposals,
        load_status_history, load_teams, load_university_assignments,
        load_university_issue_offers, load_universities, load_user_issues,
        moderate_issue, update_assignment, update_milestone, update_offer_commitment,
        update_proposal, update_team_outcomes, update_team_status, update_university
    )
    from AI_model import inspect_image_proof, sanitize_and_reencode_image
    from evidence_review import review_issue_evidence
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
    return next((university for university in load_universities() if str(university.get("contact_email", "")).casefold() == user.casefold()), None)
def render_dashboard_team(team):
    milestones = load_milestones(team["id"])
    history = load_status_history(team["id"])
    milestone_markup = "".join(f"<p>Milestone: {html.escape(milestone['title'])} · {html.escape(str(milestone['status']))} · {html.escape(str(milestone['due_date'] or 'No due date'))}</p><form data-endpoint='/api/university/milestone-status'><input type='hidden' name='milestone_id' value='{milestone['id']}'><select name='status'><option>Pending</option><option>In Progress</option><option>Completed</option></select><input name='testing_result' placeholder='Testing result'><button>Save milestone</button></form>" for milestone in milestones)
    history_markup = "".join(f"<p>History: {html.escape(item['status'])} · {html.escape(item['changed_by'])} · {html.escape(str(item['changed_at']))}</p>" for item in history)
    return f"<p><strong>{html.escape(team['name'])}</strong> · {html.escape(team['faculty_mentor'])} · {html.escape(team['status'])} · {html.escape(', '.join(team['members']))}</p><form data-endpoint='/api/university/team-status'><input type='hidden' name='team_id' value='{team['id']}'><select name='status'><option>Team Formed</option><option>Prototype</option><option>Pilot</option><option>Deployed</option><option>Impact Measured</option></select><input name='note' placeholder='Stage update note'><button>Update stage</button></form><form data-endpoint='/api/university/milestones'><input type='hidden' name='team_id' value='{team['id']}'><input name='title' placeholder='Milestone title' required><input name='due_date' type='date'><input name='deliverable' placeholder='Deliverable'><button>Add milestone</button></form>{milestone_markup}<h4>Status history</h4>{history_markup}<form data-endpoint='/api/university/team-outcomes'><input type='hidden' name='team_id' value='{team['id']}'><input name='ip_outcome' placeholder='IP or patent outcome'><input name='startup_outcome' placeholder='Startup outcome'><textarea name='impact_summary' placeholder='Community impact summary'></textarea><button>Save outcomes</button></form>"
def render_university_dashboard(user: str) -> str:
    template = UNIVERSITY_DASHBOARD_FILE.read_text(encoding="utf-8")
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
        return template.replace("__USER__", html.escape(user))\
                       .replace("__UNIVERSITY_HERO__", error_hero)\
                       .replace("__METRICS_BAR__", "")\
                       .replace("__CHALLENGES_CONTENT__", "")\
                       .replace("__TEAMS_CONTENT__", "")\
                       .replace("__MILESTONES_CONTENT__", "")\
                       .replace("__OFFERS_CONTENT__", "")\
                       .replace("__MESSAGES_CONTENT__", "")\
                       .replace("__PROFILE_CONTENT__", "")

    assignments = load_university_assignments(user)
    all_teams = load_teams()
    my_teams = [team for team in all_teams if team["university_id"] == university["id"]]
    offers = load_university_issue_offers(user)
    messages = load_messages(user)
    
    assigned_count = len(assignments)
    accepted_count = sum(1 for a in assignments if a.get("status") == "Accepted")
    teams_count = len(my_teams)
    
    all_milestones = []
    for t in my_teams:
        all_milestones.extend(load_milestones(t["id"]))
    completed_milestones = sum(1 for m in all_milestones if m.get("status") == "Completed")
    total_milestones = len(all_milestones)
    
    domains_list = [d.strip() for d in str(university.get("domains", "")).split(",") if d.strip()]
    domain_tags = "".join(f"<span class='inst-tag'>🏷️ {html.escape(d)}</span>" for d in domains_list)

    hero_html = f"""
    <div class="hero-card">
      <div class="hero-top">
        <div>
          <span class="hero-eyebrow">Academic Collaboration & Innovation Hub</span>
          <h1 class="hero-title">{html.escape(university['name'])}</h1>
          <p class="hero-desc">Institutional command centre for societal challenge adoption, faculty-guided student research teams, prototyping milestones, patent filings, and industry co-development across Jharkhand.</p>
          <div class="inst-badges">
            <span class="inst-tag">📍 {html.escape(university['district'])} District</span>
            {domain_tags}
            <span class="inst-tag">✉️ {html.escape(university.get('contact_email') or user)}</span>
          </div>
        </div>
      </div>
    </div>
    """

    metrics_html = f"""
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon blue">📋</div>
        <div class="metric-info">
          <h4>Assigned Challenges</h4>
          <div class="val">{assigned_count}</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon green">✅</div>
        <div class="metric-info">
          <h4>Accepted Projects</h4>
          <div class="val">{accepted_count}</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon gold">👥</div>
        <div class="metric-info">
          <h4>Student Teams</h4>
          <div class="val">{teams_count}</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon coral">🚀</div>
        <div class="metric-info">
          <h4>Milestones Done</h4>
          <div class="val">{completed_milestones}/{total_milestones}</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon blue">🤝</div>
        <div class="metric-info">
          <h4>Industry Offers</h4>
          <div class="val">{len(offers)}</div>
        </div>
      </div>
    </div>
    """

    # Tab 1: Assigned Challenges Content
    if not assignments:
        challenges_html = """
        <div class="empty-state">
          <h3>No Challenges Assigned Yet</h3>
          <p>Government administrators match validated societal challenges to your institution based on domain expertise and district relevance. Once assigned, you can formally accept them here.</p>
        </div>
        """
    else:
        cards = []
        for a in assignments:
            status = a.get("status", "Assigned")
            pill_class = "accepted" if status == "Accepted" else ("rejected" if status == "Rejected" else ("clarification" if status == "Needs clarification" else "assigned"))
            issue_teams = [t for t in my_teams if t["issue_id"] == a["issue_id"]]
            teams_submarkup = "".join(f"<div style='margin:4px 0; font-size:13px;'>🔹 <strong>{html.escape(t['name'])}</strong> (Mentor: {html.escape(t['faculty_mentor'])}) · Stage: <span class='status-pill accepted' style='font-size:10px; padding:2px 8px;'>{html.escape(t['status'])}</span></div>" for t in issue_teams) or "<p style='color:var(--muted); font-size:13px;'>No team assembled yet. Use the Student Project Teams tab to assemble a team.</p>"
            
            cards.append(f"""
            <div class="challenge-card">
              <div class="card-header-row">
                <div>
                  <div style="font-size:12px; font-weight:700; color:var(--primary); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">{html.escape(a.get('category', 'Civic Challenge'))}</div>
                  <h2 class="challenge-title">{html.escape(a['title'])}</h2>
                </div>
                <span class="status-pill {pill_class}">{html.escape(status)}</span>
              </div>
              <div class="meta-row">
                <span class="meta-item">📍 District: <strong>{html.escape(a.get('district', 'Ranchi'))}</strong></span>
                <span class="meta-item">🏛️ Block: <strong>{html.escape(a.get('block', 'N/A') or 'N/A')}</strong></span>
                <span class="meta-item">📅 Institutional Decision: <strong>{html.escape(str(a.get('response_reason') or 'Awaiting formal institutional response'))}</strong></span>
              </div>
              <p class="challenge-desc">{html.escape(a.get('description', ''))}</p>
              
              <div class="card-subblock">
                <h4>🏛️ Formal Institutional Decision</h4>
                <form data-endpoint="/api/university/assignment-response">
                  <input type="hidden" name="issue_id" value="{a['issue_id']}">
                  <div class="form-row">
                    <div>
                      <label>Decision Status</label>
                      <select name="status">
                        <option value="Accepted" {"selected" if status == "Accepted" else ""}>Accept Challenge (Commit Lab & Faculty)</option>
                        <option value="Needs clarification" {"selected" if status == "Needs clarification" else ""}>Request Clarification from Government</option>
                        <option value="Rejected" {"selected" if status == "Rejected" else ""}>Decline (Outside Domain / Capacity)</option>
                      </select>
                    </div>
                    <div>
                      <label>Decision Rationale / Lab Commitment</label>
                      <input name="reason" value="{html.escape(str(a.get('response_reason') or ''))}" placeholder="e.g. Accepted by Dept of Civil Engineering under Smart Water initiative" required>
                    </div>
                  </div>
                  <button type="submit" class="btn btn-primary btn-sm">Save Institutional Decision</button>
                </form>
              </div>

              <div class="card-subblock">
                <h4>👥 Active Project Teams for this Challenge</h4>
                {teams_submarkup}
              </div>

              <div class="card-subblock">
                <h4>💡 Submit Institutional Solution Proposal</h4>
                <form data-endpoint="/api/proposals">
                  <input type="hidden" name="issue_id" value="{a['issue_id']}">
                  <label>Solution Title</label>
                  <input name="title" placeholder="e.g., IoT Low-Cost Flow Sensor Network" required>
                  <label>Technical Solution Description & Architecture</label>
                  <textarea name="description" placeholder="Detail the engineering methodology, bill of materials, expected efficiency, and deployment roadmap..." required></textarea>
                  <button type="submit" class="btn btn-accent btn-sm">Submit Solution Proposal to Public Portal</button>
                </form>
              </div>
            </div>
            """)
        challenges_html = "".join(cards)

    # Tab 2: Teams Content
    options_for_issues = "".join(f"<option value='{a['issue_id']}'>{html.escape(a['title'])} ({html.escape(a.get('district',''))})</option>" for a in assignments)
    stages_order = ["Team Formed", "Prototype", "Pilot", "Deployed", "Impact Measured"]
    
    team_cards = []
    for team in my_teams:
        team_id = team["id"]
        status = team["status"]
        history = load_status_history(team_id)
        
        stepper_steps = []
        is_past = True
        for st in stages_order:
            cls = ""
            if st == status:
                cls = "active"
                is_past = False
            elif is_past:
                cls = "completed"
            stepper_steps.append(f"""
            <div class="stage-step {cls}">
              <div class="step-circle">{"✓" if cls == "completed" else "●"}</div>
              <span>{st}</span>
            </div>
            """)
        stepper_html = f"<div class='stage-stepper'>{''.join(stepper_steps)}</div>"
        history_items = "".join(
          f"<div style='font-size:12px; color:var(--ink-secondary); padding:4px 0; border-bottom:1px dashed var(--line);'>• <strong>{html.escape(h['status'])}</strong> by {html.escape(h['changed_by'])} ({html.escape(str(h['changed_at']))}) {('— <em>' + html.escape(h.get('note', '')) + '</em>') if h.get('note') else ''}</div>"
          for h in history
        ) or "<p style='font-size:12px; color:var(--muted);'>No previous stage updates recorded.</p>"
        
        team_cards.append(f"""
        <div class="challenge-card">
          <div class="card-header-row">
            <div>
              <span class="status-pill accepted" style="margin-bottom:6px;">Team #{team_id}</span>
              <h2 class="challenge-title">{html.escape(team['name'])}</h2>
            </div>
            <span class="status-pill assigned">Stage: {html.escape(status)}</span>
          </div>
          
          <div class="meta-row">
            <span class="meta-item">👨‍🏫 Faculty Mentor: <strong>{html.escape(team['faculty_mentor'])}</strong></span>
            <span class="meta-item">🎓 Student Members: <strong>{html.escape(', '.join(team['members']))}</strong></span>
          </div>
          
          <div class="card-subblock">
            <h4>🚀 Project Lifecycle Progression</h4>
            {stepper_html}
            <form data-endpoint="/api/university/team-status">
              <input type="hidden" name="team_id" value="{team_id}">
              <div class="form-row">
                <div>
                  <label>Update Stage</label>
                  <select name="status">
                    <option {"selected" if status == "Team Formed" else ""}>Team Formed</option>
                    <option {"selected" if status == "Prototype" else ""}>Prototype</option>
                    <option {"selected" if status == "Pilot" else ""}>Pilot</option>
                    <option {"selected" if status == "Deployed" else ""}>Deployed</option>
                    <option {"selected" if status == "Impact Measured" else ""}>Impact Measured</option>
                  </select>
                </div>
                <div>
                  <label>Progress Notes / Deliverable Summary</label>
                  <input name="note" placeholder="e.g. Lab bench prototype completed, bench testing verified">
                </div>
              </div>
              <button type="submit" class="btn btn-primary btn-sm">Update Project Stage</button>
            </form>
          </div>

          <div class="card-subblock">
            <h4>🏆 IP, Patent & Startup Outcomes</h4>
            <form data-endpoint="/api/university/team-outcomes">
              <input type="hidden" name="team_id" value="{team_id}">
              <div class="form-row">
                <div>
                  <label>IP / Patent Outcome</label>
                  <input name="ip_outcome" value="{html.escape(str(team.get('ip_outcome') or ''))}" placeholder="e.g. Provisional Patent Application #2026/JH/0042">
                </div>
                <div>
                  <label>Startup / Incubation Outcome</label>
                  <input name="startup_outcome" value="{html.escape(str(team.get('startup_outcome') or ''))}" placeholder="e.g. Incubated at BIT Mesra STEP, seed funding applied">
                </div>
              </div>
              <label>Community Impact Summary</label>
              <textarea name="impact_summary" placeholder="Provide metrics: estimated lives touched, water savings, cost reduction, carbon offset...">{html.escape(str(team.get('impact_summary') or ''))}</textarea>
              <button type="submit" class="btn btn-primary btn-sm">Save Outcomes</button>
            </form>
          </div>

          <div class="card-subblock">
            <h4>📜 Stage History & Audit Log</h4>
            {history_items}
          </div>
        </div>
        """)
        
    create_team_form = f"""
    <div class="content-card" style="margin-bottom:28px;">
      <h3 style="font-family:'Outfit',sans-serif; font-size:20px; margin-bottom:6px;">Assemble Multidisciplinary Student Team</h3>
      <p style="color:var(--ink-secondary); font-size:14px; margin-bottom:18px;">Form a faculty-guided multidisciplinary project team for an assigned challenge.</p>
      <form class="team" data-endpoint="/api/university/teams" data-type="team">
        <input type="hidden" name="university_id" value="{university['id']}">
        <div class="form-row">
          <div>
            <label>Assigned Challenge</label>
            <select name="issue_id" required>
              {options_for_issues or "<option disabled>No challenges assigned yet</option>"}
            </select>
          </div>
          <div>
            <label>Team Name</label>
            <input name="name" placeholder="e.g., Team Jal-Drishti" required>
          </div>
        </div>
        <div class="form-row">
          <div>
            <label>Faculty Mentor Email</label>
            <input name="faculty_mentor" type="email" placeholder="mentor@bitmesra.ac.in" required>
          </div>
          <div>
            <label>Student Member Emails (comma separated)</label>
            <input name="members" placeholder="student1@bitmesra.ac.in, student2@bitmesra.ac.in" required>
          </div>
        </div>
        <button type="submit" class="btn btn-primary" {"disabled" if not assignments else ""}>Assemble & Register Team</button>
      </form>
    </div>
    """
    teams_html = create_team_form + ("".join(team_cards) if team_cards else "<div class='empty-state'><h3>No Teams Formed Yet</h3><p>Use the form above to assemble a project team for your assigned challenges.</p></div>")

    # Tab 3: Milestones Content
    milestone_blocks = []
    for team in my_teams:
        ms_list = load_milestones(team["id"])
        ms_items = []
        for m in ms_list:
            status = m.get("status", "Pending")
            ms_pill = "accepted" if status == "Completed" else ("pending" if status == "In Progress" else "assigned")
            ms_items.append(f"""
            <div class="milestone-item">
              <div style="flex:1; min-width:240px;">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                  <span class="status-pill {ms_pill}" style="font-size:10px; padding:2px 8px;">{html.escape(status)}</span>
                  <span class="milestone-title">{html.escape(m['title'])}</span>
                </div>
                <div class="milestone-sub">
                  <span>📅 Due: <strong>{html.escape(str(m.get('due_date') or 'No deadline'))}</strong></span> · 
                  <span>📦 Deliverable: <strong>{html.escape(str(m.get('deliverable') or 'Standard Report'))}</strong></span>
                </div>
                {f"<div style='margin-top:6px; font-size:12px; color:var(--primary);'>🧪 <strong>Test Results:</strong> {html.escape(m['testing_result'])}</div>" if m.get('testing_result') else ""}
              </div>
              <form data-endpoint="/api/university/milestone-status" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <input type="hidden" name="milestone_id" value="{m['id']}">
                <select name="status" style="width:auto; margin-bottom:0; padding:6px 10px; font-size:12px;">
                  <option {"selected" if status == "Pending" else ""}>Pending</option>
                  <option {"selected" if status == "In Progress" else ""}>In Progress</option>
                  <option {"selected" if status == "Completed" else ""}>Completed</option>
                </select>
                <input name="testing_result" value="{html.escape(str(m.get('testing_result') or ''))}" placeholder="Testing / verification notes" style="width:200px; margin-bottom:0; padding:6px 10px; font-size:12px;">
                <button type="submit" class="btn btn-outline btn-sm">Save</button>
              </form>
            </div>
            """)
            
        milestone_blocks.append(f"""
        <div class="challenge-card">
          <div class="card-header-row">
            <div>
              <span class="hero-eyebrow">Team Milestones</span>
              <h2 class="challenge-title">{html.escape(team['name'])}</h2>
            </div>
            <span class="status-pill assigned">Stage: {html.escape(team['status'])}</span>
          </div>

          <div class="card-subblock" style="margin-bottom:18px;">
            <h4>➕ Add Project Milestone & Deliverable</h4>
            <form data-endpoint="/api/university/milestones">
              <input type="hidden" name="team_id" value="{team['id']}">
              <div class="form-row">
                <div>
                  <label>Milestone Title</label>
                  <input name="title" placeholder="e.g. PCB fabrication & bench calibration" required>
                </div>
                <div>
                  <label>Target Due Date</label>
                  <input name="due_date" type="date">
                </div>
                <div>
                  <label>Deliverable Type / Specification</label>
                  <input name="deliverable" placeholder="e.g. Hardware Prototype v1.0 & Test Report">
                </div>
              </div>
              <button type="submit" class="btn btn-primary btn-sm">Add Milestone</button>
            </form>
          </div>

          <div style="margin-top:14px;">
            <h4 style="font-family:'Outfit',sans-serif; font-size:16px; margin-bottom:12px;">Roadmap & Deliverable Status</h4>
            {''.join(ms_items) if ms_items else '<p style="color:var(--muted); font-size:13px;">No milestones added yet for this team.</p>'}
          </div>
        </div>
        """)
    milestones_html = "".join(milestone_blocks) if milestone_blocks else "<div class='empty-state'><h3>No Teams Available</h3><p>Assemble a project team first to manage roadmap milestones and pilot testing.</p></div>"

    # Tab 4: Offers Content
    if not offers:
        offers_html = """
        <div class="empty-state">
          <h3>No Industry Support Offers Yet</h3>
          <p>CSR organizations, startups, and MSMEs can browse approved challenges and submit offers for mentorship, seed funding, lab access, and deployment support.</p>
        </div>
        """
    else:
        offer_cards = []
        for o in offers:
            stype = o.get("support_type", "Mentorship")
            status = o.get("status", "Offered")
            pill_class = "accepted" if status == "Accepted" else ("delivered" if status == "Delivered" else "offered")
            offer_cards.append(f"""
            <div class="challenge-card">
              <div class="card-header-row">
                <div>
                  <span class="status-pill {pill_class}">{html.escape(status)}</span>
                  <h3 class="challenge-title" style="margin-top:6px; font-size:19px;">{html.escape(o.get('partner_name','Industry Partner'))} · <span style="color:var(--primary);">{html.escape(stype)} Support</span></h3>
                </div>
                <span class="status-pill pending">Challenge: {html.escape(o.get('issue_title','Civic Issue'))}</span>
              </div>
              <div class="meta-row">
                <span class="meta-item">🏢 Partner Type: <strong>{html.escape(o.get('partner_type','Industry'))}</strong></span>
                <span class="meta-item">📍 District: <strong>{html.escape(o.get('district','Jharkhand'))}</strong></span>
                <span class="meta-item">✉️ Partner Contact: <strong>{html.escape(o.get('partner_email','N/A'))}</strong></span>
              </div>
              <p class="challenge-desc"><strong>Support Commitment Details:</strong> {html.escape(o.get('details',''))}</p>
              {f"<div style='margin-top:10px; font-size:13px; color:var(--primary-dark); background:var(--primary-light); padding:10px; border-radius:6px;'>📝 <strong>Note:</strong> {html.escape(o['commitment_note'])}</div>" if o.get('commitment_note') else ""}
              <div style="margin-top:16px;">
                <button class="btn btn-outline btn-sm" onclick="showTab('messages')">✉️ Send Message to Partner</button>
              </div>
            </div>
            """)
        offers_html = "".join(offer_cards)

    # Tab 5: Messages Content
    msg_history = "".join(f"""
    <div style="background:var(--surface); border:1px solid var(--line); border-radius:var(--radius-sm); padding:14px 18px; margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:12px; color:var(--muted);">
        <span><strong>{html.escape(m['sender'])}</strong> ➔ <strong>{html.escape(m['recipient'])}</strong></span>
        <span>{html.escape(str(m.get('created_at','')))}</span>
      </div>
      <p style="color:var(--ink); font-size:14px;">{html.escape(m['message'])}</p>
    </div>
    """ for m in messages) or "<div class='empty-state' style='padding:24px;'><h3>No Messages Yet</h3><p>Coordinate directly with industry partners, student leads, and government officials.</p></div>"
    
    recipients_options = "".join(f"<option value='{r}'>{html.escape(r)}</option>" for r in sorted(known_recipients()) if r != user)

    messages_html = f"""
    <div style="display:grid; grid-template-columns:minmax(0,1.2fr) minmax(320px,0.8fr); gap:24px; align-items:flex-start;">
      <div class="content-card">
        <h3 style="font-family:'Outfit',sans-serif; font-size:20px; margin-bottom:16px;">Conversation Stream</h3>
        {msg_history}
      </div>
      <div class="content-card">
        <h3 style="font-family:'Outfit',sans-serif; font-size:20px; margin-bottom:16px;">Send Project Message</h3>
        <form data-endpoint="/api/messages">
          <label>Recipient</label>
          <select name="recipient" required>
            {recipients_options}
          </select>
          <label>Related Challenge / Project ID (Optional)</label>
          <input name="related_id" type="number" placeholder="e.g., 1">
          <label>Message Content</label>
          <textarea name="message" placeholder="Type your project update, inquiry, or meeting request..." required></textarea>
          <button type="submit" class="btn btn-primary">Send Message</button>
        </form>
      </div>
    </div>
    """

    # Tab 6: Profile Content
    profile_html = f"""
    <div class="content-card" style="max-width:800px;">
      <h3 style="font-family:'Outfit',sans-serif; font-size:22px; margin-bottom:6px;">Institutional Profile & Research Facilities</h3>
      <p style="color:var(--ink-secondary); font-size:14px; margin-bottom:20px;">Manage your university's specialization domains, research centers, and contact profile.</p>
      <form data-endpoint="/api/admin/universities">
        <input type="hidden" name="university_id" value="{university['id']}">
        <div class="form-row">
          <div>
            <label>Institution Name</label>
            <input name="name" value="{html.escape(university['name'])}" required>
          </div>
          <div>
            <label>District</label>
            <input name="district" value="{html.escape(university['district'])}" required>
          </div>
        </div>
        <label>Expertise Domains (comma separated)</label>
        <input name="domains" value="{html.escape(university['domains'])}" required>
        <label>Departments Involved</label>
        <input name="departments" value="{html.escape(str(university.get('departments') or ''))}" placeholder="e.g. Civil Engineering, Computer Science, Environmental Engineering">
        <label>Laboratories & Fabrication Facilities</label>
        <input name="laboratories" value="{html.escape(str(university.get('laboratories') or ''))}" placeholder="e.g. Advanced Water Testing Lab, IoT Prototyping Center">
        <label>Incubation Facilities & Research Hubs</label>
        <input name="incubation_facilities" value="{html.escape(str(university.get('incubation_facilities') or ''))}" placeholder="e.g. STEP Technology Incubation Hub">
        <label>Official Contact Email</label>
        <input name="contact_email" value="{html.escape(str(university.get('contact_email') or ''))}" required>
        <button type="submit" class="btn btn-primary" style="margin-top:10px;">Save Profile Changes</button>
      </form>
    </div>
    """

    return template.replace("__USER__", html.escape(user))\
                   .replace("__UNIVERSITY_HERO__", hero_html)\
                   .replace("__METRICS_BAR__", metrics_html)\
                   .replace("__CHALLENGES_CONTENT__", challenges_html)\
                   .replace("__TEAMS_CONTENT__", teams_html)\
                   .replace("__MILESTONES_CONTENT__", milestones_html)\
                   .replace("__OFFERS_CONTENT__", offers_html)\
                   .replace("__MESSAGES_CONTENT__", messages_html)\
                   .replace("__PROFILE_CONTENT__", profile_html)


def industry_for_user(user):
    return next((partner for partner in load_industry_partners() if str(partner.get("contact_email", "")).casefold() == user.casefold()), None)


def render_industry_dashboard(user: str) -> str:
    template = INDUSTRY_DASHBOARD_FILE.read_text(encoding="utf-8")
    partner = industry_for_user(user)
    if partner is None:
        error_hero = f"""
        <div class="hero-card">
          <span class="hero-eyebrow">Authentication Required</span>
          <h1 class="hero-title">Industry Partner Account Required</h1>
          <p class="hero-desc">The signed-in account (<strong>{html.escape(user)}</strong>) is not recognized as an industry or CSR partner. Please sign in with a registered partner email (e.g. <code>partner@jin.example</code>, <code>connect@alf.example</code>, or <code>innovation@etm.example</code>) or contact the portal administrator.</p>
          <div style="margin-top:20px;">
            <a href="/logout" class="btn btn-accent">Sign In with Partner Account</a>
          </div>
        </div>
        """
        return template.replace("__USER__", html.escape(user))\
                       .replace("__INDUSTRY_HERO__", error_hero)\
                       .replace("__METRICS_BAR__", "")\
                       .replace("__CHALLENGES_CONTENT__", "")\
                       .replace("__COMMITMENTS_CONTENT__", "")\
                       .replace("__NEW_OFFER_CONTENT__", "")\
                       .replace("__PIPELINE_CONTENT__", "")\
                       .replace("__MESSAGES_CONTENT__", "")\
                       .replace("__PROFILE_CONTENT__", "")

    approved_issues = [issue for issue in load_issues() if issue.get("moderation_status", "Pending") == "Approved"]
    my_offers = load_partner_offers(user)
    all_teams = load_all_teams_with_details()
    messages = load_messages(user)
    assignments = load_assignments()
    universities = load_universities()
    uni_map = {u["id"]: u["name"] for u in universities}
    
    active_offers_count = len(my_offers)
    accepted_offers_count = sum(1 for o in my_offers if o.get("status") in {"Accepted", "Delivered"})
    challenges_count = len(approved_issues)
    pipeline_teams_count = len(all_teams)

    domains_list = [d.strip() for d in str(partner.get("domains", "")).split(",") if d.strip()]
    domain_tags = "".join(f"<span class='partner-tag'>🏷️ {html.escape(d)}</span>" for d in domains_list)

    hero_html = f"""
    <div class="hero-card">
      <div class="hero-top">
        <div>
          <span class="hero-eyebrow">CSR & Corporate Collaboration Portal</span>
          <h1 class="hero-title">{html.escape(partner['name'])}</h1>
          <p class="hero-desc">Connect directly with university engineering teams and Jharkhand communities. Provide CSR grants, prototyping resources, testing grounds, and mentorship to scale high-impact grassroots innovations.</p>
          <div class="partner-meta-tags">
            <span class="partner-tag">🏢 Type: <strong>{html.escape(partner['partner_type'])}</strong></span>
            <span class="partner-tag">📍 District: <strong>{html.escape(partner['district'])}</strong></span>
            {domain_tags}
            <span class="partner-tag">✉️ {html.escape(partner.get('contact_email') or user)}</span>
          </div>
        </div>
      </div>
    </div>
    """

    metrics_html = f"""
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon gold">🤝</div>
        <div class="metric-info">
          <h4>Active Offers</h4>
          <div class="val">{active_offers_count}</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon green">✅</div>
        <div class="metric-info">
          <h4>Delivered / Accepted</h4>
          <div class="val">{accepted_offers_count}</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon blue">🌍</div>
        <div class="metric-info">
          <h4>Open Challenges</h4>
          <div class="val">{challenges_count}</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon coral">🔬</div>
        <div class="metric-info">
          <h4>University Teams</h4>
          <div class="val">{pipeline_teams_count}</div>
        </div>
      </div>
    </div>
    """

    # Tab 1: Explore State Challenges
    districts = sorted(list({i.get("district", "Ranchi") for i in approved_issues}))
    categories = sorted(list({i.get("category", "") for i in approved_issues if i.get("category")}))
    
    district_opts = "".join(f"<option value='{d}'>{html.escape(d)}</option>" for d in districts)
    category_opts = "".join(f"<option value='{c}'>{html.escape(c)}</option>" for c in categories)

    filter_html = f"""
    <div class="filter-bar">
      <span style="font-size:13px; font-weight:700; color:var(--ink-secondary);">🔍 Filters:</span>
      <select id="filter-district" onchange="filterChallenges()">
        <option value="">All Districts</option>
        {district_opts}
      </select>
      <select id="filter-domain" onchange="filterChallenges()">
        <option value="">All Domains</option>
        {category_opts}
      </select>
      <input id="filter-search" placeholder="Search keywords..." oninput="filterChallenges()">
    </div>
    """

    challenge_items = []
    for issue in approved_issues:
        iid = issue["id"]
        assignment = assignments.get(iid)
        assigned_uni_name = uni_map.get(assignment["university_id"]) if assignment else None
        uni_tag = f"<span class='status-pill accepted' style='font-size:11px;'>🏛️ Assigned to {html.escape(assigned_uni_name)}</span>" if assigned_uni_name else "<span class='status-pill pending' style='font-size:11px;'>Open for Assignment</span>"
        
        challenge_items.append(f"""
        <div class="challenge-item-card" data-district="{html.escape(issue.get('district',''))}" data-domain="{html.escape(issue.get('category',''))}">
          <div>
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:8px;">
              <span class="support-tag funding">{html.escape(issue.get('category','General'))}</span>
              {uni_tag}
            </div>
            <h3 class="card-title" style="margin-bottom:8px;">{html.escape(issue['title'])}</h3>
            <div class="meta-row">
              <span class="meta-item">📍 <strong>{html.escape(issue.get('district','Ranchi'))}</strong> {('· ' + html.escape(str(issue.get('block', '')))) if issue.get('block') else ''}</span>
              <span class="meta-item">👥 <strong>{issue.get('supporters', 0)} supporters</strong></span>
            </div>
            <p style="color:var(--ink-secondary); font-size:13px; line-height:1.5; margin-bottom:16px;">{html.escape(issue.get('description',''))}</p>
          </div>
          <div>
            <button class="btn btn-primary btn-sm" style="width:100%;" onclick="selectChallengeForOffer({iid})">🤝 Offer Support for This Challenge</button>
          </div>
        </div>
        """)
    challenges_html = filter_html + f"<div class='challenges-grid'>{''.join(challenge_items) if challenge_items else '<div class="empty-state"><h3>No Approved Challenges</h3><p>There are currently no moderated challenges open for partnership.</p></div>'}</div>"

    # Tab 2: Commitments Content
    if not my_offers:
        commitments_html = """
        <div class="empty-state">
          <h3>No Active Commitments</h3>
          <p>Explore the approved challenges catalogue to submit support offers for mentorship, seed funding, lab access, testing, or deployment.</p>
        </div>
        """
    else:
        offer_cards = []
        for o in my_offers:
            stype = o.get("support_type", "Mentorship")
            status = o.get("status", "Offered")
            pill_class = "accepted" if status == "Accepted" else ("delivered" if status == "Delivered" else ("declined" if status == "Declined" else "offered"))
            tag_class = stype.lower() if stype.lower() in {"mentorship", "funding", "prototyping", "testing", "deployment"} else "mentorship"
            
            offer_cards.append(f"""
            <div class="content-card">
              <div class="card-header-row">
                <div>
                  <span class="support-tag {tag_class}">{html.escape(stype)} Support</span>
                  <h3 class="card-title" style="margin-top:6px;">{html.escape(o.get('title','Societal Challenge'))}</h3>
                </div>
                <span class="status-pill {pill_class}">{html.escape(status)}</span>
              </div>
              <div class="meta-row">
                <span class="meta-item">📍 District: <strong>{html.escape(o.get('district','Ranchi'))}</strong></span>
                <span class="meta-item">🏛️ Block: <strong>{html.escape(o.get('block','N/A') or 'N/A')}</strong></span>
              </div>
              <p style="color:var(--ink-secondary); font-size:14px; line-height:1.6; margin-bottom:16px;"><strong>Offer Details:</strong> {html.escape(o.get('details',''))}</p>
              {f"<div style='margin-bottom:14px; font-size:13px; color:var(--primary-dark); background:var(--primary-light); padding:10px; border-radius:6px;'>📝 <strong>University / Admin Feedback:</strong> {html.escape(o['commitment_note'])}</div>" if o.get('commitment_note') else ""}
              <div style="display:flex; gap:10px; align-items:center;">
                <button class="btn btn-outline btn-sm" onclick="showTab('messages')">✉️ Message University Mentor</button>
              </div>
            </div>
            """)
        commitments_html = "".join(offer_cards)

    # Tab 3: New Offer Content
    issue_options = "".join(f"<option value='{i['id']}'>{html.escape(i['title'])} ({html.escape(i.get('district','Ranchi'))} · {html.escape(i.get('category',''))})</option>" for i in approved_issues)
    new_offer_html = f"""
    <div class="content-card" style="max-width:850px;">
      <h3 style="font-family:'Outfit',sans-serif; font-size:22px; margin-bottom:6px;">Submit Industry or CSR Support Offer</h3>
      <p style="color:var(--ink-secondary); font-size:14px; margin-bottom:20px;">Partner with university project teams and local communities by providing technical mentorship, CSR funding, fabrication facilities, testing labs, or deployment channels.</p>
      
      <form data-endpoint="/api/industry/offers">
        <label>Select Societal Challenge</label>
        <select name="issue_id" required>
          {issue_options or "<option disabled>No approved challenges available</option>"}
        </select>
        
        <label>Support Category</label>
        <select name="support_type" required>
          <option value="Mentorship">Mentorship & Technical Guidance (Engineering, Design, Business)</option>
          <option value="Funding">Seed Funding & CSR Grants (Equipment, Stipends, Travel)</option>
          <option value="Prototyping">Prototyping & Fabrication Lab Access (3D Printing, CNC, Electronics)</option>
          <option value="Testing">Testing & Validation (Field trials, QA, Certification labs)</option>
          <option value="Deployment">Commercial Pilot & Deployment (Scaling, Manufacturing, Distribution)</option>
        </select>
        
        <label>Commitment & Support Details</label>
        <textarea name="details" placeholder="Describe the concrete support you are offering (e.g. 'Rs. 2.5 Lakh seed grant + access to Ranchi testing facility + 10 hours monthly engineering mentorship')..." required></textarea>
        
        <button type="submit" class="btn btn-primary" {"disabled" if not approved_issues else ""}>Submit Commitment & Partnership Offer</button>
      </form>
    </div>
    """

    # Tab 4: Pipeline Content
    pipeline_cards = []
    for team in all_teams:
        status = team.get("status", "Forming")
        ms_list = load_milestones(team["id"])
        completed_ms = sum(1 for m in ms_list if m.get("status") == "Completed")
        
        pipeline_cards.append(f"""
        <div class="team-pipeline-card">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:8px;">
            <span class="support-tag prototyping">Team #{team['id']}</span>
            <span class="status-pill accepted">{html.escape(status)}</span>
          </div>
          <h3 class="card-title" style="font-size:18px; margin-bottom:6px;">{html.escape(team['name'])}</h3>
          <div style="font-size:13px; font-weight:600; color:var(--primary); margin-bottom:8px;">🏛️ {html.escape(team.get('university_name','University'))} ({html.escape(team.get('university_district','Jharkhand'))})</div>
          
          <div class="meta-row" style="margin-bottom:10px;">
            <span class="meta-item">🎯 Challenge: <strong>{html.escape(team.get('issue_title','Societal Challenge'))}</strong></span>
          </div>
          
          <div style="font-size:13px; color:var(--ink-secondary); margin-bottom:12px;">
            <div>👨‍🏫 Mentor: <strong>{html.escape(team['faculty_mentor'])}</strong></div>
            <div>👥 Members: {html.escape(', '.join(team['members']))}</div>
            <div>🏆 Milestones: <strong>{completed_ms}/{len(ms_list)} completed</strong></div>
          </div>
          
          {f"<div style='font-size:12px; color:var(--primary-dark); background:var(--primary-light); padding:8px; border-radius:6px; margin-bottom:12px;'>💡 <strong>IP / Patent:</strong> {html.escape(team['ip_outcome'])}</div>" if team.get('ip_outcome') else ""}
          {f"<div style='font-size:12px; color:var(--green); background:var(--green-light); padding:8px; border-radius:6px; margin-bottom:12px;'>🚀 <strong>Startup:</strong> {html.escape(team['startup_outcome'])}</div>" if team.get('startup_outcome') else ""}

          <button class="btn btn-outline btn-sm" style="width:100%;" onclick="selectChallengeForOffer({team['issue_id']})">🤝 Offer Support to This Team</button>
        </div>
        """)
    pipeline_html = f"<div class='pipeline-grid'>{''.join(pipeline_cards) if pipeline_cards else '<div class="empty-state"><h3>No University Projects Found</h3><p>University student teams will appear here once they form teams and begin prototyping.</p></div>'}</div>"

    # Tab 5: Messages Content
    msg_history = "".join(f"""
    <div style="background:var(--surface); border:1px solid var(--line); border-radius:var(--radius-sm); padding:14px 18px; margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:12px; color:var(--muted);">
        <span><strong>{html.escape(m['sender'])}</strong> ➔ <strong>{html.escape(m['recipient'])}</strong></span>
        <span>{html.escape(str(m.get('created_at','')))}</span>
      </div>
      <p style="color:var(--ink); font-size:14px;">{html.escape(m['message'])}</p>
    </div>
    """ for m in messages) or "<div class='empty-state' style='padding:24px;'><h3>No Messages Yet</h3><p>Direct project communications with faculty mentors and administrators will appear here.</p></div>"
    
    recipients_options = "".join(f"<option value='{r}'>{html.escape(r)}</option>" for r in sorted(known_recipients()) if r != user)

    messages_html = f"""
    <div style="display:grid; grid-template-columns:minmax(0,1.2fr) minmax(320px,0.8fr); gap:24px; align-items:flex-start;">
      <div class="content-card">
        <h3 style="font-family:'Outfit',sans-serif; font-size:20px; margin-bottom:16px;">Project Messages</h3>
        {msg_history}
      </div>
      <div class="content-card">
        <h3 style="font-family:'Outfit',sans-serif; font-size:20px; margin-bottom:16px;">Send Message to University Mentor</h3>
        <form data-endpoint="/api/messages">
          <label>Recipient</label>
          <select name="recipient" required>
            {recipients_options}
          </select>
          <label>Related Challenge ID (Optional)</label>
          <input name="related_id" type="number" placeholder="e.g., 1">
          <label>Message Content</label>
          <textarea name="message" placeholder="Type your partnership inquiry, mentorship schedule, or grant confirmation..." required></textarea>
          <button type="submit" class="btn btn-primary">Send Message</button>
        </form>
      </div>
    </div>
    """

    # Tab 6: Profile Content
    profile_html = f"""
    <div class="content-card" style="max-width:800px;">
      <h3 style="font-family:'Outfit',sans-serif; font-size:22px; margin-bottom:6px;">Industry Partner Profile</h3>
      <p style="color:var(--ink-secondary); font-size:14px; margin-bottom:20px;">Review your corporate details, district presence, and thematic focus domains.</p>
      <div class="card-subblock">
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; font-size:14px;">
          <div><strong style="color:var(--muted); font-size:11px; text-transform:uppercase;">Organization Name:</strong><br>{html.escape(partner['name'])}</div>
          <div><strong style="color:var(--muted); font-size:11px; text-transform:uppercase;">Partner Type:</strong><br>{html.escape(partner['partner_type'])}</div>
          <div><strong style="color:var(--muted); font-size:11px; text-transform:uppercase;">District:</strong><br>{html.escape(partner['district'])}</div>
          <div><strong style="color:var(--muted); font-size:11px; text-transform:uppercase;">Contact Email:</strong><br>{html.escape(partner['contact_email'])}</div>
        </div>
        <div style="margin-top:14px; font-size:14px;">
          <strong style="color:var(--muted); font-size:11px; text-transform:uppercase;">CSR & Innovation Domains:</strong><br>
          {html.escape(partner['domains'])}
        </div>
      </div>
    </div>
    """

    return template.replace("__USER__", html.escape(user))\
                   .replace("__INDUSTRY_HERO__", hero_html)\
                   .replace("__METRICS_BAR__", metrics_html)\
                   .replace("__CHALLENGES_CONTENT__", challenges_html)\
                   .replace("__COMMITMENTS_CONTENT__", commitments_html)\
                   .replace("__NEW_OFFER_CONTENT__", new_offer_html)\
                   .replace("__PIPELINE_CONTENT__", pipeline_html)\
                   .replace("__MESSAGES_CONTENT__", messages_html)\
                   .replace("__PROFILE_CONTENT__", profile_html)
def render_government_dashboard():
    metrics = load_dashboard_metrics()
    moderation = "".join(f"<li>{html.escape(str(row['status']))}: {row['total']}</li>" for row in metrics["moderation"])
    distribution = "".join(f"<li>{html.escape(str(row['district']))} · {html.escape(str(row['category']))}: {row['total']}</li>" for row in metrics["district_domains"])
    stages = "".join(f"<li>{html.escape(str(row['status']))}: {row['total']}</li>" for row in metrics["project_stages"])
    return f"<h1>Government dashboard</h1><p>Jharkhand societal innovation overview.</p><section><h2>Totals</h2><p>Issues: {metrics['total_issues']} · Proposals: {metrics['proposals']} · Assignments: {metrics['assignments']} · Universities: {metrics['universities']} · Industry partners: {metrics['industry_partners']} · Support offers: {metrics['support_offers']}</p></section><section><h2>Moderation</h2><ul>{moderation or '<li>No issue data</li>'}</ul></section><section><h2>District and domain distribution</h2><ul>{distribution or '<li>No issue data</li>'}</ul></section><section><h2>Project progress</h2><ul>{stages or '<li>No project teams</li>'}</ul></section>"
def notification_markup(user):
    notifications = load_notifications(user)
    if not notifications:
        return "<h2>Notifications</h2><p>No notifications.</p>"
    return "<h2>Notifications</h2>" + "".join(f"<p>{html.escape(item['message'])} · {html.escape(str(item['created_at']))}</p>" for item in notifications)
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
            f'</div></article>'
        )
    return "".join(cards)
def render_admin_issues():
    pending = [issue for issue in ISSUES if issue.get("moderation_status", "Pending") == "Pending"]
    if not pending:
        return "<p>No pending issues.</p>"
    return "".join(
        f"<article><h2>{html.escape(str(issue.get('title', 'Untitled issue')))}</h2><p>{html.escape(str(issue.get('description', '')))}</p><p>{html.escape(str(issue.get('district', 'Ranchi')))} · {html.escape(str(issue.get('block', '')))} · {html.escape(str(issue.get('category', '')))}</p><form><input type='hidden' name='issue_id' value='{issue['id']}'><textarea name='reason' placeholder='Reason for this decision' required></textarea><button name='status' value='Approved'>Approve</button><button name='status' value='Rejected'>Reject</button></form></article>"
        for issue in pending
    )
def render_industry_admin():
    partners = load_industry_partners()
    offers = load_all_partner_offers()
    offer_markup = "".join(f"<form class='offer-update'><input type='hidden' name='offer_id' value='{offer['id']}'><p>{html.escape(offer['partner_name'])} offered {html.escape(offer['support_type'])} for {html.escape(offer['title'])}</p><select name='status'><option>Offered</option><option>Accepted</option><option>Delivered</option><option>Declined</option></select><input name='note' placeholder='Commitment note'><button>Update commitment</button></form>" for offer in offers) or "<p>No support offers yet.</p>"
    return "<h2>Industry partner registration</h2><form class='industry-create'><input name='name' placeholder='Organization name' required><select name='partner_type'><option>Industry</option><option>Startup</option><option>MSME</option><option>CSR Organization</option><option>Research Laboratory</option></select><input name='district' placeholder='District' required><input name='domains' placeholder='Domains' required><input name='contact_email' placeholder='Contact email' required><button>Register partner</button></form><h2>Registered partners</h2>" + "".join(f"<p>{html.escape(partner['name'])} · {html.escape(partner['partner_type'])} · {html.escape(partner['contact_email'])}</p>" for partner in partners) + "<h2>Support commitments</h2>" + offer_markup
def render_university_issues():
    universities = load_universities()
    assignments = load_assignments()
    directory = "<h2>University registration</h2><form class='university-create'><input name='name' placeholder='University name' required><input name='district' placeholder='District' required><input name='domains' placeholder='Domains' required><input name='departments' placeholder='Departments'><input name='laboratories' placeholder='Laboratories'><input name='incubation_facilities' placeholder='Incubation facilities'><input name='contact_email' placeholder='Contact email' required><button type='submit'>Register university</button></form><h2>University profiles</h2>" + "".join(
        f"<form class='university-profile'><input type='hidden' name='university_id' value='{university['id']}'><input name='name' value='{html.escape(university['name'])}' required><input name='district' value='{html.escape(university['district'])}' required><input name='domains' value='{html.escape(university['domains'])}' required><input name='departments' value='{html.escape(university.get('departments') or '')}' placeholder='Departments'><input name='laboratories' value='{html.escape(university.get('laboratories') or '')}' placeholder='Laboratories'><input name='incubation_facilities' value='{html.escape(university.get('incubation_facilities') or '')}' placeholder='Incubation facilities'><input name='contact_email' value='{html.escape(university.get('contact_email') or '')}'><button type='submit'>Save profile</button></form>"
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
        ranked_universities = sorted(
            universities,
            key=lambda university: (
                issue_domain in str(university.get("domains", "")).casefold(),
                issue_district == str(university.get("district", "")).casefold(),
            ),
            reverse=True,
        )
        recommended = ranked_universities[0] if ranked_universities else None
        recommendation = f"<p><strong>Recommended:</strong> {html.escape(recommended['name'])} based on district and domain expertise.</p>" if recommended else ""
        current = f"<p>Assigned to university ID {assignment['university_id']} ({html.escape(assignment['status'])}).</p><p>{html.escape(str(assignment.get('response_reason') or ''))}</p><form class='response'><input type='hidden' name='issue_id' value='{issue['id']}'><select name='status'><option>Accepted</option><option>Rejected</option><option>Needs clarification</option></select><input name='reason' placeholder='University response' required><button type='submit'>Save response</button></form>" if assignment else "<p>Not assigned.</p>"
        issue_teams = [team for team in teams if team["issue_id"] == issue["id"]]
        team_markup = "".join(render_dashboard_team(team) for team in issue_teams)
        cards.append(f"<article><h2>{html.escape(str(issue['title']))}</h2><p>{html.escape(str(issue.get('description', '')))}</p><p>{html.escape(str(issue.get('district', 'Ranchi')))} · {html.escape(str(issue.get('block', '')))} · {html.escape(str(issue.get('category', '')))}</p>{recommendation}{current}<form class='assignment'><input type='hidden' name='issue_id' value='{issue['id']}'><select name='university_id' required>{options}</select><button type='submit'>Assign university</button></form>{team_markup}<form class='team'><input type='hidden' name='issue_id' value='{issue['id']}'><input type='hidden' name='university_id' value='{assignment['university_id'] if assignment else ''}'><input name='name' placeholder='Team name' required><input name='faculty_mentor' placeholder='Faculty mentor email' required><input name='members' placeholder='Student emails, comma separated' required><button type='submit'>Create project team</button></form></article>")
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
            self.send_html(render_university_dashboard(user))
            return
        if path == "/industry-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if industry_for_user(user) is None:
                self.send_error(403)
                return
            self.send_html(render_industry_dashboard(user))
            return
        if path == "/government-dashboard":
            user = self.session_user()
            if user is None:
                self.redirect("/login")
                return
            if not is_admin(user) and industry_for_user(user) is None:
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
            self.send_json({"issue_id": issue_id, "status": status})
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
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid support offer."}, status=400)
                return
            if support_type not in {"Mentorship", "Funding", "Prototyping", "Testing", "Deployment"} or not details:
                self.send_json({"message": "Choose a support type and provide details."}, status=400)
                return
            if not any(issue.get("id") == issue_id and issue.get("moderation_status", "Pending") == "Approved" for issue in ISSUES):
                self.send_json({"message": "Only approved issues can receive offers."}, status=400)
                return
            offer = create_support_offer(issue_id, partner["id"], support_type, details)
            issue = next((item for item in ISSUES if item.get("id") == issue_id), None)
            if issue and issue.get("reporter"):
                create_notification(issue["reporter"], f"An industry partner offered {support_type.lower()} support for your issue.", "offer", offer["id"])
            self.send_json({"message": "Support offer submitted.", "offer": offer}, status=201)
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
            if not update_university(university_id, name, district, domains, departments, laboratories, incubation_facilities, contact_email):
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
                values = {field: str(data.get(field, "")).strip()[:limit] for field, limit in {"name": 255, "district": 100, "domains": 1000, "departments": 1000, "laboratories": 1000, "incubation_facilities": 1000, "contact_email": 255}.items()}
            except (TypeError, ValueError, json.JSONDecodeError):
                self.send_json({"message": "Invalid university profile."}, status=400)
                return
            if not values["name"] or not values["district"] or not values["domains"] or "@" not in values["contact_email"]:
                self.send_json({"message": "Name, district, domains, and a valid contact email are required."}, status=400)
                return
            try:
                university = create_university(**values)
            except Exception:
                self.send_json({"message": "A university with this contact email may already exist."}, status=400)
                return
            self.send_json({"message": "University registered.", "university": university}, status=201)
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
        portal_role = form.get("portal_role", ["citizen"])[0]
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
        destination = {
          "government": "/government-dashboard",
          "university": "/university-dashboard",
          "industry": "/industry-dashboard",
        }.get(portal_role, "/")
        self.redirect(destination,f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
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
