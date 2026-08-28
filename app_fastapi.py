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
    CITIZEN_PAGE_FILE, UNIVERSITY_DASHBOARD_FILE, INDUSTRY_DASHBOARD_FILE, GOVERNMENT_DASHBOARD_FILE
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
        if not authenticate(email, password):
            return HTMLResponse(content=load_login_page('<p class="error">Email or password is incorrect.</p>'), status_code=401)
        session_id = create_session_record(email)
        response = RedirectResponse(url="/", status_code=303)
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

else:
    app = None
