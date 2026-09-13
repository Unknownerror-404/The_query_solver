import unittest
class TestAutoBan(unittest.TestCase):
    def test_auto_ban_recurring_issues(self):
        from storage import create_contractor, assign_issue_to_contractor, update_contractor_assignment, load_contractors
        from community import ISSUES, add_issue

        # 1. Create a dummy contractor and activate it
        import uuid
        uid = uuid.uuid4().hex[:8]
        c = create_contractor(
            "AutoBan Builders",
            "Owner X",
            f"LIC-{uid}",
            "Ranchi",
            "Roads",
            f"autoban_{uid}@test.com",
            "1234",
        )
        cid = c["id"]

        from storage import update_contractor_status
        update_contractor_status(cid, "Active", "Approved by admin")

        # 2. Add an original issue and assign to contractor, then complete it
        orig_issue = {
            "title": "Build a road",
            "category": "Roads",
            "lat": 23.0,
            "lng": 85.0,
        }
        orig = add_issue(orig_issue)
        assign_issue_to_contractor(orig["issue"]["id"], cid, "admin")

        from storage import load_contractor_assignments
        assignments = load_contractor_assignments(cid)
        update_contractor_assignment(assignments[0]["id"], "Completed", "Done")

        # 3. Simulate 3 new recurring issues at the exact same location
        for i in range(3):
            new_issue = {
                "title": f"Pothole {i}",
                "category": "Roads",
                "lat": 23.0,
                "lng": 85.0,
            }
            add_issue(new_issue)

        # 4. Automatic blocking is disabled; contractor administration decides.
        contractors = load_contractors()
        c_updated = next(c for c in contractors if c["id"] == cid)
        self.assertEqual(c_updated["approval_status"], "Active")


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
        self.assertIn(
            "University Innovations &amp; Prototypes",
            html_out.replace("&", "&amp;"),
        )

    def test_unregistered_account_render(self):
        from map import render_university_dashboard, render_industry_dashboard

        uni_out = render_university_dashboard("unregistered@example.com")
        self.assertIn("University Account Required", uni_out)

        ind_out = render_industry_dashboard("unregistered@example.com")
        self.assertIn("Industry Partner Account Required", ind_out)