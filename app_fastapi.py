"""Production FastAPI application entry point for Societal Innovation Collaboration Portal.

Run with: uvicorn app_fastapi:app --reload --port 8000
"""

from __future__ import annotations

import base64
import binascii
import html
import json
import secrets
from typing import Any, Optional

try:
    from fastapi import FastAPI, Request, HTTPException, Depends, Response
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
except ImportError:
    FastAPI = None

from login_users import authenticate, create_account, is_admin, professional_profile
from community import ISSUES, add_issue, render_page, upvote_issue
from storage import (
    assign_issue, check_rate_limit, create_industry_partner, create_message,
    create_milestone, create_notification, create_session_record,
    create_support_offer, create_team, create_university, create_university_report, delete_session_record,
    get_proof, get_proposal_visual, get_session_user, insert_proposal,
    load_milestones, load_teams, load_university_assignments, load_universities,
    moderate_issue, update_assignment, update_milestone, update_offer_commitment,
    update_proposal, update_team_outcomes, update_team_status, update_university,
)
from AI_model import inspect_image_proof, sanitize_and_reencode_image
from evidence_review import review_issue_evidence
from map import (
    load_login_page, load_university_login_page, load_university_register_page, load_register_page,
    build_proposals_page, build_professionals_page,
    render_admin_issues, render_industry_admin, render_university_issues, proposal_issue, known_recipients,
    render_university_dashboard, render_industry_dashboard, render_government_dashboard,
    auto_assign_issue_to_best_university, auto_assign_tasks_to_university,
    notification_markup, render_messages, render_user_issues, MAP_PAGE, university_for_user, industry_for_user,
    ADMIN_PAGE, UNIVERSITY_PAGE, CITIZEN_PAGE_FILE, UNIVERSITY_DASHBOARD_FILE,
    INDUSTRY_DASHBOARD_FILE, GOVERNMENT_DASHBOARD_FILE, PROPOSALS
)

if FastAPI is not None:
    app = FastAPI(
        title="Societal Innovation Collaboration Portal",
        description="Jharkhand Civic Issue Reporting & Collaboration API",
        version="1.0.0"
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "127.0.0.1"
        if request.method == "POST" and not check_rate_limit(client_ip, max_requests=60, window_seconds=60):
            return JSONResponse(status_code=429, content={"message": "Rate limit exceeded. Please wait a minute."})
        return await call_next(request)

    async def get_current_user(request: Request) -> Optional[str]:
        session_id = request.cookies.get("session_id")
        if not session_id:
            return None
        return get_session_user(session_id)

    def require_user(current_user: Optional[str]) -> str:
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return current_user

    def require_admin(current_user: Optional[str]) -> str:
        user = require_user(current_user)
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Admin authorization required")
        return user

    def require_json_issue_membership(issue_id: int, user: str) -> None:
        assignment_ids = {assignment["issue_id"] for assignment in load_university_assignments(user)}
        if issue_id not in assignment_ids:
            raise HTTPException(status_code=403, detail="Issue is not assigned to this university")

    @app.get("/", response_class=HTMLResponse)
    async def index(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            return RedirectResponse(url="/login", status_code=303)
        issues_json = json.dumps(ISSUES).replace("</", "<\\/")
        html_content = MAP_PAGE.replace("__ISSUES__", issues_json).replace("__USER__", html.escape(current_user))
        return HTMLResponse(content=html_content)

    @app.get("/login", response_class=HTMLResponse)
    async def get_login():
        return HTMLResponse(content=load_login_page(""))

    @app.post("/login")
    async def post_login(request: Request):
        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        if not authenticate(email, password):
            return HTMLResponse(content=load_login_page('<p class="error">Email or password is incorrect.</p>'), status_code=401)
        session_id = create_session_record(email)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
        return response

    @app.get("/university/login", response_class=HTMLResponse)
    @app.get("/university-login", response_class=HTMLResponse)
    async def get_university_login():
        return HTMLResponse(content=load_university_login_page(""))

    @app.get("/university/register", response_class=HTMLResponse)
    @app.get("/university-register", response_class=HTMLResponse)
    async def get_university_register():
        return HTMLResponse(content=load_university_register_page(""))

    @app.post("/university/login")
    @app.post("/university-login")
    async def post_university_login(request: Request):
        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        if not authenticate(email, password):
            return HTMLResponse(content=load_university_login_page("Email or password is incorrect."), status_code=401)
        university = university_for_user(email)
        if university is None:
            return HTMLResponse(content=load_university_login_page("This account is not linked to a registered university profile."), status_code=403)
        session_id = create_session_record(email)
        response = RedirectResponse(url="/university-dashboard", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
        return response

    @app.post("/university/register")
    @app.post("/university-register")
    async def post_university_register(request: Request):
        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        confirm_password = str(form.get("confirm_password", ""))
        values = {
            "name": str(form.get("name", "")).strip()[:255],
            "district": str(form.get("district", "")).strip()[:100],
            "domains": str(form.get("domains", "")).strip()[:1000],
            "expertise": str(form.get("expertise", "")).strip()[:1500],
            "departments": str(form.get("departments", "")).strip()[:1000],
            "laboratories": str(form.get("laboratories", "")).strip()[:1000],
            "incubation_facilities": str(form.get("incubation_facilities", "")).strip()[:1000],
            "contact_email": email,
        }
        if password != confirm_password:
            return HTMLResponse(content=load_university_register_page('<p class="error">Passwords do not match.</p>'), status_code=400)
        if not values["name"] or not values["district"] or not values["domains"] or not values["expertise"] or "@" not in email:
            return HTMLResponse(content=load_university_register_page('<p class="error">University name, district, domains, expertise, and valid email are required.</p>'), status_code=400)
        if university_for_user(email) is not None:
            return HTMLResponse(content=load_university_register_page('<p class="error">A university profile already uses this email.</p>'), status_code=400)
        created, message = create_account(email, password)
        if not created:
            return HTMLResponse(content=load_university_register_page(f'<p class="error">{html.escape(message)}</p>'), status_code=400)
        university = create_university(**values)
        assigned = auto_assign_tasks_to_university(university)
        assignment_text = f" AI assigned {len(assigned)} approved task(s) to your dashboard." if assigned else " No approved matching tasks are available yet."
        return HTMLResponse(content=load_university_register_page(f'<p class="success">University registered successfully.{assignment_text} You can sign in now.</p>'))

    @app.get("/logout")
    async def logout(request: Request):
        session_id = request.cookies.get("session_id")
        if session_id:
            delete_session_record(session_id)
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(key="session_id")
        return response

    @app.get("/register", response_class=HTMLResponse)
    async def get_register():
        return HTMLResponse(content=load_register_page(""))

    @app.post("/register")
    async def post_register(request: Request):
        form = await request.form()
        email = str(form.get("email", "")).strip().lower()
        password = str(form.get("password", ""))
        confirm_password = str(form.get("confirm_password", ""))
        if password != confirm_password:
            return HTMLResponse(content=load_register_page('<p class="error">Passwords do not match.</p>'), status_code=400)
        created, message = create_account(email, password)
        if not created:
            return HTMLResponse(content=load_register_page(f'<p class="error">{html.escape(message)}</p>'), status_code=400)
        return RedirectResponse(url="/login", status_code=303)

    @app.get("/community", response_class=HTMLResponse)
    async def community(request: Request, lat: Optional[float] = None, lng: Optional[float] = None, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            return RedirectResponse(url="/login", status_code=303)
        return HTMLResponse(content=render_page(current_user, lat, lng))

    @app.get("/proposals", response_class=HTMLResponse)
    async def proposals(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            return RedirectResponse(url="/login", status_code=303)
        return HTMLResponse(content=build_proposals_page(current_user))

    @app.get("/professionals", response_class=HTMLResponse)
    async def professionals(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            return RedirectResponse(url="/login", status_code=303)
        return HTMLResponse(content=build_professionals_page(current_user))

    @app.get("/citizen-dashboard", response_class=HTMLResponse)
    @app.get("/my-issues", response_class=HTMLResponse)
    async def citizen_dashboard(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            return RedirectResponse(url="/login", status_code=303)
        template = CITIZEN_PAGE_FILE.read_text(encoding="utf-8")
        return HTMLResponse(content=template.replace("__USER__", html.escape(current_user)).replace("__ISSUES__", render_user_issues(current_user)))

    @app.get("/university-dashboard", response_class=HTMLResponse)
    async def university_dashboard(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user or university_for_user(current_user) is None:
            raise HTTPException(status_code=403, detail="University account required")
        template = UNIVERSITY_DASHBOARD_FILE.read_text(encoding="utf-8")
        return HTMLResponse(content=template.replace("__ASSIGNMENTS__", render_university_dashboard(current_user)))

    @app.get("/industry-dashboard", response_class=HTMLResponse)
    async def industry_dashboard(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user or industry_for_user(current_user) is None:
            raise HTTPException(status_code=403, detail="Industry account required")
        template = INDUSTRY_DASHBOARD_FILE.read_text(encoding="utf-8")
        return HTMLResponse(content=template.replace("__CONTENT__", render_industry_dashboard(current_user)))

    @app.get("/government-dashboard", response_class=HTMLResponse)
    async def government_dashboard(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user or not is_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin authorization required")
        template = GOVERNMENT_DASHBOARD_FILE.read_text(encoding="utf-8")
        return HTMLResponse(content=template.replace("__CONTENT__", render_government_dashboard()))

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            return RedirectResponse(url="/login", status_code=303)
        require_admin(current_user)
        return HTMLResponse(content=ADMIN_PAGE.replace("__ISSUES__", render_admin_issues()))

    @app.get("/universities", response_class=HTMLResponse)
    async def universities_page(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            return RedirectResponse(url="/login", status_code=303)
        require_admin(current_user)
        return HTMLResponse(content=UNIVERSITY_PAGE.replace("__ISSUES__", render_university_issues()))

    @app.get("/industry-admin", response_class=HTMLResponse)
    async def industry_admin_page(current_user: Optional[str] = Depends(get_current_user)):
        require_admin(current_user)
        page = (
            "<!doctype html><html><body>"
            f"{render_industry_admin()}"
            "<script>"
            "document.querySelector('.industry-create').onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/industry-partners',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});if(response.ok)location.reload();else alert((await response.json()).message||'Registration failed')};"
            "document.querySelectorAll('.offer-update').forEach(form=>form.onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/admin/offer-commitments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});if(response.ok)location.reload();else alert((await response.json()).message||'Commitment update failed')})"
            "</script></body></html>"
        )
        return HTMLResponse(content=page)

    @app.get("/notifications", response_class=HTMLResponse)
    async def notifications_page(current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        return HTMLResponse(content=f"<!doctype html><html><body>{notification_markup(user)}</body></html>")

    @app.get("/messages", response_class=HTMLResponse)
    async def messages_page(current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        return HTMLResponse(content=f"<!doctype html><html><body>{render_messages(user)}<script>document.querySelector('#message-form').onsubmit=async event=>{{event.preventDefault();const response=await fetch('/api/messages',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))}});if(response.ok)location.reload();else alert((await response.json()).message||'Message failed')}};</script></body></html>")

    @app.get("/proof/{proof_id}")
    async def get_proof_image(proof_id: str):
        proof = get_proof(proof_id)
        if not proof:
            raise HTTPException(status_code=404, detail="Proof not found")
        return Response(content=proof[1], media_type=proof[0])

    @app.get("/proposal-visual/{proposal_id}")
    async def get_proposal_visual_image(proposal_id: int):
        visual = get_proposal_visual(proposal_id)
        if not visual:
            raise HTTPException(status_code=404, detail="Proposal visual not found")
        return Response(content=visual[1], media_type=visual[0])

    @app.get("/api/issues")
    async def list_issues_api():
        return JSONResponse(content=ISSUES)

    @app.post("/api/issues")
    async def create_issue_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        try:
            data = await request.json()
            data["lat"] = float(data["lat"])
            data["lng"] = float(data["lng"])
            data["district"] = str(data.get("district", "Ranchi")).strip() or "Ranchi"
            data["block"] = str(data.get("block", "")).strip()
            data["reporter"] = current_user
            encoded_proof = data.pop("proof_image", "")
            proof_type = data.pop("proof_type", "image/jpeg")
            if proof_type not in {"image/jpeg", "image/png", "image/webp"}:
                return JSONResponse(status_code=415, content={"message": "Unsupported proof image type"})
            proof_bytes = base64.b64decode(encoded_proof, validate=True) if encoded_proof else b""
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, binascii.Error):
            return JSONResponse(status_code=400, content={"message": "Invalid issue data."})
        if len(proof_bytes) > 8 * 1024 * 1024:
            return JSONResponse(status_code=413, content={"message": "Proof image is larger than 8 MB"})
        if proof_bytes:
            proof_bytes, proof_type = sanitize_and_reencode_image(proof_bytes, proof_type)
            proof = inspect_image_proof(proof_bytes, data["lat"], data["lng"])
            if proof["status"] == "mismatch":
                return JSONResponse(status_code=422, content=proof)
            data.update({"proof_status": proof["status"], "proof_message": proof["message"]})
            data["proof_id"] = secrets.token_urlsafe(12)
            data["_proof_type"] = proof_type
            data["_proof_data"] = proof_bytes
        created = add_issue(data)
        if created.get("result") == "new" and created.get("issue"):
            assignment = auto_assign_issue_to_best_university(created["issue"])
            if assignment:
                created["assignment"] = {
                    "university_id": assignment["university"]["id"],
                    "university_name": assignment["university"]["name"],
                    "score": assignment["score"],
                }
        return JSONResponse(status_code=201 if created["result"] == "new" else 200, content=created)

    @app.post("/api/issues/{issue_id}/upvote")
    async def upvote_issue_api(issue_id: int, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        supported, supporters = upvote_issue(issue_id, user)
        if not supported:
            raise HTTPException(status_code=404, detail="Issue not found or already supported")
        return JSONResponse(content={"supporters": supporters})

    @app.post("/api/admin/issues")
    async def moderate_issue_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_admin(current_user)
        try:
            data = await request.json()
            issue_id = int(data["issue_id"])
            decision = str(data["status"])
            reason = str(data.get("reason", "")).strip()
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid moderation data."})
        if decision not in {"Approved", "Rejected", "Archived"} or not reason or len(reason) > 1000:
            return JSONResponse(status_code=400, content={"message": "Choose a valid decision and provide a reason."})
        if not moderate_issue(issue_id, decision, reason, user):
            return JSONResponse(status_code=404, content={"message": "Issue not found."})
        issue = next((item for item in ISSUES if item.get("id") == issue_id), None)
        if issue is not None:
            issue.update({"moderation_status": decision, "moderation_reason": reason, "moderated_by": user})
            if issue.get("reporter"):
                create_notification(issue["reporter"], f"Your issue '{issue.get('title', 'issue')}' was {decision.lower()}.", "issue", issue_id)
            if decision == "Approved":
                auto_assign_issue_to_best_university(issue)
        return JSONResponse(content={"status": decision, "issue_id": issue_id})

    @app.post("/api/admin/assignments")
    async def assign_issue_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_admin(current_user)
        try:
            data = await request.json()
            issue_id = int(data["issue_id"])
            university_id = int(data["university_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid assignment data."})
        if not assign_issue(issue_id, university_id, user):
            return JSONResponse(status_code=404, content={"message": "Issue or university not found."})
        university = next((item for item in load_universities() if item["id"] == university_id), None)
        if university and university.get("contact_email"):
            create_notification(university["contact_email"], f"A challenge was assigned to {university['name']}.", "assignment", issue_id)
        return JSONResponse(content={"issue_id": issue_id, "university_id": university_id, "status": "Assigned"})

    @app.post("/api/admin/assignment-response")
    async def admin_assignment_response_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        require_admin(current_user)
        try:
            data = await request.json()
            issue_id = int(data["issue_id"])
            assignment_status = str(data["status"])
            reason = str(data.get("reason", "")).strip()
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid university response."})
        if assignment_status not in {"Accepted", "Rejected", "Needs clarification"} or not reason or len(reason) > 1000:
            return JSONResponse(status_code=400, content={"message": "Choose a valid response and provide a reason."})
        if not update_assignment(issue_id, assignment_status, reason):
            return JSONResponse(status_code=404, content={"message": "Assignment not found."})
        return JSONResponse(content={"issue_id": issue_id, "status": assignment_status})

    @app.post("/api/university/reports")
    async def create_university_report_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        university = university_for_user(current_user)
        if not university:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        issue_id = int(data["issue_id"])
        title = str(data["title"]).strip()
        summary = str(data["summary"]).strip()
        deliverables = str(data.get("deliverables", "")).strip()
        if not title or not summary:
            return JSONResponse(status_code=400, content={"message": "Title and summary are required."})
        report = create_university_report(issue_id, university["id"], current_user, title, summary, deliverables)
        create_notification("admin@jharkhand.gov.in", f"University '{university['name']}' submitted a project report: '{title}'", "report", issue_id)
        return JSONResponse(status_code=201, content={"message": "Report submitted successfully.", "report": report})

    @app.post("/api/university/assignment-response")
    async def university_assignment_response_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        university = university_for_user(current_user)
        if not university:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        issue_id = int(data["issue_id"])
        status = str(data["status"])
        reason = str(data.get("reason", "")).strip()
        require_json_issue_membership(issue_id, current_user)
        if status not in {"Accepted", "Rejected", "Needs clarification"} or not reason:
            return JSONResponse(status_code=400, content={"message": "Choose a valid response and provide a reason."})
        update_assignment(issue_id, status, reason)
        create_notification("admin@jharkhand.gov.in", f"University '{university['name']}' has {status.upper()} assignment for Issue #{issue_id}. Reason: {reason}", "assignment_response", issue_id)
        return JSONResponse(status_code=200, content={"issue_id": issue_id, "status": status})

    @app.post("/api/university/teams")
    async def create_university_team_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        university = university_for_user(current_user)
        if not university:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        issue_id = int(data["issue_id"])
        university_id = int(data["university_id"])
        name = str(data["name"]).strip()[:150]
        mentor = str(data["faculty_mentor"]).strip()[:255]
        members = [str(m).strip()[:255] for m in data.get("members", []) if str(m).strip()]
        if university_id != university["id"]:
            raise HTTPException(status_code=403, detail="University mismatch")
        require_json_issue_membership(issue_id, current_user)
        if not name or not mentor or not members:
            return JSONResponse(status_code=400, content={"message": "Team name, faculty mentor, and student emails are required."})
        team = create_team(issue_id, university_id, name, mentor, members)
        return JSONResponse(status_code=201, content={"message": "Project team created.", "team": team})

    @app.post("/api/university/team-status")
    async def update_team_status_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        university = university_for_user(user)
        if not university:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        team_id = int(data["team_id"])
        team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
        if team is None:
            raise HTTPException(status_code=403, detail="Team does not belong to this university")
        team_status = str(data.get("status", ""))
        if team_status not in {"Team Formed", "Prototype", "Pilot", "Deployed", "Impact Measured"}:
            return JSONResponse(status_code=400, content={"message": "Invalid project stage."})
        update_team_status(team_id, team_status, user, str(data.get("note", "")).strip()[:1000])
        return JSONResponse(content={"team_id": team_id, "status": team_status})

    @app.post("/api/university/milestones")
    async def create_milestone_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        university = university_for_user(user)
        if not university:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        team_id = int(data["team_id"])
        team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
        if team is None:
            raise HTTPException(status_code=403, detail="Team does not belong to this university")
        title = str(data.get("title", "")).strip()[:200]
        if not title:
            return JSONResponse(status_code=400, content={"message": "Milestone title is required."})
        milestone = create_milestone(team_id, title, str(data.get("due_date", "")).strip(), str(data.get("deliverable", "")).strip()[:1000])
        return JSONResponse(status_code=201, content={"message": "Milestone added.", "milestone": milestone})

    @app.post("/api/university/milestone-status")
    async def update_milestone_status_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        university = university_for_user(user)
        if not university:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        team_id = int(data["team_id"])
        milestone_id = int(data["milestone_id"])
        team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
        if team is None or not any(milestone["id"] == milestone_id for milestone in load_milestones(team_id)):
            raise HTTPException(status_code=403, detail="Milestone does not belong to this university")
        milestone_status = str(data.get("status", ""))
        if milestone_status not in {"Pending", "In Progress", "Completed"}:
            return JSONResponse(status_code=400, content={"message": "Invalid milestone status."})
        update_milestone(milestone_id, milestone_status, str(data.get("testing_result", "")).strip()[:2000])
        return JSONResponse(content={"milestone_id": milestone_id, "status": milestone_status})

    @app.post("/api/university/team-outcomes")
    async def update_team_outcomes_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        university = university_for_user(user)
        if not university:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        team_id = int(data["team_id"])
        team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
        if team is None:
            raise HTTPException(status_code=403, detail="Team does not belong to this university")
        update_team_outcomes(
            team_id,
            str(data.get("ip_outcome", "")).strip()[:2000],
            str(data.get("startup_outcome", "")).strip()[:2000],
            str(data.get("impact_summary", "")).strip()[:3000],
        )
        return JSONResponse(content={"team_id": team_id, "status": "saved"})

    @app.post("/api/industry/offers")
    async def create_industry_offer_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        partner = industry_for_user(user)
        if partner is None:
            raise HTTPException(status_code=403, detail="Industry account required")
        try:
            data = await request.json()
            issue_id = int(data["issue_id"])
            support_type = str(data["support_type"]).strip()
            details = str(data["details"]).strip()[:3000]
            funding_amount = int(data.get("funding_amount") or 0)
            resources = str(data.get("resources", "")).strip()[:1000]
            timeline = str(data.get("timeline", "")).strip()[:100]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid support offer."})
        allowed_types = {
            "Mentorship", "Funding", "Prototyping", "Testing", "Deployment",
            "Co-development", "Technology Transfer", "Pilot Implementation",
            "CSR / Seed Funding", "Prototyping Facility", "Testing & Validation", "Deployment & Scaling",
        }
        if support_type not in allowed_types or not details:
            return JSONResponse(status_code=400, content={"message": "Choose a valid support type and provide details."})
        if not any(issue.get("id") == issue_id and issue.get("moderation_status", "Pending") == "Approved" for issue in ISSUES):
            return JSONResponse(status_code=400, content={"message": "Only approved issues can receive offers."})
        offer = create_support_offer(issue_id, partner["id"], support_type, details, funding_amount, resources, timeline)
        issue = next((item for item in ISSUES if item.get("id") == issue_id), None)
        if issue and issue.get("reporter"):
            create_notification(issue["reporter"], f"Industry partner '{partner['name']}' pledged {support_type} support for your issue.", "offer", offer["id"])
        create_notification("admin@jharkhand.gov.in", f"Industry partner '{partner['name']}' pledged {support_type} for Issue #{issue_id}.", "offer", offer["id"])
        return JSONResponse(status_code=201, content={"message": "Support offer submitted.", "offer": offer})

    @app.post("/api/messages")
    async def create_message_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        try:
            data = await request.json()
            recipient = str(data["recipient"]).strip().lower()
            message = str(data["message"]).strip()[:3000]
            related_id = int(data["related_id"]) if data.get("related_id") else None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid message."})
        if recipient not in known_recipients() or not message:
            return JSONResponse(status_code=400, content={"message": "Choose a known recipient and provide a message."})
        sent = create_message(user, recipient, message, "project" if related_id else "", related_id)
        create_notification(recipient, f"New project message from {user}.", "message", sent["id"])
        return JSONResponse(status_code=201, content={"message": "Message sent.", "message_id": sent["id"]})

    @app.post("/api/admin/universities")
    async def update_university_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        require_admin(current_user)
        try:
            data = await request.json()
            university_id = int(data["university_id"])
            values = {field: str(data.get(field, "")).strip()[:limit] for field, limit in {"name": 255, "district": 100, "domains": 1000, "expertise": 1500, "departments": 1000, "laboratories": 1000, "incubation_facilities": 1000, "contact_email": 255}.items()}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid university profile."})
        if not values["name"] or not values["district"] or not values["domains"]:
            return JSONResponse(status_code=400, content={"message": "Name, district, and domains are required."})
        if not update_university(university_id, **values):
            return JSONResponse(status_code=404, content={"message": "University not found."})
        return JSONResponse(content={"message": "University profile updated.", "university_id": university_id})

    @app.post("/api/admin/universities/create")
    async def create_university_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        require_admin(current_user)
        try:
            data = await request.json()
            values = {field: str(data.get(field, "")).strip()[:limit] for field, limit in {"name": 255, "district": 100, "domains": 1000, "expertise": 1500, "departments": 1000, "laboratories": 1000, "incubation_facilities": 1000, "contact_email": 255}.items()}
        except (TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid university profile."})
        if not values["name"] or not values["district"] or not values["domains"] or not values["expertise"] or "@" not in values["contact_email"]:
            return JSONResponse(status_code=400, content={"message": "Name, district, domains, expertise, and a valid contact email are required."})
        try:
            university = create_university(**values)
        except Exception:
            return JSONResponse(status_code=400, content={"message": "A university with this contact email may already exist."})
        auto_assign_tasks_to_university(university)
        return JSONResponse(status_code=201, content={"message": "University registered.", "university": university})

    @app.post("/api/admin/industry-partners")
    async def create_industry_partner_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        require_admin(current_user)
        try:
            data = await request.json()
            values = {field: str(data.get(field, "")).strip()[:limit] for field, limit in {"name": 255, "partner_type": 50, "district": 100, "domains": 1000, "contact_email": 255}.items()}
        except (TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid industry partner profile."})
        if not all(values.values()) or "@" not in values["contact_email"]:
            return JSONResponse(status_code=400, content={"message": "All partner fields and a valid contact email are required."})
        try:
            partner = create_industry_partner(**values)
        except Exception:
            return JSONResponse(status_code=400, content={"message": "A partner with this email may already exist."})
        return JSONResponse(status_code=201, content={"message": "Industry partner registered.", "partner": partner})

    @app.post("/api/admin/offer-commitments")
    async def update_offer_commitment_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        require_admin(current_user)
        try:
            data = await request.json()
            offer_id = int(data["offer_id"])
            offer_status = str(data["status"])
            note = str(data.get("note", "")).strip()[:2000]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid commitment update."})
        if offer_status not in {"Offered", "Accepted", "Delivered", "Declined"}:
            return JSONResponse(status_code=400, content={"message": "Invalid commitment status."})
        if not update_offer_commitment(offer_id, offer_status, note):
            return JSONResponse(status_code=404, content={"message": "Support offer not found."})
        return JSONResponse(content={"offer_id": offer_id, "status": offer_status})

    @app.post("/api/admin/teams")
    async def admin_create_team_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        require_admin(current_user)
        try:
            data = await request.json()
            issue_id = int(data["issue_id"])
            university_id = int(data["university_id"])
            name = str(data["name"]).strip()[:150]
            mentor = str(data["faculty_mentor"]).strip()[:255]
            members = [str(member).strip()[:255] for member in data.get("members", []) if str(member).strip()]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid team data."})
        if not name or not mentor or not members or not university_id:
            return JSONResponse(status_code=400, content={"message": "Team name, faculty mentor, and students are required."})
        try:
            team = create_team(issue_id, university_id, name, mentor, members)
        except Exception:
            return JSONResponse(status_code=400, content={"message": "The issue or university assignment is invalid."})
        return JSONResponse(status_code=201, content={"message": "Project team created.", "team": team})

    @app.post("/api/proposals")
    async def create_proposal_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        try:
            data = await request.json()
            issue_id = int(data.get("issue_id"))
            title = str(data.get("title", "")).strip()
            description = str(data.get("description", "")).strip()
            visual = data.get("visual", "")
            visual_type = data.get("visual_type", "")
        except (ValueError, TypeError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid proposal data."})
        if not title:
            return JSONResponse(status_code=400, content={"message": "Proposal title is required."})
        if not description:
            return JSONResponse(status_code=400, content={"message": "Proposal description is required."})
        if proposal_issue(issue_id) is None:
            return JSONResponse(status_code=404, content={"message": "The selected issue was not found."})
        try:
            visual_data = base64.b64decode(visual, validate=True) if visual else b""
        except (ValueError, binascii.Error):
            return JSONResponse(status_code=400, content={"message": "Invalid proposal visual."})
        if len(visual_data) > 8 * 1024 * 1024:
            return JSONResponse(status_code=413, content={"message": "Proposal visual is larger than 8 MB."})
        proposal = insert_proposal({"issue_id": issue_id, "title": title[:120], "description": description[:3000], "author": user, "visual": "", "visual_type": visual_type, "_visual_data": visual_data})
        PROPOSALS.append(proposal)
        return JSONResponse(status_code=201, content={"message": "Proposal published.", "proposal": proposal})

    @app.post("/api/proposals/{proposal_id}/vote")
    async def vote_proposal_api(proposal_id: int, current_user: Optional[str] = Depends(get_current_user)):
        require_user(current_user)
        proposal = next((item for item in PROPOSALS if item["id"] == proposal_id), None)
        if proposal is None:
            return JSONResponse(status_code=404, content={"message": "Proposal not found."})
        proposal["votes"] += 1
        update_proposal(proposal)
        return JSONResponse(content={"votes": proposal["votes"], "result": "voted"})

    @app.post("/api/proposals/{proposal_id}/review")
    async def review_proposal_api(proposal_id: int, request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        profile = professional_profile(user)
        if profile is None:
            return JSONResponse(status_code=403, content={"message": "Only verified professionals can submit reviews."})
        proposal = next((item for item in PROPOSALS if item["id"] == proposal_id), None)
        if proposal is None:
            return JSONResponse(status_code=404, content={"message": "Proposal not found."})
        try:
            data = await request.json()
            decision = str(data.get("decision", "")).strip()
            explanation = str(data.get("explanation", "")).strip()
        except (ValueError, TypeError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid review data."})
        result, reviewed = review_issue_evidence(PROPOSALS, proposal_id, profile.get("name", user), decision, explanation)
        if result == "invalid":
            return JSONResponse(status_code=400, content={"message": "Choose a valid decision and provide an explanation."})
        update_proposal(reviewed)
        return JSONResponse(content={"message": "Review saved.", "result": "reviewed"})

    @app.post("/api/issues/{issue_id}/evidence-review")
    async def review_issue_evidence_api(issue_id: int, request: Request, current_user: Optional[str] = Depends(get_current_user)):
        user = require_user(current_user)
        profile = professional_profile(user)
        if profile is None:
            return JSONResponse(status_code=403, content={"message": "Only verified professionals can review evidence."})
        try:
            data = await request.json()
            decision = str(data.get("decision", "")).strip()
            explanation = str(data.get("explanation", "")).strip()
        except (ValueError, TypeError, json.JSONDecodeError):
            return JSONResponse(status_code=400, content={"message": "Invalid evidence review data."})
        result, issue = review_issue_evidence(ISSUES, issue_id, profile.get("name", user), decision, explanation)
        if result == "invalid":
            return JSONResponse(status_code=400, content={"message": "Choose a valid evidence decision and provide an explanation."})
        if result == "missing":
            return JSONResponse(status_code=404, content={"message": "Issue not found."})
        return JSONResponse(content={"message": "Evidence review saved.", "result": result, "issue": issue})

else:
    app = None
