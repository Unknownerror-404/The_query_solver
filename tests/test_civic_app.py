"""Automated test suite for Societal Innovation Collaboration Portal."""

from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from login_users import authenticate, create_account, _hash_password
from community import distance_km, upvote_issue, ISSUES
from AI_model import IssueDeduplicator, classify_issue, sanitize_and_reencode_image, inspect_image_proof
from map import industry_match_score
from storage import create_session_record, get_session_user, delete_session_record, check_rate_limit


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

    def test_industry_auth_templates_have_flow_links(self):
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        login = (templates_dir / "industry_login.html").read_text(encoding="utf-8")
        register = (templates_dir / "industry_register.html").read_text(encoding="utf-8")
        self.assertIn('action="/industry/login"', login)
        self.assertIn('action="/industry/register"', register)
        self.assertIn('href="/industry/register"', login)
        self.assertIn('href="/industry/login"', register)


if __name__ == "__main__":
    unittest.main()
