"""Automated test suite for Societal Innovation Collaboration Portal."""

from __future__ import annotations

import unittest
import secrets
from io import BytesIO
from pathlib import Path
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from login_users import authenticate, create_account, _hash_password
from community import distance_km, upvote_issue, ISSUES
from AI_model import IssueDeduplicator, classify_issue, sanitize_and_reencode_image, inspect_image_proof
from map import industry_match_score
from storage import create_session_record, get_session_user, delete_session_record, check_rate_limit, load_dashboard_metrics, create_support_offer, update_offer_commitment, insert_proposal, update_proposal, update_team_outcomes, load_teams, create_milestone, get_milestone_deliverable, create_project_review, load_project_reviews, create_professional_profile, load_professional_profiles, update_professional_approval, create_team, create_support_request, load_support_requests, create_university, create_industry_partner, load_universities, load_industry_partners, update_institution_approval


class TestAuthentication(unittest.TestCase):
    def test_password_hashing(self):
        hash1, salt1 = _hash_password("mysecretpassword")
        hash2, salt2 = _hash_password("mysecretpassword", salt=salt1)
        self.assertEqual(hash1, hash2)
        self.assertEqual(salt1, salt2)

    def test_invalid_email_create_account(self):
        success, msg = create_account("invalid-email", "password123")
        self.assertFalse(success)
        self.assertIn("valid email", msg.lower())

    def test_short_password(self):
        success, msg = create_account("testuser@example.com", "123")
        self.assertFalse(success)
        self.assertIn("at least 8 characters", msg.lower())


class TestDistanceAndDeduplication(unittest.TestCase):
    def test_distance_km(self):
        # Ranchi to Jamshedpur distance roughly ~100-130km
        dist = distance_km(23.3441, 85.3096, 22.8046, 86.2029)
        self.assertTrue(100 < dist < 140)

    def test_token_similarity_fallback(self):
        dedup = IssueDeduplicator()
        report = {"title": "Pothole on Main Road", "description": "Large hole near Morabadi", "category": "Roads", "lat": 23.3441, "lng": 85.3096}
        existing = [{"id": 1, "title": "Pothole on Main Road", "description": "Deep hole near service road", "category": "Roads", "lat": 23.3442, "lng": 85.3097}]
        match = dedup.find_match(report, existing)
        self.assertIsNotNone(match)
        self.assertIn(match.decision, {"duplicate", "possible_duplicate"})

    def test_ai_classification_and_priority(self):
        result = classify_issue("Dangerous pothole near school", "Road blocked for days and unsafe for children")
        self.assertEqual(result["predicted_category"], "Urban Infrastructure")
        self.assertGreaterEqual(result["priority_score"], 80)
        self.assertEqual(result["priority_label"], "Critical")
        self.assertTrue(result["matching_explanation"])

    def test_industry_match_uses_expertise_and_location(self):
        partner = {"district": "Ranchi", "domains": "Water Resources, Healthcare"}
        issue = {"district": "Ranchi", "category": "Water Resources", "title": "Broken water pipeline", "description": "Drinking water supply is blocked"}
        score, matches, same_district = industry_match_score(partner, issue)
        self.assertGreaterEqual(score, 45)
        self.assertTrue(matches)
        self.assertTrue(same_district)


class TestImageSanitization(unittest.TestCase):
    def test_sanitize_empty_bytes(self):
        bytes_out, mime = sanitize_and_reencode_image(b"")
        self.assertEqual(bytes_out, b"")
        self.assertEqual(mime, "image/jpeg")

    def test_inspect_image_no_exif(self):
        dummy_bytes = b"not-a-real-image"
        res = inspect_image_proof(dummy_bytes, 23.3441, 85.3096)
        self.assertEqual(res["status"], "unverified")


class TestSessionAndRateLimiting(unittest.TestCase):
    def test_rate_limit_helper(self):
        test_key = "test_client_ip_123"
        # Should allow first request
        allowed = check_rate_limit(test_key, max_requests=2, window_seconds=60)
        self.assertTrue(allowed)

    def test_session_lifecycle(self):
        test_email = "session_test@example.com"
        session_id = create_session_record(test_email)
        self.assertTrue(len(session_id) > 10)
        user = get_session_user(session_id)
        self.assertEqual(user, test_email)
        delete_session_record(session_id)
        user_after = get_session_user(session_id)
        self.assertIsNone(user_after)


class TestDashboardTemplates(unittest.TestCase):
    def test_templates_exist(self):
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        for name in ("citizen.html", "university.html", "university_login.html", "industry.html", "industry_login.html", "industry_register.html", "government.html"):
            tmpl = templates_dir / name
            self.assertTrue(tmpl.exists(), f"Template {name} missing")
            content = tmpl.read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", content.lower())
            self.assertIn('/templates/shared.css', content)

    def test_pwa_assets_exist_and_are_registered(self):
        root = Path(__file__).resolve().parent.parent
        manifest = (root / "manifest.json").read_text(encoding="utf-8")
        worker = (root / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn('"display": "standalone"', manifest)
        self.assertIn("self.addEventListener(\"fetch\"", worker)
        for name in ("citizen.html", "community.html", "government.html", "university.html", "industry.html"):
            content = (root / "templates" / name).read_text(encoding="utf-8")
            self.assertIn('rel="manifest"', content)
            self.assertIn("service-worker.js", content)

    def test_industry_auth_templates_have_flow_links(self):
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        login = (templates_dir / "industry_login.html").read_text(encoding="utf-8")
        register = (templates_dir / "industry_register.html").read_text(encoding="utf-8")
        self.assertIn('action="/industry/login"', login)
        self.assertIn('action="/industry/register"', register)
        self.assertIn('href="/industry/register"', login)
        self.assertIn('href="/industry/login"', register)


class TestUniversityAndIndustryDashboards(unittest.TestCase):
    def test_university_dashboard_render(self):
        from map import render_university_dashboard
        html_out = render_university_dashboard("innovation@bitmesra.ac.in")
        self.assertIn("Birla Institute of Technology, Mesra", html_out)
        self.assertIn("Assigned Challenges", html_out)
        self.assertIn("Student Project Teams", html_out)
        self.assertIn("Milestones &amp; Testing", html_out.replace("&", "&amp;"))

    def test_industry_dashboard_render(self):
        from map import render_industry_dashboard
        html_out = render_industry_dashboard("partner@jin.example")
        self.assertIn("Jharkhand Innovation Network", html_out)
        self.assertIn("Explore Challenges", html_out)
        self.assertIn("Submit Support Offer", html_out)
        self.assertIn("University Innovations &amp; Prototypes", html_out.replace("&", "&amp;"))

    def test_unregistered_account_render(self):
        from map import render_university_dashboard, render_industry_dashboard
        uni_out = render_university_dashboard("unregistered@example.com")
        self.assertIn("University Account Required", uni_out)
        ind_out = render_industry_dashboard("unregistered@example.com")
        self.assertIn("Industry Partner Account Required", ind_out)


class TestGovernmentAnalytics(unittest.TestCase):
    def test_dashboard_metrics_include_collaboration_outcomes(self):
        metrics = load_dashboard_metrics()
        self.assertIn("university_participation", metrics)
        self.assertIn("support_by_type", metrics)
        self.assertIn("project_outcomes", metrics)
        self.assertTrue(metrics["university_participation"])
        self.assertTrue(metrics["support_by_type"])

    def test_government_dashboard_renders_collaboration_charts(self):
        from map import render_government_dashboard
        html_out = render_government_dashboard()
        self.assertIn("University participation", html_out)
        self.assertIn("Industry support by type", html_out)
        self.assertIn("Project outcomes", html_out)


class TestCollaborationPersistence(unittest.TestCase):
    def test_industry_support_offer_lifecycle(self):
        offer = create_support_offer(1, 1, "Mentorship", "Weekly prototype mentoring", timeline="30 days")
        self.assertEqual(offer["status"], "Offered")
        self.assertTrue(update_offer_commitment(offer["id"], "Accepted", "Mentor confirmed"))

    def test_solution_proposal_persistence(self):
        proposal = insert_proposal({"issue_id": 1, "title": "Safer road sensing", "description": "Install low-cost sensors.", "author": "citizen@example.com"})
        self.assertEqual(proposal["status"], "Submitted")
        proposal["status"] = "Approved"
        update_proposal(proposal)
        self.assertEqual(proposal["status"], "Approved")

    def test_structured_impact_evidence_persistence(self):
        teams = load_teams()
        if not teams:
            self.skipTest("No project team is available in the configured database")
        self.assertTrue(update_team_outcomes(teams[0]["id"], "Patent filed", "Incubated", "Reduced response time", "Sakchi Ward", "2026-09-01", "2026-10-01", 120, "40% faster detection"))
        metrics = load_dashboard_metrics()
        outcome_totals = {item["outcome"]: item["total"] for item in metrics["project_outcomes"]}
        self.assertGreaterEqual(outcome_totals["Beneficiaries reached"], 120)
        self.assertGreaterEqual(outcome_totals["Measured outcomes"], 1)

    def test_milestone_deliverable_round_trip(self):
        teams = load_teams()
        if not teams:
            self.skipTest("No project team is available in the configured database")
        milestone = create_milestone(teams[0]["id"], "Evidence upload test", "2026-12-01", "Pilot report", "text/plain", b"pilot evidence")
        deliverable = get_milestone_deliverable(milestone["id"])
        self.assertEqual(deliverable, ("text/plain", b"pilot evidence"))

    def test_project_review_record_round_trip(self):
        teams = load_teams()
        if not teams:
            self.skipTest("No project team is available in the configured database")
        review = create_project_review(teams[0]["id"], "Pilot", "Needs changes", "Add two more field measurements.", "admin@jharkhand.gov.in")
        self.assertEqual(review["review_type"], "Pilot")
        self.assertEqual(load_project_reviews(teams[0]["id"])[0]["decision"], "Needs changes")

    def test_professional_approval_lifecycle(self):
        email = f"reviewer.{secrets.token_hex(6)}@example.gov"
        profile = create_professional_profile(email, "Review Officer", "Jharkhand Lab", "Public health reviewer", "Department verification")
        self.assertEqual(profile["approval_status"], "Pending")
        self.assertTrue(update_professional_approval(email, "Active"))
        approved = next(item for item in load_professional_profiles("Active") if item["email"] == email)
        self.assertEqual(approved["name"], "Review Officer")

    def test_team_member_roles_persist(self):
        members = [f"student.{secrets.token_hex(4)}@example.edu", f"faculty.{secrets.token_hex(4)}@example.edu"]
        team = create_team(1, 1, f"Role test {secrets.token_hex(4)}", "mentor@example.edu", members, {members[0]: "Student", members[1]: "Faculty co-mentor"})
        saved = next(item for item in load_teams() if item["id"] == team["id"])
        self.assertEqual(saved["member_roles"][members[0]], "Student")
        self.assertEqual(saved["member_roles"][members[1]], "Faculty co-mentor")

    def test_university_support_request_persists(self):
        request = create_support_request(1, 1, "innovation@bitmesra.ac.in", "Testing", "Validate the pilot sensors in the field.")
        self.assertEqual(request["status"], "Requested")
        saved = load_support_requests(1)
        self.assertTrue(any(item["id"] == request["id"] and item["support_type"] == "Testing" for item in saved))

    def test_university_and_industry_approval_lifecycle(self):
        university = create_university("Test Approval University", "Ranchi", "Healthcare", "Public Health", "Health Lab", "Innovation Hub", f"uni.{secrets.token_hex(4)}@example.edu", "Community health")
        partner = create_industry_partner("Test Approval Partner", "Startup", "Ranchi", "Healthcare", f"partner.{secrets.token_hex(4)}@example.com")
        self.assertEqual(university["approval_status"], "Pending")
        self.assertEqual(partner["approval_status"], "Pending")
        self.assertTrue(update_institution_approval("university", university["id"], "Active"))
        self.assertTrue(update_institution_approval("industry", partner["id"], "Rejected"))
        saved_university = next(item for item in load_universities() if item["id"] == university["id"])
        saved_partner = next(item for item in load_industry_partners() if item["id"] == partner["id"])
        self.assertEqual(saved_university["approval_status"], "Active")
        self.assertEqual(saved_partner["approval_status"], "Rejected")

    def test_solution_vote_is_one_per_user_and_changeable(self):
        from app_fastapi import record_proposal_vote
        proposals = [{"id": 101, "issue_id": 7, "votes": 0}, {"id": 102, "issue_id": 7, "votes": 0}]
        voters = {}
        self.assertEqual(record_proposal_vote(proposals, voters, 101, "citizen@example.com")[:2], ("voted", 1))
        self.assertEqual(record_proposal_vote(proposals, voters, 101, "citizen@example.com")[:2], ("already_voted", 1))
        self.assertEqual(record_proposal_vote(proposals, voters, 102, "citizen@example.com")[:2], ("changed", 1))
        self.assertEqual(proposals[0]["votes"], 0)
        self.assertEqual(proposals[1]["votes"], 1)


if __name__ == "__main__":
    unittest.main()
