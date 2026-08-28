"""Production FastAPI application entry point for Societal Innovation Collaboration Portal.

Run with: uvicorn app_fastapi:app --reload --port 8000
"""

from __future__ import annotations

import base64
import html
import json
from typing import Any, Optional

try:
    from fastapi import FastAPI, Request, HTTPException, status, Depends, Response
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
    from fastapi.staticfiles import StaticFiles
except ImportError:
    FastAPI = None

from login_users import authenticate, create_account, is_admin, professional_profile
from community import JHARKHAND_DISTRICTS, JHARKHAND_DOMAINS, ISSUES, add_issue, nearby_issues, render_page, upvote_issue
from storage import (
    assign_issue, check_rate_limit, create_account_record, create_industry_partner,
    create_message, create_milestone, create_notification, create_session_record,
    create_support_offer, create_team, create_university, delete_session_record,
    get_proof, get_proposal_visual, get_session_user, insert_proposal, load_all_partner_offers,
    load_assignments, load_dashboard_metrics, load_industry_partners, load_milestones,
    load_notifications, load_messages, load_partner_offers, load_proposals,
    load_status_history, load_teams, load_university_assignments, load_universities,
    load_user_issues, moderate_issue, update_assignment, update_milestone,
    update_offer_commitment, update_proposal, update_team_outcomes, update_team_status,
    update_university,
)
from AI_model import inspect_image_proof, sanitize_and_reencode_image
from map import (
    load_login_page, load_register_page, build_proposals_page, build_professionals_page,
    render_admin_issues, render_industry_admin, render_university_issues,
    render_university_dashboard, render_industry_dashboard, render_government_dashboard,
    notification_markup, render_messages, render_user_issues, MAP_PAGE, university_for_user, industry_for_user,
    CITIZEN_PAGE_FILE, UNIVERSITY_PAGE, UNIVERSITY_DASHBOARD_FILE, INDUSTRY_DASHBOARD_FILE, GOVERNMENT_DASHBOARD_FILE
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
        portal_role = str(form.get("portal_role", "citizen"))
        if not authenticate(email, password):
            return HTMLResponse(content=load_login_page('<p class="error">Email or password is incorrect.</p>'), status_code=401)
        session_id = create_session_record(email)
        destination = {
            "government": "/government-dashboard",
            "university": "/university-dashboard",
            "industry": "/industry-dashboard",
        }.get(portal_role, "/")
        response = RedirectResponse(url=destination, status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
        return response

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

    @app.get("/universities", response_class=HTMLResponse)
    async def universities(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user or not is_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin authorization required")
        return HTMLResponse(content=UNIVERSITY_PAGE.replace("__ISSUES__", render_university_issues()))

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
        return HTMLResponse(content=render_university_dashboard(current_user))

    @app.get("/industry-dashboard", response_class=HTMLResponse)
    async def industry_dashboard(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user or industry_for_user(current_user) is None:
            raise HTTPException(status_code=403, detail="Industry account required")
        return HTMLResponse(content=render_industry_dashboard(current_user))

    @app.get("/government-dashboard", response_class=HTMLResponse)
    async def government_dashboard(current_user: Optional[str] = Depends(get_current_user)):
        if not current_user or (not is_admin(current_user) and industry_for_user(current_user) is None):
            raise HTTPException(status_code=403, detail="Government or industry account required")
        template = GOVERNMENT_DASHBOARD_FILE.read_text(encoding="utf-8")
        return HTMLResponse(content=template.replace("__CONTENT__", render_government_dashboard()))

    @app.get("/proof/{proof_id}")
    async def get_proof_image(proof_id: str):
        proof = get_proof(proof_id)
        if not proof:
            raise HTTPException(status_code=404, detail="Proof not found")
        return Response(content=proof[1], media_type=proof[0])

    @app.get("/api/issues")
    async def list_issues_api():
        return JSONResponse(content=ISSUES)

    @app.post("/api/issues")
    async def create_issue_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        data = await request.json()
        data["lat"] = float(data["lat"])
        data["lng"] = float(data["lng"])
        data["district"] = str(data.get("district", "Ranchi")).strip() or "Ranchi"
        data["block"] = str(data.get("block", "")).strip()
        data["reporter"] = current_user
        encoded_proof = data.pop("proof_image", "")
        proof_type = data.pop("proof_type", "image/jpeg")
        proof_bytes = base64.b64decode(encoded_proof, validate=True) if encoded_proof else b""
        if proof_bytes:
            proof_bytes, proof_type = sanitize_and_reencode_image(proof_bytes, proof_type)
            proof = inspect_image_proof(proof_bytes, data["lat"], data["lng"])
            if proof["status"] == "mismatch":
                return JSONResponse(status_code=422, content=proof)
            data.update({"proof_status": proof["status"], "proof_message": proof["message"]})
            data["proof_id"] = "proof_" + str(len(ISSUES) + 1)
            data["_proof_type"] = proof_type
            data["_proof_data"] = proof_bytes
        created = add_issue(data)
        return JSONResponse(status_code=201 if created["result"] == "new" else 200, content=created)

    @app.post("/api/issues/{issue_id}/upvote")
    async def upvote_issue_api(issue_id: int, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        result = upvote_issue(issue_id, current_user)
        status_code = 409 if result.get("error") == "already_voted" else (404 if result.get("error") == "not_found" else 200)
        return JSONResponse(status_code=status_code, content=result)

    @app.post("/api/university/assignment-response")
    async def university_assignment_response(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user or university_for_user(current_user) is None:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        issue_id = int(data["issue_id"])
        status = str(data["status"])
        reason = str(data.get("reason", "")).strip()
        assignments = load_university_assignments(current_user)
        if issue_id not in {a["issue_id"] for a in assignments}:
            raise HTTPException(status_code=403, detail="Challenge not assigned to this university")
        if status not in {"Accepted", "Rejected", "Needs clarification"} or not reason:
            return JSONResponse(status_code=400, content={"message": "Choose a valid response and provide a reason."})
        update_assignment(issue_id, status, reason)
        return JSONResponse(content={"issue_id": issue_id, "status": status, "message": "Decision saved successfully."})

    @app.post("/api/university/teams")
    async def university_create_team(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        university = university_for_user(current_user or "")
        if not current_user or university is None:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        issue_id = int(data["issue_id"])
        university_id = int(data["university_id"])
        name = str(data["name"]).strip()[:150]
        mentor = str(data["faculty_mentor"]).strip()[:255]
        members = [str(m).strip()[:255] for m in data.get("members", []) if str(m).strip()]
        if university_id != university["id"] or issue_id not in {a["issue_id"] for a in load_university_assignments(current_user)}:
            raise HTTPException(status_code=403, detail="Unauthorized")
        if not name or not mentor or not members:
            return JSONResponse(status_code=400, content={"message": "Team name, faculty mentor, and students are required."})
        team = create_team(issue_id, university_id, name, mentor, members)
        return JSONResponse(status_code=201, content={"message": "Project team created successfully.", "team": team})

    @app.post("/api/university/team-status")
    async def university_team_status(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        university = university_for_user(current_user or "")
        if not current_user or university is None:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        team_id = int(data["team_id"])
        status = str(data.get("status", ""))
        note = str(data.get("note", "")).strip()[:1000]
        if status not in {"Team Formed", "Prototype", "Pilot", "Deployed", "Impact Measured"}:
            return JSONResponse(status_code=400, content={"message": "Invalid project stage."})
        team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
        if team is None:
            raise HTTPException(status_code=403, detail="Team not found or not owned by university")
        update_team_status(team_id, status, current_user, note)
        return JSONResponse(content={"team_id": team_id, "status": status, "message": "Project stage updated."})

    @app.post("/api/university/milestones")
    async def university_create_milestone(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        university = university_for_user(current_user or "")
        if not current_user or university is None:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        team_id = int(data["team_id"])
        title = str(data.get("title", "")).strip()[:200]
        due_date = str(data.get("due_date", "")).strip()
        deliverable = str(data.get("deliverable", "")).strip()[:1000]
        if not title:
            return JSONResponse(status_code=400, content={"message": "Milestone title is required."})
        team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
        if team is None:
            raise HTTPException(status_code=403, detail="Team not found")
        milestone = create_milestone(team_id, title, due_date, deliverable)
        return JSONResponse(status_code=201, content={"message": "Milestone added.", "milestone": milestone})

    @app.post("/api/university/milestone-status")
    async def university_milestone_status(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        university = university_for_user(current_user or "")
        if not current_user or university is None:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        milestone_id = int(data["milestone_id"])
        status = str(data.get("status", ""))
        testing_result = str(data.get("testing_result", "")).strip()[:2000]
        if status not in {"Pending", "In Progress", "Completed"}:
            return JSONResponse(status_code=400, content={"message": "Invalid milestone status."})
        update_milestone(milestone_id, status, testing_result)
        return JSONResponse(content={"milestone_id": milestone_id, "status": status, "message": "Milestone updated."})

    @app.post("/api/university/team-outcomes")
    async def university_team_outcomes(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        university = university_for_user(current_user or "")
        if not current_user or university is None:
            raise HTTPException(status_code=403, detail="University account required")
        data = await request.json()
        team_id = int(data["team_id"])
        ip_outcome = str(data.get("ip_outcome", "")).strip()[:2000]
        startup_outcome = str(data.get("startup_outcome", "")).strip()[:2000]
        impact_summary = str(data.get("impact_summary", "")).strip()[:3000]
        team = next((item for item in load_teams() if item["id"] == team_id and item["university_id"] == university["id"]), None)
        if team is None:
            raise HTTPException(status_code=403, detail="Team not found")
        update_team_outcomes(team_id, ip_outcome, startup_outcome, impact_summary)
        return JSONResponse(content={"team_id": team_id, "status": "saved", "message": "Outcomes saved."})

    @app.post("/api/industry/offers")
    async def industry_offers_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        partner = industry_for_user(current_user or "")
        if not current_user or partner is None:
            raise HTTPException(status_code=403, detail="Industry account required")
        data = await request.json()
        issue_id = int(data["issue_id"])
        support_type = str(data.get("support_type", "")).strip()
        details = str(data.get("details", "")).strip()[:3000]
        if support_type not in {"Mentorship", "Funding", "Prototyping", "Testing", "Deployment"} or not details:
            return JSONResponse(status_code=400, content={"message": "Choose a support type and provide details."})
        offer = create_support_offer(issue_id, partner["id"], support_type, details)
        issue = next((item for item in ISSUES if item.get("id") == issue_id), None)
        if issue and issue.get("reporter"):
            create_notification(issue["reporter"], f"An industry partner offered {support_type.lower()} support for your issue.", "offer", offer["id"])
        return JSONResponse(status_code=201, content={"message": "Support offer submitted successfully.", "offer": offer})

    @app.post("/api/messages")
    async def send_message_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        data = await request.json()
        recipient = str(data.get("recipient", "")).strip().lower()
        message = str(data.get("message", "")).strip()[:3000]
        related_id = int(data["related_id"]) if data.get("related_id") else None
        if not recipient or not message:
            return JSONResponse(status_code=400, content={"message": "Recipient and message are required."})
        sent = create_message(current_user, recipient, message, "project" if related_id else "", related_id)
        create_notification(recipient, f"New project message from {current_user}.", "message", sent["id"])
        return JSONResponse(status_code=201, content={"message": "Message sent.", "message_id": sent["id"]})

    @app.post("/api/proposals")
    async def create_proposal_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        data = await request.json()
        issue_id = int(data["issue_id"])
        title = str(data.get("title", "")).strip()[:120]
        description = str(data.get("description", "")).strip()
        if not title or not description:
            return JSONResponse(status_code=400, content={"message": "Title and description are required."})
        proposal = insert_proposal({"issue_id": issue_id, "title": title, "description": description, "author": current_user})
        return JSONResponse(status_code=201, content={"message": "Solution proposal submitted.", "proposal": proposal})

    @app.post("/api/admin/universities")
    async def update_university_api(request: Request, current_user: Optional[str] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        data = await request.json()
        university_id = int(data["university_id"])
        name = str(data["name"]).strip()[:255]
        district = str(data["district"]).strip()[:100]
        domains = str(data["domains"]).strip()[:1000]
        departments = str(data.get("departments", "")).strip()[:1000]
        laboratories = str(data.get("laboratories", "")).strip()[:1000]
        incubation_facilities = str(data.get("incubation_facilities", "")).strip()[:1000]
        contact_email = str(data.get("contact_email", "")).strip()[:255]
        update_university(university_id, name, district, domains, departments, laboratories, incubation_facilities, contact_email)
        return JSONResponse(content={"message": "University profile updated.", "university_id": university_id})

else:
    app = None
