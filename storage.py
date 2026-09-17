"""MySQL persistence for the civic-map application."""

from __future__ import annotations

import os
import json
import secrets
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error, IntegrityError


load_dotenv(Path(__file__).resolve().with_name(".env"))

logger = logging.getLogger(__name__)


MYSQL_CONFIG = {
    "host": os.getenv("CIVIC_MAP_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("CIVIC_MAP_DB_PORT", "3306")),
    "user": os.getenv("CIVIC_MAP_DB_USER", "root"),
    "password": os.getenv("CIVIC_MAP_DB_PASSWORD", "Mi123456#"),
    "database": os.getenv("CIVIC_MAP_DB_NAME", "sih26"),
    "connection_timeout": int(os.getenv("CIVIC_MAP_DB_TIMEOUT", "2")),
}


_DB_AVAILABLE: bool = False

_MEM_ISSUES: list[dict[str, Any]] = [
    {"id": 1, "title": "Pothole on Main Road", "category": "Roads", "area": "Morabadi, Ranchi", "district": "Ranchi", "block": "Morabadi", "lat": 23.3441, "lng": 85.3096, "supporters": 28, "age": "5h ago", "description": "A deep pothole is slowing traffic near the service road.", "moderation_status": "Approved"},
    {"id": 2, "title": "Garbage uncollected for four days", "category": "Waste", "area": "Bank More, Dhanbad", "district": "Dhanbad", "block": "Bank More", "lat": 23.7957, "lng": 86.4304, "supporters": 18, "age": "4d ago", "description": "Household waste has accumulated beside the community park.", "moderation_status": "Approved"},
    {"id": 3, "title": "Water cut, no notice", "category": "Water", "area": "Sakchi, Jamshedpur", "district": "East Singhbhum", "block": "Sakchi", "lat": 22.8046, "lng": 86.2029, "supporters": 42, "age": "36h ago", "description": "The neighbourhood has had no supply since yesterday morning.", "moderation_status": "Approved"},
    {"id": 4, "title": "Streetlight outage at junction", "category": "Streetlights", "area": "Tower Chowk, Deoghar", "district": "Deoghar", "block": "Tower Chowk", "lat": 24.4857, "lng": 86.6947, "supporters": 12, "age": "2d ago", "description": "Three streetlights are out, making the junction difficult to cross at night.", "moderation_status": "Approved"},
]

_MEM_UNIVERSITIES: list[dict[str, Any]] = [
    {"id": 1, "name": "Birla Institute of Technology, Mesra", "district": "Ranchi", "domains": "Engineering, Energy, Water Resources", "departments": "Civil Engineering, Electrical & Electronics, Environmental Sciences", "laboratories": "Advanced Water Lab, IoT Center, Power Systems Lab", "incubation_facilities": "STEP Technology Incubation Hub", "contact_email": "innovation@bitmesra.ac.in"},
    {"id": 2, "name": "National Institute of Technology, Jamshedpur", "district": "East Singhbhum", "domains": "Engineering, Urban Infrastructure, Energy", "departments": "Mechanical, Civil, Computer Science", "laboratories": "Materials Testing, Smart City Lab", "incubation_facilities": "NIT Innovation & Incubation Center", "contact_email": "innovation@nitjsr.ac.in"},
    {"id": 3, "name": "Central University of Jharkhand", "district": "Ranchi", "domains": "Education, Healthcare, Rural Livelihoods", "departments": "Rural Development, Public Health, Biotechnology", "laboratories": "Bio-resource Lab, Soil & Water Testing", "incubation_facilities": "Centre for Tribal & Rural Innovation", "contact_email": "innovation@cuj.ac.in"},
]

_MEM_INDUSTRY: list[dict[str, Any]] = [
    {"id": 1, "name": "Jharkhand Innovation Network", "partner_type": "Startup", "district": "Ranchi", "domains": "Education, Agriculture, Energy", "contact_email": "partner@jin.example"},
    {"id": 2, "name": "Adivasi Livelihoods Foundation", "partner_type": "CSR Organization", "district": "Khunti", "domains": "Rural Livelihoods, Healthcare, Water Resources", "contact_email": "connect@alf.example"},
    {"id": 3, "name": "Eastern Tech Manufacturing", "partner_type": "MSME", "district": "East Singhbhum", "domains": "Engineering, Urban Infrastructure, Sanitation", "contact_email": "innovation@etm.example"},
]

_MEM_ASSIGNMENTS: dict[int, dict[str, Any]] = {
    3: {"issue_id": 3, "university_id": 1, "status": "Accepted", "response_reason": "Accepted by Dept of Civil Engineering for IoT-based smart pressure monitoring.", "assigned_by": "admin@jharkhand.gov.in"},
    1: {"issue_id": 1, "university_id": 1, "status": "Accepted", "response_reason": "Accepted for smart road sensing study.", "assigned_by": "admin@jharkhand.gov.in"},
}

_MEM_TEAMS: list[dict[str, Any]] = [
    {"id": 1, "issue_id": 3, "university_id": 1, "name": "Team Jal-Drishti", "faculty_mentor": "mentor@bitmesra.ac.in", "status": "Prototype", "members": ["student1@bitmesra.ac.in", "student2@bitmesra.ac.in"], "ip_outcome": "Provisional Patent Application #2026/JH/0042", "startup_outcome": "Incubated at BIT STEP", "impact_summary": "Estimated 40% reduction in water leakage detection time across 12 wards.", "university_name": "Birla Institute of Technology, Mesra", "university_district": "Ranchi", "issue_title": "Water cut, no notice", "issue_category": "Water", "issue_district": "East Singhbhum", "issue_block": "Sakchi"},
]

_MEM_MILESTONES: list[dict[str, Any]] = [
    {"id": 1, "team_id": 1, "title": "Sensor Calibration & PCB Design", "due_date": "2026-09-15", "status": "Completed", "deliverable": "PCB v1.0 & Calibration Curves", "testing_result": "Accuracy within +/-1.5% under varying pressure flows."},
    {"id": 2, "team_id": 1, "title": "Pilot Field Installation in Sakchi Ward", "due_date": "2026-10-30", "status": "In Progress", "deliverable": "5 IoT sensor nodes deployed", "testing_result": "Telemetry streaming live via LoRaWAN."},
]

_MEM_OFFERS: list[dict[str, Any]] = [
    {"id": 1, "issue_id": 3, "partner_id": 1, "support_type": "Funding", "details": "Rs. 2.5 Lakh seed grant + LoRaWAN gateway hardware access for Ranchi pilot testing.", "status": "Accepted", "commitment_note": "Seed grant disbursed; gateways deployed.", "title": "Water cut, no notice", "district": "East Singhbhum", "block": "Sakchi", "category": "Water", "partner_name": "Jharkhand Innovation Network", "partner_type": "Startup", "partner_email": "partner@jin.example"},
    {"id": 2, "issue_id": 1, "partner_id": 3, "support_type": "Prototyping", "details": "Fabrication lab access at Jamshedpur facility for weather-resistant enclosures.", "status": "Offered", "commitment_note": "", "title": "Pothole on Main Road", "district": "Ranchi", "block": "Morabadi", "category": "Roads", "partner_name": "Eastern Tech Manufacturing", "partner_type": "MSME", "partner_email": "innovation@etm.example"},
]

_MEM_ACCOUNTS: dict[str, dict[str, str]] = {}
_MEM_SESSIONS: dict[str, str] = {}
_MEM_MESSAGES: list[dict[str, Any]] = []
_MEM_NOTIFICATIONS: list[dict[str, Any]] = []
_MEM_STATUS_HISTORY: list[dict[str, Any]] = []
_MEM_UNIVERSITY_REPORTS: list[dict[str, Any]] = []
_MEM_PROJECT_REVIEWS: list[dict[str, Any]] = []
_MEM_PROFESSIONALS: list[dict[str, Any]] = [{"email": "engineer@example.gov", "name": "Arun Mehta", "organization": "Bengaluru Urban Transport Authority", "affiliation": "Government transport professional", "verification": "Verified by organization", "approval_status": "Active"}]
_MEM_SUPPORT_REQUESTS: list[dict[str, Any]] = []
_MEM_PROPOSALS: list[dict[str, Any]] = []
_MEM_RATE_LIMITS: dict[str, Any] = {}
_MEM_CONTRACTORS: list[dict[str, Any]] = []
_MEM_CONTRACTOR_ASSIGNMENTS: list[dict[str, Any]] = []
_MEM_CONTRACTOR_COMPLAINTS: list[dict[str, Any]] = []
_MEMORY_ISSUES_FILE = Path(__file__).with_name("memory_issues.json")


def _load_memory_issues() -> None:
    if not _MEMORY_ISSUES_FILE.exists():
        return
    try:
        saved_issues = json.loads(_MEMORY_ISSUES_FILE.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return
    if not isinstance(saved_issues, list):
        return
    known_ids = {item.get("id") for item in _MEM_ISSUES}
    for saved_issue in saved_issues:
        if not isinstance(saved_issue, dict) or saved_issue.get("id") in known_ids:
            continue
        _MEM_ISSUES.append(saved_issue)


def _save_memory_issues() -> None:
    try:
        _MEMORY_ISSUES_FILE.write_text(json.dumps(_MEM_ISSUES, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _migrate_memory_records(cursor: Any) -> None:
    for issue in _MEM_ISSUES:
        cursor.execute(
            """
            INSERT IGNORE INTO issues
            (id, title, category, description, area, district, block, latitude, longitude,
             supporters, age, moderation_status, reporter)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                issue["id"], issue.get("title", "Untitled issue"), issue.get("category", "Other"),
                issue.get("description", ""), issue.get("area", ""), issue.get("district", "Ranchi"),
                issue.get("block", ""), issue.get("lat", 0), issue.get("lng", 0),
                issue.get("supporters", 0), issue.get("age", "just now"),
                issue.get("moderation_status", "Pending"), issue.get("reporter"),
            ),
        )

    for university in _MEM_UNIVERSITIES:
        cursor.execute(
            """
            INSERT INTO universities
            (id, name, district, domains, expertise, departments, laboratories,
             incubation_facilities, contact_email, approval_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            name = VALUES(name), district = VALUES(district), domains = VALUES(domains),
            expertise = VALUES(expertise), departments = VALUES(departments),
            laboratories = VALUES(laboratories), incubation_facilities = VALUES(incubation_facilities),
            approval_status = VALUES(approval_status)
            """,
            (
                university["id"], university["name"], university.get("district", "Ranchi"),
                university.get("domains", ""), university.get("expertise", ""),
                university.get("departments", ""), university.get("laboratories", ""),
                university.get("incubation_facilities", ""), university.get("contact_email", ""),
                university.get("approval_status", "Active"),
            ),
        )

    for profile in _MEM_PROFESSIONALS:
        cursor.execute(
            """
            INSERT INTO professional_profiles
            (email, name, organization, affiliation, verification, approval_status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE name = VALUES(name), organization = VALUES(organization),
            affiliation = VALUES(affiliation), verification = VALUES(verification),
            approval_status = VALUES(approval_status)
            """,
            (
                profile["email"], profile.get("name", ""), profile.get("organization", ""),
                profile.get("affiliation", ""), profile.get("verification", ""),
                profile.get("approval_status", "Active"),
            ),
        )

    for assignment in _MEM_ASSIGNMENTS.values():
        cursor.execute(
            """
            INSERT INTO issue_assignments
            (issue_id, university_id, status, response_reason, assigned_by)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE university_id = VALUES(university_id),
            status = VALUES(status), response_reason = VALUES(response_reason),
            assigned_by = VALUES(assigned_by)
            """,
            (
                assignment["issue_id"], assignment["university_id"], assignment.get("status", "Assigned"),
                assignment.get("response_reason", ""), assignment.get("assigned_by", "system"),
            ),
        )

    for team in _MEM_TEAMS:
        cursor.execute(
            """
            INSERT IGNORE INTO project_teams
            (id, issue_id, university_id, name, faculty_mentor, status, ip_outcome,
             startup_outcome, impact_summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                team["id"], team["issue_id"], team["university_id"], team["name"],
                team.get("faculty_mentor", ""), team.get("status", "Forming"),
                team.get("ip_outcome"), team.get("startup_outcome"), team.get("impact_summary"),
            ),
        )
        cursor.executemany(
            "INSERT IGNORE INTO team_members (team_id, student_email, member_role) VALUES (%s, %s, %s)",
            [(team["id"], member, "Student") for member in team.get("members", [])],
        )

    for milestone in _MEM_MILESTONES:
        cursor.execute(
            """
            INSERT IGNORE INTO milestones
            (id, team_id, title, due_date, status, deliverable, testing_result)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                milestone["id"], milestone["team_id"], milestone["title"], milestone.get("due_date"),
                milestone.get("status", "Pending"), milestone.get("deliverable", ""),
                milestone.get("testing_result", ""),
            ),
        )

    for offer in _MEM_OFFERS:
        cursor.execute(
            """
            INSERT IGNORE INTO support_offers
            (id, issue_id, partner_id, support_type, details, status, commitment_note)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                offer["id"], offer["issue_id"], offer["partner_id"], offer["support_type"],
                offer.get("details", ""), offer.get("status", "Offered"), offer.get("commitment_note", ""),
            ),
        )


_load_memory_issues()


def connect():
    return mysql.connector.connect(**MYSQL_CONFIG)


def ensure_database() -> None:
    server_config = {key: value for key, value in MYSQL_CONFIG.items() if key != "database"}
    connection = mysql.connector.connect(**server_config)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS `{}`".format(MYSQL_CONFIG["database"].replace("`", "``"))
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def initialise(default_issues: Iterable[dict[str, Any]] = ()) -> None:
    global _DB_AVAILABLE
    try:
        ensure_database()
        connection = connect()
    except Exception as exc:
        logger.error("MySQL initialisation failed; database fallback is active. Check CIVIC_MAP_DB_* values. Error: %s", exc)
        _DB_AVAILABLE = False
        return
    _DB_AVAILABLE = True
    try:
        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
        id INT PRIMARY KEY AUTO_INCREMENT,

        -- User-submitted issue information
        title VARCHAR(255) NOT NULL,
        category VARCHAR(100) NOT NULL,
        description TEXT NOT NULL,

        -- Location information
        area VARCHAR(255) NOT NULL,
        district VARCHAR(100) NOT NULL DEFAULT 'Ranchi',
        block VARCHAR(100) NOT NULL DEFAULT '',
        latitude DECIMAL(10, 7) NOT NULL,
        longitude DECIMAL(10, 7) NOT NULL,

        -- Sentence Transformer / AI classification
        ai_category VARCHAR(100),
        category_confidence DECIMAL(5, 4),
        category_mismatch BOOLEAN NOT NULL DEFAULT FALSE,

        -- Semantic tags produced by the tagging system
        ai_tags JSON,

        -- Model used to generate the AI results
        tagging_model VARCHAR(150),

        -- Issue metadata
        supporters INT NOT NULL DEFAULT 0,
        age VARCHAR(50) NOT NULL,

        -- Proof/evidence
        proof_id VARCHAR(100),
        proof_type VARCHAR(30),
        proof_data LONGBLOB,
        proof_status VARCHAR(30),
        proof_message TEXT,

        -- Video evidence / processing
        video_id VARCHAR(100),
        video_type VARCHAR(40),
        video_data LONGBLOB,
        video_predicted_category VARCHAR(100),
        video_confidence DECIMAL(4, 2),
        video_explanation TEXT,

        -- Moderation
        moderation_status VARCHAR(30) NOT NULL DEFAULT 'Pending',
        moderation_reason TEXT,
        moderated_by VARCHAR(255),

        -- Reporter
        reporter VARCHAR(255),

        -- Timestamp
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
        

        for statement in (
            "ALTER TABLE issues ADD COLUMN district VARCHAR(100) NOT NULL DEFAULT 'Ranchi'",
            "ALTER TABLE issues ADD COLUMN block VARCHAR(100) NOT NULL DEFAULT ''",
            "ALTER TABLE issues ADD COLUMN proof_type VARCHAR(30)",
            "ALTER TABLE issues ADD COLUMN proof_data LONGBLOB",
            "ALTER TABLE issues ADD COLUMN predicted_category VARCHAR(100)",
            "ALTER TABLE issues ADD COLUMN category_confidence DECIMAL(4, 2)",
            "ALTER TABLE issues ADD COLUMN priority_score INT",
            "ALTER TABLE issues ADD COLUMN priority_label VARCHAR(30)",
            "ALTER TABLE issues ADD COLUMN matching_explanation TEXT",
            "ALTER TABLE issues ADD COLUMN moderation_status VARCHAR(30) NOT NULL DEFAULT 'Pending'",
            "ALTER TABLE issues ADD COLUMN moderation_reason TEXT",
            "ALTER TABLE issues ADD COLUMN moderated_by VARCHAR(255)",
            "ALTER TABLE issues ADD COLUMN reporter VARCHAR(255)",

            "ALTER TABLE issues ADD COLUMN ai_category VARCHAR(100)",
            "ALTER TABLE issues ADD COLUMN ai_confidence DECIMAL(6,5)",
            "ALTER TABLE issues ADD COLUMN category_mismatch BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE issues ADD COLUMN ai_tags JSON",
            "ALTER TABLE issues ADD COLUMN tagging_model VARCHAR(150)",
            "ALTER TABLE issues ADD COLUMN video_id VARCHAR(100)",
            "ALTER TABLE issues ADD COLUMN video_type VARCHAR(40)",
            "ALTER TABLE issues ADD COLUMN video_data LONGBLOB",
            "ALTER TABLE issues ADD COLUMN video_predicted_category VARCHAR(100)",
            "ALTER TABLE issues ADD COLUMN video_confidence DECIMAL(4, 2)",
            "ALTER TABLE issues ADD COLUMN video_explanation TEXT",
        ):
            try:
                cursor.execute(statement)
            except Error as error:
                if error.errno != 1060:
                    raise
        cursor.execute("SELECT COUNT(*) FROM issues")
        if cursor.fetchone()[0] == 0:
            for issue in default_issues:
                cursor.execute(
                    """
                    INSERT INTO issues
                    (id, title, category, area, latitude, longitude, description, supporters, age)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (issue["id"], issue["title"], issue["category"], issue["area"], issue["lat"], issue["lng"], issue.get("description", ""), issue.get("supporters", 0), issue.get("age", "just now")),
                )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_supporters (
                issue_id INT NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                PRIMARY KEY (issue_id, user_email),
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                email VARCHAR(255) PRIMARY KEY,
                password_hash CHAR(64) NOT NULL,
                salt CHAR(32) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS proposals (
                id INT PRIMARY KEY AUTO_INCREMENT,
                issue_id INT NOT NULL,
                title VARCHAR(120) NOT NULL,
                description TEXT NOT NULL,
                author VARCHAR(255) NOT NULL,
                votes INT NOT NULL DEFAULT 0,
                status VARCHAR(40) NOT NULL DEFAULT 'Submitted',
                visual_type VARCHAR(30),
                visual_data LONGBLOB,
                review_decision VARCHAR(40),
                review_explanation TEXT,
                reviewer VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS proposal_votes (
                issue_id INT NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                proposal_id INT NOT NULL,
                PRIMARY KEY (issue_id, user_email),
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (proposal_id) REFERENCES proposals(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS universities (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                district VARCHAR(100) NOT NULL,
                domains TEXT NOT NULL,
                expertise TEXT,
                departments TEXT,
                laboratories TEXT,
                incubation_facilities TEXT,
                contact_email VARCHAR(255),
                approval_status VARCHAR(30) NOT NULL DEFAULT 'Active',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            cursor.execute("ALTER TABLE universities ADD COLUMN approval_status VARCHAR(30) NOT NULL DEFAULT 'Active'")
        except Error as error:
            if error.errno != 1060:
                raise
        for statement in (
            "ALTER TABLE universities ADD COLUMN expertise TEXT",
            "ALTER TABLE universities ADD COLUMN departments TEXT",
            "ALTER TABLE universities ADD COLUMN laboratories TEXT",
            "ALTER TABLE universities ADD COLUMN incubation_facilities TEXT",
        ):
            try:
                cursor.execute(statement)
            except Error as error:
                if error.errno != 1060:
                    raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_assignments (
                issue_id INT PRIMARY KEY,
                university_id INT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Assigned',
                response_reason TEXT,
                assigned_by VARCHAR(255) NOT NULL,
                assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (university_id) REFERENCES universities(id) ON DELETE CASCADE
            )
            """
        )
        try:
            cursor.execute("ALTER TABLE issue_assignments ADD COLUMN response_reason TEXT")
        except Error as error:
            if error.errno != 1060:
                raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS project_teams (
                id INT PRIMARY KEY AUTO_INCREMENT,
                issue_id INT NOT NULL,
                university_id INT NOT NULL,
                name VARCHAR(150) NOT NULL,
                faculty_mentor VARCHAR(255) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Forming',
                ip_outcome TEXT,
                startup_outcome TEXT,
                impact_summary TEXT,
                pilot_location VARCHAR(255),
                pilot_start_date DATE,
                pilot_end_date DATE,
                beneficiary_count INT NOT NULL DEFAULT 0,
                outcome_metric TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (university_id) REFERENCES universities(id) ON DELETE CASCADE
            )
            """
        )
        for statement in (
            "ALTER TABLE project_teams ADD COLUMN ip_outcome TEXT",
            "ALTER TABLE project_teams ADD COLUMN startup_outcome TEXT",
            "ALTER TABLE project_teams ADD COLUMN impact_summary TEXT",
            "ALTER TABLE project_teams ADD COLUMN pilot_location VARCHAR(255)",
            "ALTER TABLE project_teams ADD COLUMN pilot_start_date DATE",
            "ALTER TABLE project_teams ADD COLUMN pilot_end_date DATE",
            "ALTER TABLE project_teams ADD COLUMN beneficiary_count INT NOT NULL DEFAULT 0",
            "ALTER TABLE project_teams ADD COLUMN outcome_metric TEXT",
        ):
            try:
                cursor.execute(statement)
            except Error as error:
                if error.errno != 1060:
                    raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS team_members (
                team_id INT NOT NULL,
                student_email VARCHAR(255) NOT NULL,
                member_role VARCHAR(30) NOT NULL DEFAULT 'Student',
                PRIMARY KEY (team_id, student_email),
                FOREIGN KEY (team_id) REFERENCES project_teams(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS project_status_history (
                id INT PRIMARY KEY AUTO_INCREMENT,
                team_id INT NOT NULL,
                status VARCHAR(30) NOT NULL,
                changed_by VARCHAR(255) NOT NULL,
                note TEXT,
                changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES project_teams(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS milestones (
                id INT PRIMARY KEY AUTO_INCREMENT,
                team_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                due_date DATE,
                status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                deliverable TEXT,
                testing_result TEXT,
                completed_at DATE,
                deliverable_type VARCHAR(100),
                deliverable_data LONGBLOB,
                FOREIGN KEY (team_id) REFERENCES project_teams(id) ON DELETE CASCADE
            )
            """
        )
        for statement in (
            "ALTER TABLE milestones ADD COLUMN testing_result TEXT",
            "ALTER TABLE milestones ADD COLUMN completed_at DATE",
            "ALTER TABLE milestones ADD COLUMN deliverable_type VARCHAR(100)",
            "ALTER TABLE milestones ADD COLUMN deliverable_data LONGBLOB",
        ):
            try:
                cursor.execute(statement)
            except Error as error:
                if error.errno != 1060:
                    raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS university_reports (
                id INT PRIMARY KEY AUTO_INCREMENT,
                issue_id INT NOT NULL,
                university_id INT NOT NULL,
                submitted_by VARCHAR(255) NOT NULL,
                title VARCHAR(255) NOT NULL,
                summary TEXT NOT NULL,
                deliverables TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (university_id) REFERENCES universities(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS project_reviews (
                id INT PRIMARY KEY AUTO_INCREMENT,
                team_id INT NOT NULL,
                review_type VARCHAR(30) NOT NULL,
                decision VARCHAR(30) NOT NULL,
                notes TEXT NOT NULL,
                reviewed_by VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES project_teams(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS professional_profiles (
                email VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                organization VARCHAR(255) NOT NULL,
                affiliation VARCHAR(255) NOT NULL,
                verification VARCHAR(255) NOT NULL,
                approval_status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("SELECT COUNT(*) FROM professional_profiles WHERE email = %s", ("engineer@example.gov",))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO professional_profiles (email, name, organization, affiliation, verification, approval_status) VALUES (%s, %s, %s, %s, %s, 'Active')", ("engineer@example.gov", "Arun Mehta", "Bengaluru Urban Transport Authority", "Government transport professional", "Verified by organization"))
        cursor.execute("SELECT COUNT(*) FROM universities")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO universities (name, district, domains, contact_email) VALUES (%s, %s, %s, %s)",
                (
                    ("Birla Institute of Technology, Mesra", "Ranchi", "Engineering, Energy, Water Resources", "innovation@bitmesra.ac.in"),
                    ("National Institute of Technology, Jamshedpur", "East Singhbhum", "Engineering, Urban Infrastructure, Energy", "innovation@nitjsr.ac.in"),
                    ("Central University of Jharkhand", "Ranchi", "Education, Healthcare, Rural Livelihoods", "innovation@cuj.ac.in"),
                ),
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS industry_partners (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                partner_type VARCHAR(50) NOT NULL,
                district VARCHAR(100) NOT NULL,
                domains TEXT NOT NULL,
                contact_email VARCHAR(255) NOT NULL UNIQUE,
                approval_status VARCHAR(30) NOT NULL DEFAULT 'Active',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            cursor.execute("ALTER TABLE industry_partners ADD COLUMN approval_status VARCHAR(30) NOT NULL DEFAULT 'Active'")
        except Error as error:
            if error.errno != 1060:
                raise
        try:
            cursor.execute("ALTER TABLE team_members ADD COLUMN member_role VARCHAR(30) NOT NULL DEFAULT 'Student'")
        except Error as error:
            if error.errno != 1060:
                raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS support_offers (
                id INT PRIMARY KEY AUTO_INCREMENT,
                issue_id INT NOT NULL,
                partner_id INT NOT NULL,
                support_type VARCHAR(50) NOT NULL,
                details TEXT NOT NULL,
                funding_amount BIGINT NOT NULL DEFAULT 0,
                resources TEXT,
                timeline VARCHAR(100),
                status VARCHAR(30) NOT NULL DEFAULT 'Offered',
                commitment_note TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (partner_id) REFERENCES industry_partners(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS support_requests (
                id INT PRIMARY KEY AUTO_INCREMENT,
                issue_id INT NOT NULL,
                university_id INT NOT NULL,
                requested_by VARCHAR(255) NOT NULL,
                support_type VARCHAR(50) NOT NULL,
                details TEXT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Requested',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (university_id) REFERENCES universities(id) ON DELETE CASCADE
            )
            """
        )
        for statement in (
            "ALTER TABLE support_offers ADD COLUMN commitment_note TEXT",
            "ALTER TABLE support_offers ADD COLUMN funding_amount BIGINT NOT NULL DEFAULT 0",
            "ALTER TABLE support_offers ADD COLUMN resources TEXT",
            "ALTER TABLE support_offers ADD COLUMN timeline VARCHAR(100)",
        ):
            try:
                cursor.execute(statement)
            except Error as error:
                if error.errno != 1060:
                    raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INT PRIMARY KEY AUTO_INCREMENT,
                recipient VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                related_type VARCHAR(50),
                related_id INT,
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INT PRIMARY KEY AUTO_INCREMENT,
                sender VARCHAR(255) NOT NULL,
                recipient VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                related_type VARCHAR(50),
                related_id INT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("SELECT COUNT(*) FROM industry_partners")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO industry_partners (name, partner_type, district, domains, contact_email) VALUES (%s, %s, %s, %s, %s)",
                (
                    ("Jharkhand Innovation Network", "Startup", "Ranchi", "Education, Agriculture, Energy", "partner@jin.example"),
                    ("Adivasi Livelihoods Foundation", "CSR Organization", "Khunti", "Rural Livelihoods, Healthcare, Water Resources", "connect@alf.example"),
                    ("Eastern Tech Manufacturing", "MSME", "East Singhbhum", "Engineering, Urban Infrastructure, Sanitation", "innovation@etm.example"),
                ),
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id VARCHAR(64) PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rate_limits (
                client_key VARCHAR(255) PRIMARY KEY,
                request_count INT NOT NULL DEFAULT 1,
                reset_at TIMESTAMP NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contractors (
                id INT PRIMARY KEY AUTO_INCREMENT,
                company_name VARCHAR(255) NOT NULL,
                owner_name VARCHAR(255) NOT NULL,
                license_no VARCHAR(100) NOT NULL UNIQUE,
                district VARCHAR(100) NOT NULL,
                specializations TEXT NOT NULL,
                contact_email VARCHAR(255) NOT NULL UNIQUE,
                phone VARCHAR(20) NOT NULL,
                approval_status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                performance_score INT NOT NULL DEFAULT 0,
                complaint_count INT NOT NULL DEFAULT 0,
                completed_projects INT NOT NULL DEFAULT 0,
                block_reason TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            cursor.execute("ALTER TABLE contractors ADD COLUMN block_reason TEXT")
        except Error as error:
            if error.errno != 1060:
                raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contractor_assignments (
                id INT PRIMARY KEY AUTO_INCREMENT,
                issue_id INT NOT NULL,
                contractor_id INT NOT NULL,
                assigned_by VARCHAR(255) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Assigned',
                completion_note TEXT,
                progress_image_type VARCHAR(50),
                progress_image_data LONGBLOB,
                assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (contractor_id) REFERENCES contractors(id) ON DELETE CASCADE
            )
            """
        )
        for statement in (
            "ALTER TABLE contractor_assignments ADD COLUMN progress_image_type VARCHAR(50)",
            "ALTER TABLE contractor_assignments ADD COLUMN progress_image_data LONGBLOB",
        ):
            try:
                cursor.execute(statement)
            except Error as error:
                if error.errno != 1060:
                    raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contractor_complaints (
                id INT PRIMARY KEY AUTO_INCREMENT,
                contractor_id INT NOT NULL,
                issue_id INT NOT NULL,
                filed_by VARCHAR(255) NOT NULL,
                complaint_type VARCHAR(50) NOT NULL,
                description TEXT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                reviewed_by VARCHAR(255),
                reviewed_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contractor_id) REFERENCES contractors(id) ON DELETE CASCADE,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
            )
            """
        )
        _migrate_memory_records(cursor)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _issue(row: tuple[Any, ...]) -> dict[str, Any]:
    keys = ("id", "title", "category", "area", "district", "block", "lat", "lng", "description", "supporters", "age", "proof_id", "proof_type", "proof_status", "proof_message", "predicted_category", "category_confidence", "priority_score", "priority_label", "matching_explanation", "moderation_status", "moderation_reason", "moderated_by", "reporter", "video_id", "video_predicted_category", "video_confidence", "video_explanation")
    issue = {key: value for key, value in zip(keys, row) if value is not None}
    for coordinate in ("lat", "lng"):
        if isinstance(issue.get(coordinate), Decimal):
            issue[coordinate] = float(issue[coordinate])
    if isinstance(issue.get("category_confidence"), Decimal):
        issue["category_confidence"] = float(issue["category_confidence"])
    if isinstance(issue.get("video_confidence"), Decimal):
        issue["video_confidence"] = float(issue["video_confidence"])
    return issue


def load_issues() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return list(_MEM_ISSUES)
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, title, category, area, district, block, latitude, longitude, description, supporters, age, proof_id, proof_type, proof_status, proof_message, predicted_category, category_confidence, priority_score, priority_label, matching_explanation, moderation_status, moderation_reason, moderated_by, reporter, video_id, video_predicted_category, video_confidence, video_explanation FROM issues ORDER BY id")
        return [_issue(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def load_user_issues(reporter: str) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [i for i in _MEM_ISSUES if str(i.get("reporter", "")).casefold() == reporter.casefold()]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT i.id, i.title, i.description, i.district, i.block, i.category, i.moderation_status, i.moderation_reason, a.status AS assignment_status, u.name AS university_name, t.id AS team_id, t.name AS team_name, t.status AS team_status, ca.id AS contractor_assignment_id, ca.contractor_id, c.company_name AS contractor_name, ca.status AS contractor_assignment_status, ca.completion_note AS contractor_completion_note, ca.progress_image_type AS contractor_progress_image_type FROM issues i LEFT JOIN issue_assignments a ON a.issue_id = i.id LEFT JOIN universities u ON u.id = a.university_id LEFT JOIN project_teams t ON t.issue_id = i.id AND t.university_id = a.university_id LEFT JOIN contractor_assignments ca ON ca.issue_id = i.id LEFT JOIN contractors c ON c.id = ca.contractor_id WHERE LOWER(i.reporter) = LOWER(%s) ORDER BY i.id DESC", (reporter,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

def insert_issue(issue: dict[str, Any]) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        iid = max((i["id"] for i in _MEM_ISSUES), default=0) + 1
        saved = dict(issue)
        for private_field in ("_proof_type", "_proof_data", "_video_type", "_video_data"):
            saved.pop(private_field, None)
        saved.update({"id": iid, "supporters": 1, "age": "just now", "moderation_status": "Pending"})
        _MEM_ISSUES.append(saved)
        _save_memory_issues()
        return saved
    connection = connect()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO issues
            (title, category, ai_category, ai_confidence, category_mismatch, ai_tags, tagging_model,
             area, district, block, latitude, longitude, description, supporters, age,
             proof_id, proof_type, proof_data, proof_status, proof_message,
             predicted_category, category_confidence, priority_score, priority_label, matching_explanation,
             moderation_status, reporter,
             video_id, video_type, video_data, video_predicted_category, video_confidence, video_explanation)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, 1, 'just now',
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    'Pending', %s,
                    %s, %s, %s, %s, %s, %s)
            """,
            (
                issue["title"], issue["category"],
                issue.get("problem_type"), issue.get("tag_confidence"),
                issue.get("category_mismatch", False), issue.get("problem_tags"),
                issue.get("tag_version"),
                issue.get("area", ""), issue.get("district", "Ranchi"), issue.get("block", ""),
                issue["lat"], issue["lng"], issue.get("description", ""),
                issue.get("proof_id"), issue.get("_proof_type"), issue.get("_proof_data"),
                issue.get("proof_status"), issue.get("proof_message"),
                issue.get("predicted_category"), issue.get("category_confidence") or issue.get("tag_confidence"),
                issue.get("priority_score"), issue.get("priority_label"),
                issue.get("matching_explanation"), issue.get("reporter"),
                issue.get("video_id"), issue.get("_video_type"), issue.get("_video_data"),
                issue.get("video_predicted_category"), issue.get("video_confidence"),
                issue.get("video_explanation"),
            ),
        )

        issue_id = cursor.lastrowid
        reporter = str(issue.get("reporter", "")).strip()

        if reporter:
            cursor.execute(
                "INSERT INTO issue_supporters (issue_id, user_email) VALUES (%s, %s)",
                (issue_id, reporter),
            )
        connection.commit()

        saved = dict(issue)

        # Don't return raw proof/video data to the application
        saved.pop("_proof_type", None)
        saved.pop("_proof_data", None)
        saved.pop("_video_type", None)
        saved.pop("_video_data", None)

        saved.update({
            "id": issue_id or cursor.lastrowid,
            "supporters": 1,
            "age": "just now",
        })
        return saved

    finally:
        cursor.close()
        connection.close()


def update_issue(issue: dict[str, Any]) -> None:
    if not _DB_AVAILABLE:
        existing = next((i for i in _MEM_ISSUES if i["id"] == issue.get("id")), None)
        if existing:
            existing.update(issue)
            _save_memory_issues()
        return
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE issues SET supporters = %s, proof_id = %s, proof_type = %s, proof_data = %s, proof_status = %s, proof_message = %s, video_id = %s, video_type = %s, video_data = %s, video_predicted_category = %s, video_confidence = %s, video_explanation = %s WHERE id = %s",
            (issue.get("supporters", 0), issue.get("proof_id"), issue.get("_proof_type"), issue.get("_proof_data"), issue.get("proof_status"), issue.get("proof_message"), issue.get("video_id"), issue.get("_video_type"), issue.get("_video_data"), issue.get("video_predicted_category"), issue.get("video_confidence"), issue.get("video_explanation"), issue["id"]),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def moderate_issue(issue_id: int, status: str, reason: str, moderator: str) -> bool:
    if not _DB_AVAILABLE:
        existing = next((i for i in _MEM_ISSUES if i["id"] == issue_id), None)
        if existing:
            existing["moderation_status"] = status
            existing["moderation_reason"] = reason
            existing["moderated_by"] = moderator
            _save_memory_issues()
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE issues SET moderation_status = %s, moderation_reason = %s, moderated_by = %s WHERE id = %s",
            (status, reason, moderator, issue_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def get_proof(proof_id: str) -> tuple[str, bytes] | None:
    if not _DB_AVAILABLE:
        return None
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT proof_type, proof_data FROM issues WHERE proof_id = %s", (proof_id,))
        row = cursor.fetchone()
        if not row or row[1] is None:
            return None
        return row[0] or "application/octet-stream", bytes(row[1])
    finally:
        cursor.close()
        connection.close()



def get_video(video_id: str) -> tuple[str, bytes] | None:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT video_type, video_data FROM issues WHERE video_id = %s", (video_id,))
        row = cursor.fetchone()
        if not row or row[1] is None:
            return None
        return row[0] or "video/mp4", bytes(row[1])
    finally:
        cursor.close()
        connection.close()

def load_proposals() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return list(_MEM_PROPOSALS)
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, issue_id, title, description, author, votes, status, visual_type, review_decision, review_explanation, reviewer FROM proposals ORDER BY id")
        proposals = []
        for row in cursor.fetchall():
            proposal = dict(zip(("id", "issue_id", "title", "description", "author", "votes", "status", "visual_type", "review_decision", "review_explanation", "reviewer"), row))
            proposal["visual"] = ""
            if proposal["visual_type"]:
                proposal["visual_url"] = f"/proposal-visual/{proposal['id']}"
            proposal["review"] = None
            if proposal["review_decision"]:
                proposal["review"] = {"decision": proposal["review_decision"], "explanation": proposal["review_explanation"], "reviewer": proposal["reviewer"]}
            proposal.pop("review_decision")
            proposal.pop("review_explanation")
            proposal.pop("reviewer")
            proposals.append(proposal)
        return proposals
    finally:
        cursor.close()
        connection.close()


def insert_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        pid = max((p["id"] for p in _MEM_PROPOSALS), default=0) + 1
        saved = dict(proposal)
        saved.update({"id": pid, "votes": 0, "status": "Submitted", "review": None})
        _MEM_PROPOSALS.append(saved)
        return saved
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO proposals (issue_id, title, description, author, votes, status, visual_type, visual_data) VALUES (%s, %s, %s, %s, 0, 'Submitted', %s, %s)",
            (proposal["issue_id"], proposal["title"], proposal["description"], proposal["author"], proposal.get("visual_type"), proposal.get("_visual_data")),
        )
        connection.commit()
        saved = dict(proposal)
        saved["id"] = cursor.lastrowid
        saved.update({"votes": 0, "status": "Submitted", "review": None})
        saved.pop("_visual_data", None)
        if saved.get("visual_type") and proposal.get("_visual_data"):
            saved["visual_url"] = f"/proposal-visual/{saved['id']}"
        return saved
    finally:
        cursor.close()
        connection.close()


def update_proposal(proposal: dict[str, Any]) -> None:
    if not _DB_AVAILABLE:
        existing = next((p for p in _MEM_PROPOSALS if p["id"] == proposal.get("id")), None)
        if existing:
            existing.update(proposal)
        return
    connection = connect()
    try:
        cursor = connection.cursor()
        review = proposal.get("review") or {}
        cursor.execute(
            "UPDATE proposals SET votes = %s, status = %s, review_decision = %s, review_explanation = %s, reviewer = %s WHERE id = %s",
            (proposal.get("votes", 0), proposal.get("status", "Submitted"), review.get("decision"), review.get("explanation"), review.get("reviewer"), proposal["id"]),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def cast_proposal_vote(proposal_id: int, user_email: str) -> tuple[str, int, int | None]:
    """Record one active solution choice per supporter and issue."""
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT issue_id FROM proposals WHERE id = %s", (proposal_id,))
        row = cursor.fetchone()
        if row is None:
            return "missing", 0, None
        issue_id = int(row[0])
        cursor.execute("SELECT 1 FROM issue_supporters WHERE issue_id = %s AND user_email = %s", (issue_id, user_email))
        if cursor.fetchone() is None:
            return "ineligible", 0, None
        cursor.execute("SELECT proposal_id FROM proposal_votes WHERE issue_id = %s AND user_email = %s FOR UPDATE", (issue_id, user_email))
        previous = cursor.fetchone()
        previous_proposal_id = int(previous[0]) if previous else None
        if previous_proposal_id == proposal_id:
            cursor.execute("SELECT votes FROM proposals WHERE id = %s", (proposal_id,))
            count = cursor.fetchone()
            return "already_voted", int(count[0]) if count else 0, previous_proposal_id
        if previous_proposal_id is None:
            cursor.execute("INSERT INTO proposal_votes (issue_id, user_email, proposal_id) VALUES (%s, %s, %s)", (issue_id, user_email, proposal_id))
            result = "voted"
        else:
            cursor.execute("UPDATE proposals SET votes = GREATEST(votes - 1, 0) WHERE id = %s", (previous_proposal_id,))
            cursor.execute("UPDATE proposal_votes SET proposal_id = %s WHERE issue_id = %s AND user_email = %s", (proposal_id, issue_id, user_email))
            result = "changed"
        cursor.execute("UPDATE proposals SET votes = votes + 1 WHERE id = %s", (proposal_id,))
        cursor.execute("SELECT votes FROM proposals WHERE id = %s", (proposal_id,))
        count = cursor.fetchone()
        connection.commit()
        return result, int(count[0]) if count else 0, previous_proposal_id
    finally:
        cursor.close()
        connection.close()


def get_proposal_visual(proposal_id: int) -> tuple[str, bytes] | None:
    if not _DB_AVAILABLE:
        return None
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT visual_type, visual_data FROM proposals WHERE id = %s", (proposal_id,))
        row = cursor.fetchone()
        if not row or row[1] is None:
            return None
        return row[0] or "application/octet-stream", bytes(row[1])
    finally:
        cursor.close()
        connection.close()


def load_universities() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return list(_MEM_UNIVERSITIES)
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, district, domains, expertise, departments, laboratories, incubation_facilities, contact_email, approval_status FROM universities ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def update_university(university_id: int, name: str, district: str, domains: str, departments: str, laboratories: str, incubation_facilities: str, contact_email: str, expertise: str = "") -> bool:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE universities SET name = %s, district = %s, domains = %s, expertise = %s, departments = %s, laboratories = %s, incubation_facilities = %s, contact_email = %s WHERE id = %s",
            (name, district, domains, expertise, departments, laboratories, incubation_facilities, contact_email, university_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def create_university(name: str, district: str, domains: str, departments: str, laboratories: str, incubation_facilities: str, contact_email: str, expertise: str = "", approval_status: str = "Pending") -> dict[str, Any]:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO universities (name, district, domains, expertise, departments, laboratories, incubation_facilities, contact_email, approval_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (name, district, domains, expertise, departments, laboratories, incubation_facilities, contact_email, approval_status))
        connection.commit()
        return {"id": cursor.lastrowid, "name": name, "district": district, "domains": domains, "expertise": expertise, "departments": departments, "laboratories": laboratories, "incubation_facilities": incubation_facilities, "contact_email": contact_email, "approval_status": approval_status}
    finally:
        cursor.close()
        connection.close()


def assign_issue(issue_id: int, university_id: int, assigned_by: str) -> bool:
    if not _DB_AVAILABLE:
        _MEM_ASSIGNMENTS[issue_id] = {"issue_id": issue_id, "university_id": university_id, "status": "Assigned", "response_reason": "", "assigned_by": assigned_by}
        return True
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO issue_assignments (issue_id, university_id, assigned_by) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE university_id = VALUES(university_id), status = 'Assigned', assigned_by = VALUES(assigned_by), assigned_at = CURRENT_TIMESTAMP",
            (issue_id, university_id, assigned_by),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def load_assignments() -> dict[int, dict[str, Any]]:
    if not _DB_AVAILABLE:
        return dict(_MEM_ASSIGNMENTS)
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT issue_id, university_id, status, response_reason, assigned_by FROM issue_assignments")
        return {row["issue_id"]: row for row in cursor.fetchall()}
    finally:
        cursor.close()
        connection.close()


def load_university_assignments(contact_email: str) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        uni = next((u for u in _MEM_UNIVERSITIES if str(u.get("contact_email", "")).casefold() == contact_email.casefold()), None)
        if not uni:
            return []
        from community import ISSUES
        results = []
        for a in _MEM_ASSIGNMENTS.values():
            if a["university_id"] == uni["id"]:
                iss = next((i for i in ISSUES if i.get("id") == a["issue_id"]), {})
                results.append({
                    "issue_id": a["issue_id"],
                    "university_id": uni["id"],
                    "status": a.get("status", "Assigned"),
                    "response_reason": a.get("response_reason", ""),
                    "title": iss.get("title", f"Challenge #{a['issue_id']}"),
                    "description": iss.get("description", ""),
                    "district": iss.get("district", "Ranchi"),
                    "block": iss.get("block", ""),
                    "category": iss.get("category", "General"),
                    "university_name": uni["name"],
                })
        return results
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT a.issue_id, a.university_id, a.status, a.response_reason, i.title, i.description, i.district, i.block, i.category, u.name AS university_name FROM issue_assignments a JOIN universities u ON u.id = a.university_id JOIN issues i ON i.id = a.issue_id WHERE LOWER(u.contact_email) = LOWER(%s) ORDER BY a.assigned_at DESC",
            (contact_email,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def update_assignment(issue_id: int, status: str, reason: str) -> bool:
    if not _DB_AVAILABLE:
        if issue_id in _MEM_ASSIGNMENTS:
            _MEM_ASSIGNMENTS[issue_id]["status"] = status
            _MEM_ASSIGNMENTS[issue_id]["response_reason"] = reason
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE issue_assignments SET status = %s, response_reason = %s WHERE issue_id = %s",
            (status, reason, issue_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def load_teams() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        teams = list(_MEM_TEAMS)
        for team in teams:
            team.setdefault("member_roles", {member: "Student" for member in team.get("members", [])})
        return teams
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, issue_id, university_id, name, faculty_mentor, status FROM project_teams ORDER BY id")
        teams = cursor.fetchall()
        for team in teams:
            cursor.execute("SELECT student_email, member_role FROM team_members WHERE team_id = %s ORDER BY student_email", (team["id"],))
            members = cursor.fetchall()
            team["members"] = [row["student_email"] for row in members]
            team["member_roles"] = {row["student_email"]: row.get("member_role", "Student") for row in members}
        return teams
    finally:
        cursor.close()
        connection.close()


def create_team(issue_id: int, university_id: int, name: str, faculty_mentor: str, members: list[str], member_roles: dict[str, str] | None = None) -> dict[str, Any]:
    member_roles = member_roles or {}
    if not _DB_AVAILABLE:
        tid = max((t["id"] for t in _MEM_TEAMS), default=0) + 1
        rec = {"id": tid, "issue_id": issue_id, "university_id": university_id, "name": name, "faculty_mentor": faculty_mentor, "status": "Forming", "members": members, "member_roles": {member: member_roles.get(member, "Student") for member in members}, "ip_outcome": "", "startup_outcome": "", "impact_summary": "", "pilot_location": "", "pilot_start_date": "", "pilot_end_date": "", "beneficiary_count": 0, "outcome_metric": ""}
        _MEM_TEAMS.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO project_teams (issue_id, university_id, name, faculty_mentor) VALUES (%s, %s, %s, %s)", (issue_id, university_id, name, faculty_mentor))
        team_id = cursor.lastrowid
        cursor.executemany("INSERT INTO team_members (team_id, student_email, member_role) VALUES (%s, %s, %s)", [(team_id, member, member_roles.get(member, "Student")) for member in members])
        connection.commit()
        return {"id": team_id, "issue_id": issue_id, "university_id": university_id, "name": name, "faculty_mentor": faculty_mentor, "status": "Forming", "members": members, "member_roles": {member: member_roles.get(member, "Student") for member in members}}
    finally:
        cursor.close()
        connection.close()


def update_team_status(team_id: int, status: str, changed_by: str = "system", note: str = "") -> bool:
    if not _DB_AVAILABLE:
        t = next((item for item in _MEM_TEAMS if item["id"] == team_id), None)
        if t:
            t["status"] = status
            _MEM_STATUS_HISTORY.append({"id": len(_MEM_STATUS_HISTORY) + 1, "team_id": team_id, "status": status, "changed_by": changed_by, "note": note, "changed_at": "just now"})
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE project_teams SET status = %s WHERE id = %s", (status, team_id))
        if cursor.rowcount:
            cursor.execute("INSERT INTO project_status_history (team_id, status, changed_by, note) VALUES (%s, %s, %s, %s)", (team_id, status, changed_by, note))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def create_milestone(team_id: int, title: str, due_date: str, deliverable: str, deliverable_type: str = "", deliverable_data: bytes = b"") -> dict[str, Any]:
    if not _DB_AVAILABLE:
        mid = max((m["id"] for m in _MEM_MILESTONES), default=0) + 1
        rec = {"id": mid, "team_id": team_id, "title": title, "due_date": due_date, "status": "Pending", "deliverable": deliverable, "testing_result": "", "deliverable_type": deliverable_type, "deliverable_data": deliverable_data}
        _MEM_MILESTONES.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO milestones (team_id, title, due_date, deliverable, deliverable_type, deliverable_data) VALUES (%s, %s, NULLIF(%s, ''), %s, %s, %s)", (team_id, title, due_date, deliverable, deliverable_type, deliverable_data))
        connection.commit()
        return {"id": cursor.lastrowid, "team_id": team_id, "title": title, "due_date": due_date, "status": "Pending", "deliverable": deliverable}
    finally:
        cursor.close()
        connection.close()


def load_milestones(team_id: int) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [m for m in _MEM_MILESTONES if m["team_id"] == team_id]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, team_id, title, due_date, status, deliverable, testing_result, completed_at, deliverable_type FROM milestones WHERE team_id = %s ORDER BY due_date, id", (team_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_milestone_deliverable(milestone_id: int) -> tuple[str, bytes] | None:
    if not _DB_AVAILABLE:
        milestone = next((item for item in _MEM_MILESTONES if item["id"] == milestone_id), None)
        if not milestone or not milestone.get("deliverable_data"):
            return None
        return milestone.get("deliverable_type") or "application/octet-stream", bytes(milestone["deliverable_data"])
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT deliverable_type, deliverable_data FROM milestones WHERE id = %s", (milestone_id,))
        row = cursor.fetchone()
        if not row or row[1] is None:
            return None
        return row[0] or "application/octet-stream", bytes(row[1])
    finally:
        cursor.close()
        connection.close()


def load_status_history(team_id: int) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [h for h in _MEM_STATUS_HISTORY if h["team_id"] == team_id]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, team_id, status, changed_by, note, changed_at FROM project_status_history WHERE team_id = %s ORDER BY changed_at DESC, id DESC", (team_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_dashboard_metrics() -> dict[str, Any]:
    if not _DB_AVAILABLE:
        from community import ISSUES
        university_names = {university["id"]: university["name"] for university in _MEM_UNIVERSITIES}
        university_participation = {}
        for assignment in _MEM_ASSIGNMENTS.values():
            name = university_names.get(assignment.get("university_id"), "Unknown university")
            university_participation[name] = university_participation.get(name, 0) + 1
        support_by_type = {}
        for offer in _MEM_OFFERS:
            support_type = offer.get("support_type", "Other")
            support_by_type[support_type] = support_by_type.get(support_type, 0) + 1
        completed_projects = sum(team.get("status") in {"Deployed", "Impact Measured"} for team in _MEM_TEAMS)
        impact_projects = sum(bool(team.get("impact_summary")) for team in _MEM_TEAMS)
        patent_outcomes = sum(bool(team.get("ip_outcome")) for team in _MEM_TEAMS)
        startup_outcomes = sum(bool(team.get("startup_outcome")) for team in _MEM_TEAMS)
        beneficiary_total = sum(int(team.get("beneficiary_count") or 0) for team in _MEM_TEAMS)
        measured_outcomes = sum(bool(team.get("outcome_metric")) for team in _MEM_TEAMS)
        return {
            "total_issues": len(ISSUES),
            "moderation": [{"status": "Approved", "total": len([i for i in ISSUES if i.get("moderation_status") == "Approved"])}, {"status": "Pending", "total": len([i for i in ISSUES if i.get("moderation_status") != "Approved"])}],
            "district_domains": [{"district": i.get("district", "Ranchi"), "category": i.get("category", "General"), "total": 1} for i in ISSUES],
            "universities": len(_MEM_UNIVERSITIES),
            "assignments": len(_MEM_ASSIGNMENTS),
            "industry_partners": len(_MEM_INDUSTRY),
            "support_offers": len(_MEM_OFFERS),
            "project_stages": [{"status": "Prototype", "total": len(_MEM_TEAMS)}],
            "proposals": len(_MEM_PROPOSALS),
            "university_participation": [{"university": name, "total": total} for name, total in university_participation.items()],
            "support_by_type": [{"support_type": support_type, "total": total} for support_type, total in support_by_type.items()],
            "project_outcomes": [{"outcome": "Completed or deployed projects", "total": completed_projects}, {"outcome": "Projects with impact reports", "total": impact_projects}, {"outcome": "IP or patent outcomes", "total": patent_outcomes}, {"outcome": "Startup outcomes", "total": startup_outcomes}, {"outcome": "Beneficiaries reached", "total": beneficiary_total}, {"outcome": "Measured outcomes", "total": measured_outcomes}],
        }
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        metrics: dict[str, Any] = {}
        cursor.execute("SELECT COUNT(*) AS total FROM issues")
        metrics["total_issues"] = cursor.fetchone()["total"]
        cursor.execute("SELECT moderation_status AS status, COUNT(*) AS total FROM issues GROUP BY moderation_status ORDER BY moderation_status")
        metrics["moderation"] = cursor.fetchall()
        cursor.execute("SELECT district, category, COUNT(*) AS total FROM issues GROUP BY district, category ORDER BY district, category")
        metrics["district_domains"] = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS total FROM universities")
        metrics["universities"] = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM issue_assignments")
        metrics["assignments"] = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM industry_partners")
        metrics["industry_partners"] = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM support_offers")
        metrics["support_offers"] = cursor.fetchone()["total"]
        cursor.execute("SELECT status, COUNT(*) AS total FROM project_teams GROUP BY status ORDER BY status")
        metrics["project_stages"] = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS total FROM proposals")
        metrics["proposals"] = cursor.fetchone()["total"]
        cursor.execute("SELECT u.name AS university, COUNT(a.issue_id) AS total FROM universities u LEFT JOIN issue_assignments a ON a.university_id = u.id GROUP BY u.id, u.name ORDER BY total DESC, u.name")
        metrics["university_participation"] = cursor.fetchall()
        cursor.execute("SELECT support_type, COUNT(*) AS total FROM support_offers GROUP BY support_type ORDER BY total DESC, support_type")
        metrics["support_by_type"] = cursor.fetchall()
        cursor.execute("SELECT 'Completed or deployed projects' AS outcome, COUNT(*) AS total FROM project_teams WHERE status IN ('Deployed', 'Impact Measured') UNION ALL SELECT 'Projects with impact reports', COUNT(*) FROM project_teams WHERE impact_summary IS NOT NULL AND impact_summary <> '' UNION ALL SELECT 'IP or patent outcomes', COUNT(*) FROM project_teams WHERE ip_outcome IS NOT NULL AND ip_outcome <> '' UNION ALL SELECT 'Startup outcomes', COUNT(*) FROM project_teams WHERE startup_outcome IS NOT NULL AND startup_outcome <> '' UNION ALL SELECT 'Beneficiaries reached', COALESCE(SUM(beneficiary_count), 0) FROM project_teams UNION ALL SELECT 'Measured outcomes', COUNT(*) FROM project_teams WHERE outcome_metric IS NOT NULL AND outcome_metric <> ''")
        metrics["project_outcomes"] = cursor.fetchall()
        return metrics
    finally:
        cursor.close()
        connection.close()


def update_milestone(milestone_id: int, status: str, testing_result: str) -> bool:
    if not _DB_AVAILABLE:
        m = next((item for item in _MEM_MILESTONES if item["id"] == milestone_id), None)
        if m:
            m["status"] = status
            m["testing_result"] = testing_result
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE milestones SET status = %s, testing_result = %s, completed_at = CASE WHEN %s = 'Completed' THEN CURRENT_DATE ELSE NULL END WHERE id = %s", (status, testing_result, status, milestone_id))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def update_team_outcomes(team_id: int, ip_outcome: str, startup_outcome: str, impact_summary: str, pilot_location: str = "", pilot_start_date: str = "", pilot_end_date: str = "", beneficiary_count: int = 0, outcome_metric: str = "") -> bool:
    if not _DB_AVAILABLE:
        t = next((item for item in _MEM_TEAMS if item["id"] == team_id), None)
        if t:
            t["ip_outcome"] = ip_outcome
            t["startup_outcome"] = startup_outcome
            t["impact_summary"] = impact_summary
            t["pilot_location"] = pilot_location
            t["pilot_start_date"] = pilot_start_date
            t["pilot_end_date"] = pilot_end_date
            t["beneficiary_count"] = beneficiary_count
            t["outcome_metric"] = outcome_metric
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE project_teams SET ip_outcome = %s, startup_outcome = %s, impact_summary = %s, pilot_location = %s, pilot_start_date = NULLIF(%s, ''), pilot_end_date = NULLIF(%s, ''), beneficiary_count = %s, outcome_metric = %s WHERE id = %s", (ip_outcome, startup_outcome, impact_summary, pilot_location, pilot_start_date, pilot_end_date, beneficiary_count, outcome_metric, team_id))
        connection.commit()
        cursor.execute("SELECT id FROM project_teams WHERE id = %s", (team_id,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        connection.close()


def create_project_review(team_id: int, review_type: str, decision: str, notes: str, reviewed_by: str) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        review = {"id": len(_MEM_PROJECT_REVIEWS) + 1, "team_id": team_id, "review_type": review_type, "decision": decision, "notes": notes, "reviewed_by": reviewed_by, "created_at": "just now"}
        _MEM_PROJECT_REVIEWS.append(review)
        return review
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO project_reviews (team_id, review_type, decision, notes, reviewed_by) VALUES (%s, %s, %s, %s, %s)", (team_id, review_type, decision, notes, reviewed_by))
        connection.commit()
        return {"id": cursor.lastrowid, "team_id": team_id, "review_type": review_type, "decision": decision, "notes": notes, "reviewed_by": reviewed_by}
    finally:
        cursor.close()
        connection.close()


def load_project_reviews(team_id: int | None = None) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [review for review in _MEM_PROJECT_REVIEWS if team_id is None or review["team_id"] == team_id]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        if team_id is None:
            cursor.execute("SELECT id, team_id, review_type, decision, notes, reviewed_by, created_at FROM project_reviews ORDER BY created_at DESC, id DESC")
        else:
            cursor.execute("SELECT id, team_id, review_type, decision, notes, reviewed_by, created_at FROM project_reviews WHERE team_id = %s ORDER BY created_at DESC, id DESC", (team_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def create_professional_profile(email: str, name: str, organization: str, affiliation: str, verification: str, approval_status: str = "Pending") -> dict[str, Any]:
    email = email.strip().lower()
    if not _DB_AVAILABLE:
        existing = next((item for item in _MEM_PROFESSIONALS if item["email"] == email), None)
        if existing:
            raise ValueError("Professional profile already exists")
        profile = {"email": email, "name": name, "organization": organization, "affiliation": affiliation, "verification": verification, "approval_status": approval_status}
        _MEM_PROFESSIONALS.append(profile)
        return profile
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO professional_profiles (email, name, organization, affiliation, verification, approval_status) VALUES (%s, %s, %s, %s, %s, %s)", (email, name, organization, affiliation, verification, approval_status))
        connection.commit()
        return {"email": email, "name": name, "organization": organization, "affiliation": affiliation, "verification": verification, "approval_status": approval_status}
    finally:
        cursor.close()
        connection.close()


def load_professional_profiles(approval_status: str | None = None) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [item for item in _MEM_PROFESSIONALS if approval_status is None or item["approval_status"] == approval_status]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        if approval_status is None:
            cursor.execute("SELECT email, name, organization, affiliation, verification, approval_status FROM professional_profiles ORDER BY name")
        else:
            cursor.execute("SELECT email, name, organization, affiliation, verification, approval_status FROM professional_profiles WHERE approval_status = %s ORDER BY name", (approval_status,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def update_professional_approval(email: str, status: str) -> bool:
    if status not in {"Active", "Rejected", "Pending"}:
        return False
    email = email.strip().lower()
    if not _DB_AVAILABLE:
        profile = next((item for item in _MEM_PROFESSIONALS if item["email"] == email), None)
        if profile:
            profile["approval_status"] = status
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE professional_profiles SET approval_status = %s WHERE email = %s", (status, email))
        connection.commit()
        cursor.execute("SELECT approval_status FROM professional_profiles WHERE email = %s", (email,))
        row = cursor.fetchone()
        return bool(row and row[0] == status)
    finally:
        cursor.close()
        connection.close()


def load_industry_partners() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return list(_MEM_INDUSTRY)
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, partner_type, district, domains, contact_email, approval_status FROM industry_partners ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_partner_offers(contact_email: str) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        from community import ISSUES
        p = next((partner for partner in _MEM_INDUSTRY if str(partner.get("contact_email", "")).casefold() == contact_email.casefold()), None)
        if not p:
            return []
        results = []
        for o in _MEM_OFFERS:
            if o.get("partner_id") == p["id"]:
                iss = next((i for i in ISSUES if i.get("id") == o["issue_id"]), {})
                results.append({
                    "id": o["id"],
                    "issue_id": o["issue_id"],
                    "partner_id": p["id"],
                    "support_type": o["support_type"],
                    "details": o["details"],
                    "status": o.get("status", "Offered"),
                    "commitment_note": o.get("commitment_note", ""),
                    "title": iss.get("title", f"Challenge #{o['issue_id']}"),
                    "district": iss.get("district", "Ranchi"),
                    "block": iss.get("block", ""),
                    "partner_name": p["name"],
                })
        return results
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT o.id, o.issue_id, o.partner_id, o.support_type, o.details, 
                   o.funding_amount, o.resources, o.timeline, o.status, o.commitment_note, o.created_at,
                   i.title, i.district, i.block, i.category, i.description AS issue_description,
                   p.name AS partner_name
            FROM support_offers o
            JOIN industry_partners p ON p.id = o.partner_id
            JOIN issues i ON i.id = o.issue_id
            WHERE LOWER(p.contact_email) = LOWER(%s)
            ORDER BY o.id DESC
            """,
            (contact_email,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_all_partner_offers() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        from community import ISSUES
        results = []
        for o in _MEM_OFFERS:
            p = next((partner for partner in _MEM_INDUSTRY if partner["id"] == o.get("partner_id")), {})
            iss = next((i for i in ISSUES if i.get("id") == o["issue_id"]), {})
            results.append({
                "id": o["id"],
                "issue_id": o["issue_id"],
                "partner_id": o.get("partner_id"),
                "support_type": o["support_type"],
                "details": o["details"],
                "status": o.get("status", "Offered"),
                "commitment_note": o.get("commitment_note", ""),
                "title": iss.get("title", f"Challenge #{o['issue_id']}"),
                "partner_name": p.get("name", "Industry Partner"),
            })
        return results
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT o.id, o.issue_id, o.partner_id, o.support_type, o.details,
                   o.funding_amount, o.resources, o.timeline, o.status, o.commitment_note, o.created_at,
                   i.title, i.district, i.category, p.name AS partner_name
            FROM support_offers o
            JOIN industry_partners p ON p.id = o.partner_id
            JOIN issues i ON i.id = o.issue_id
            ORDER BY o.id DESC
            """
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def create_support_request(issue_id: int, university_id: int, requested_by: str, support_type: str, details: str) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        request = {"id": len(_MEM_SUPPORT_REQUESTS) + 1, "issue_id": issue_id, "university_id": university_id, "requested_by": requested_by, "support_type": support_type, "details": details, "status": "Requested"}
        _MEM_SUPPORT_REQUESTS.append(request)
        return request
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO support_requests (issue_id, university_id, requested_by, support_type, details) VALUES (%s, %s, %s, %s, %s)", (issue_id, university_id, requested_by, support_type, details))
        connection.commit()
        return {"id": cursor.lastrowid, "issue_id": issue_id, "university_id": university_id, "requested_by": requested_by, "support_type": support_type, "details": details, "status": "Requested"}
    finally:
        cursor.close()
        connection.close()


def load_support_requests(university_id: int | None = None) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [request for request in _MEM_SUPPORT_REQUESTS if university_id is None or request["university_id"] == university_id]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        if university_id is None:
            cursor.execute("SELECT id, issue_id, university_id, requested_by, support_type, details, status, created_at FROM support_requests ORDER BY created_at DESC, id DESC")
        else:
            cursor.execute("SELECT id, issue_id, university_id, requested_by, support_type, details, status, created_at FROM support_requests WHERE university_id = %s ORDER BY created_at DESC, id DESC", (university_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def create_support_offer(
    issue_id: int,
    partner_id: int,
    support_type: str,
    details: str,
    funding_amount: int = 0,
    resources: str = "",
    timeline: str = "",
) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        offer_id = max((offer["id"] for offer in _MEM_OFFERS), default=0) + 1
        rec = {
            "id": offer_id,
            "issue_id": issue_id,
            "partner_id": partner_id,
            "support_type": support_type,
            "details": details,
            "funding_amount": funding_amount,
            "resources": resources,
            "timeline": timeline,
            "status": "Offered",
            "commitment_note": "",
        }
        _MEM_OFFERS.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO support_offers (issue_id, partner_id, support_type, details, funding_amount, resources, timeline)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (issue_id, partner_id, support_type, details, funding_amount, resources, timeline),
        )
        connection.commit()
        return {
            "id": cursor.lastrowid,
            "issue_id": issue_id,
            "partner_id": partner_id,
            "support_type": support_type,
            "details": details,
            "funding_amount": funding_amount,
            "resources": resources,
            "timeline": timeline,
            "status": "Offered",
        }
    finally:
        cursor.close()
        connection.close()


def create_industry_partner(name: str, partner_type: str, district: str, domains: str, contact_email: str, approval_status: str = "Pending") -> dict[str, Any]:
    if not _DB_AVAILABLE:
        pid = max((p["id"] for p in _MEM_INDUSTRY), default=0) + 1
        rec = {"id": pid, "name": name, "partner_type": partner_type, "district": district, "domains": domains, "contact_email": contact_email, "approval_status": approval_status}
        _MEM_INDUSTRY.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO industry_partners (name, partner_type, district, domains, contact_email, approval_status) VALUES (%s, %s, %s, %s, %s, %s)", (name, partner_type, district, domains, contact_email, approval_status))
        connection.commit()
        return {"id": cursor.lastrowid, "name": name, "partner_type": partner_type, "district": district, "domains": domains, "contact_email": contact_email, "approval_status": approval_status}
    finally:
        cursor.close()
        connection.close()


def update_institution_approval(kind: str, institution_id: int, status: str) -> bool:
    if kind == "university":
        table = "universities"
    elif kind == "industry":
        table = "industry_partners"
    elif kind == "contractor":
        table = "contractors"
    else:
        return False
    if status not in {"Active", "Rejected", "Pending", "Blocked"}:
        return False
    if not _DB_AVAILABLE:
        records = _MEM_UNIVERSITIES if kind == "university" else _MEM_INDUSTRY
        record = next((item for item in records if item.get("id") == institution_id), None)
        if record is None:
            return False
        record["approval_status"] = status
        return True
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(f"UPDATE {table} SET approval_status = %s WHERE id = %s", (status, institution_id))
        connection.commit()
        cursor.execute(f"SELECT approval_status FROM {table} WHERE id = %s", (institution_id,))
        row = cursor.fetchone()
        return bool(row and row[0] == status)
    finally:
        cursor.close()
        connection.close()


# ---------------------------------------------------------------------------
# Contractor CRUD functions
# ---------------------------------------------------------------------------

def create_contractor(
    company_name: str,
    owner_name: str,
    license_no: str,
    district: str,
    specializations: str,
    contact_email: str,
    phone: str,
) -> dict[str, Any]:
    """Insert a new contractor and return the created record."""
    if not _DB_AVAILABLE:
        contractor = {
            "id": max((item["id"] for item in _MEM_CONTRACTORS), default=0) + 1,
            "company_name": company_name,
            "owner_name": owner_name,
            "license_no": license_no,
            "district": district,
            "specializations": specializations,
            "contact_email": contact_email,
            "phone": phone,
            "approval_status": "Pending",
            "performance_score": 0,
            "complaint_count": 0,
            "completed_projects": 0,
            "block_reason": None,
            "created_at": "just now",
        }
        _MEM_CONTRACTORS.append(contractor)
        return dict(contractor)
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO contractors
            (company_name, owner_name, license_no, district, specializations, contact_email, phone, approval_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
            """,
            (company_name, owner_name, license_no, district, specializations, contact_email, phone),
        )
        connection.commit()
        return {
            "id": cursor.lastrowid,
            "company_name": company_name,
            "owner_name": owner_name,
            "license_no": license_no,
            "district": district,
            "specializations": specializations,
            "contact_email": contact_email,
            "phone": phone,
            "approval_status": "Pending",
            "performance_score": 0,
            "complaint_count": 0,
            "completed_projects": 0,
        }
    finally:
        cursor.close()
        connection.close()


def load_contractors() -> list[dict[str, Any]]:
    """Return all contractors ordered by performance score descending."""
    if not _DB_AVAILABLE:
        return sorted((dict(item) for item in _MEM_CONTRACTORS), key=lambda item: (-item.get("performance_score", 0), -item.get("completed_projects", 0)))
    refresh_contractor_metrics()
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, company_name, owner_name, license_no, district, specializations, "
            "contact_email, phone, approval_status, performance_score, complaint_count, "
            "completed_projects, block_reason, created_at "
            "FROM contractors ORDER BY performance_score DESC, completed_projects DESC"
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def contractor_for_user(contact_email: str) -> dict[str, Any] | None:
    """Return contractor record for a given email, or None if not found/not active."""
    global _DB_AVAILABLE
    if not _DB_AVAILABLE:
        return next((dict(item) for item in _MEM_CONTRACTORS if str(item.get("contact_email", "")).casefold() == contact_email.casefold()), None)
    try:
        refresh_contractor_metrics()
        connection = connect()
    except Exception:
        _DB_AVAILABLE = False
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, company_name, owner_name, license_no, district, specializations, "
            "contact_email, phone, approval_status, performance_score, complaint_count, "
            "completed_projects, block_reason "
            "FROM contractors WHERE LOWER(contact_email) = LOWER(%s)",
            (contact_email,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def load_contractor_assignments(contractor_id: int) -> list[dict[str, Any]]:
    """Return all assignments for a given contractor with issue details."""
    if not _DB_AVAILABLE:
        issues = {item["id"]: item for item in _MEM_ISSUES}
        return [
            {
                **assignment,
                "issue_title": issues.get(assignment["issue_id"], {}).get("title", "Civic issue"),
                "issue_description": issues.get(assignment["issue_id"], {}).get("description", ""),
                "district": issues.get(assignment["issue_id"], {}).get("district", "Ranchi"),
                "block": issues.get(assignment["issue_id"], {}).get("block", ""),
                "category": issues.get(assignment["issue_id"], {}).get("category", "General"),
                "area": issues.get(assignment["issue_id"], {}).get("area", ""),
            }
            for assignment in _MEM_CONTRACTOR_ASSIGNMENTS
            if assignment["contractor_id"] == contractor_id
        ]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT ca.id, ca.issue_id, ca.contractor_id, ca.assigned_by, ca.status,
                     ca.completion_note, ca.progress_image_type, ca.assigned_at, ca.completed_at,
                   i.title AS issue_title, i.description AS issue_description,
                   i.district, i.block, i.category, i.area
            FROM contractor_assignments ca
            JOIN issues i ON i.id = ca.issue_id
            WHERE ca.contractor_id = %s
            ORDER BY ca.assigned_at DESC
            """,
            (contractor_id,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_all_contractor_assignments() -> list[dict[str, Any]]:
    """Return all contractor assignments with contractor and issue details (for admin)."""
    global _DB_AVAILABLE
    if not _DB_AVAILABLE:
        contractors = {item["id"]: item for item in _MEM_CONTRACTORS}
        issues = {item["id"]: item for item in _MEM_ISSUES}
        return [
            {
                **assignment,
                "issue_title": issues.get(assignment["issue_id"], {}).get("title", "Civic issue"),
                "district": issues.get(assignment["issue_id"], {}).get("district", "Ranchi"),
                "category": issues.get(assignment["issue_id"], {}).get("category", "General"),
                "company_name": contractors.get(assignment["contractor_id"], {}).get("company_name", "Contractor"),
                "contractor_email": contractors.get(assignment["contractor_id"], {}).get("contact_email", ""),
                "performance_score": contractors.get(assignment["contractor_id"], {}).get("performance_score", 0),
                "contractor_status": contractors.get(assignment["contractor_id"], {}).get("approval_status", "Pending"),
            }
            for assignment in _MEM_CONTRACTOR_ASSIGNMENTS
        ]
    try:
        connection = connect()
    except Exception:
        _DB_AVAILABLE = False
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT ca.id, ca.issue_id, ca.contractor_id, ca.assigned_by, ca.status,
                     ca.completion_note, ca.progress_image_type, ca.assigned_at, ca.completed_at,
                   i.title AS issue_title, i.district, i.category,
                   c.company_name, c.contact_email AS contractor_email,
                   c.performance_score, c.approval_status AS contractor_status
            FROM contractor_assignments ca
            JOIN issues i ON i.id = ca.issue_id
            JOIN contractors c ON c.id = ca.contractor_id
            ORDER BY ca.assigned_at DESC
            """
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def assign_issue_to_contractor(issue_id: int, contractor_id: int, assigned_by: str) -> bool:
    """Assign an issue to a contractor. Returns True on success."""
    if not _DB_AVAILABLE:
        if not any(item["id"] == contractor_id for item in _MEM_CONTRACTORS):
            return False
        assignment = next((item for item in _MEM_CONTRACTOR_ASSIGNMENTS if item["issue_id"] == issue_id), None)
        if assignment is None:
            _MEM_CONTRACTOR_ASSIGNMENTS.append({"id": max((item["id"] for item in _MEM_CONTRACTOR_ASSIGNMENTS), default=0) + 1, "issue_id": issue_id, "contractor_id": contractor_id, "assigned_by": assigned_by, "status": "Assigned", "completion_note": "", "progress_image_type": "", "progress_image_data": b"", "assigned_at": "just now", "completed_at": None})
        else:
            assignment.update({"contractor_id": contractor_id, "assigned_by": assigned_by, "status": "Assigned", "completed_at": None})
        return True
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO contractor_assignments (issue_id, contractor_id, assigned_by, status)
            VALUES (%s, %s, %s, 'Assigned')
            ON DUPLICATE KEY UPDATE
                contractor_id = VALUES(contractor_id),
                assigned_by = VALUES(assigned_by),
                status = 'Assigned',
                assigned_at = CURRENT_TIMESTAMP,
                completed_at = NULL
            """,
            (issue_id, contractor_id, assigned_by),
        )
        connection.commit()
        return True
    except Exception:
        return False
    finally:
        cursor.close()
        connection.close()


def update_contractor_assignment(assignment_id: int, status: str, note: str = "", progress_image_type: str = "", progress_image_data: bytes = b"") -> bool:
    """Update contractor assignment status and optionally set completion timestamp."""
    if not _DB_AVAILABLE:
        assignment = next((item for item in _MEM_CONTRACTOR_ASSIGNMENTS if item["id"] == assignment_id), None)
        if assignment is None:
            return False
        assignment.update({"status": status, "completion_note": note})
        if progress_image_type and progress_image_data:
            assignment.update({"progress_image_type": progress_image_type, "progress_image_data": progress_image_data})
        assignment["completed_at"] = "just now" if status == "Completed" else None
        if status == "Completed":
            contractor = next((item for item in _MEM_CONTRACTORS if item["id"] == assignment["contractor_id"]), None)
            if contractor:
                contractor["completed_projects"] = sum(1 for item in _MEM_CONTRACTOR_ASSIGNMENTS if item["contractor_id"] == contractor["id"] and item["status"] == "Completed")
                contractor["performance_score"] = contractor["completed_projects"] * 10 - contractor.get("complaint_count", 0) * 5
        return True
    connection = connect()
    try:
        cursor = connection.cursor()
        if progress_image_type and progress_image_data:
            image_columns = ", progress_image_type = %s, progress_image_data = %s"
            image_values = (progress_image_type, progress_image_data)
        else:
            image_columns = ""
            image_values = ()
        completed_column = ", completed_at = CURRENT_TIMESTAMP" if status == "Completed" else ""
        cursor.execute(
            f"UPDATE contractor_assignments SET status = %s, completion_note = %s{image_columns}{completed_column} WHERE id = %s",
            (status, note, *image_values, assignment_id),
        )
        connection.commit()
        updated = cursor.rowcount > 0
        if status == "Completed":
            cursor.execute("SELECT contractor_id FROM contractor_assignments WHERE id = %s", (assignment_id,))
            row = cursor.fetchone()
            if row:
                recalculate_contractor_score(row[0])
        return updated
    finally:
        cursor.close()
        connection.close()


def get_contractor_progress_image(assignment_id: int) -> tuple[str, bytes] | None:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT progress_image_type, progress_image_data FROM contractor_assignments WHERE id = %s", (assignment_id,))
        row = cursor.fetchone()
        if not row or row[1] is None:
            return None
        return row[0] or "application/octet-stream", bytes(row[1])
    finally:
        cursor.close()
        connection.close()


def create_contractor_complaint(
    contractor_id: int,
    issue_id: int,
    filed_by: str,
    complaint_type: str,
    description: str,
) -> dict[str, Any]:
    """File a quality complaint against a contractor."""
    if not _DB_AVAILABLE:
        complaint = {
            "id": len(_MEM_CONTRACTOR_COMPLAINTS) + 1,
            "contractor_id": contractor_id,
            "issue_id": issue_id,
            "filed_by": filed_by,
            "complaint_type": complaint_type,
            "description": description,
            "status": "Pending",
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": "just now",
        }
        _MEM_CONTRACTOR_COMPLAINTS.append(complaint)
        contractor = next((item for item in _MEM_CONTRACTORS if item["id"] == contractor_id), None)
        if contractor:
            contractor["complaint_count"] = sum(1 for item in _MEM_CONTRACTOR_COMPLAINTS if item["contractor_id"] == contractor_id and item["status"] == "Reviewed")
            contractor["performance_score"] = contractor.get("completed_projects", 0) * 10 - contractor["complaint_count"] * 5
        return dict(complaint)
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO contractor_complaints
            (contractor_id, issue_id, filed_by, complaint_type, description, status)
            VALUES (%s, %s, %s, %s, %s, 'Pending')
            """,
            (contractor_id, issue_id, filed_by, complaint_type, description),
        )
        complaint_id = cursor.lastrowid
        cursor.execute(
            "UPDATE contractors SET complaint_count = complaint_count + 1 WHERE id = %s",
            (contractor_id,),
        )
        connection.commit()
        recalculate_contractor_score(contractor_id)
        return {
            "id": complaint_id,
            "contractor_id": contractor_id,
            "issue_id": issue_id,
            "filed_by": filed_by,
            "complaint_type": complaint_type,
            "description": description,
            "status": "Pending",
        }
    finally:
        cursor.close()
        connection.close()


def load_contractor_complaints(contractor_id: int | None = None) -> list[dict[str, Any]]:
    """Return complaints, optionally filtered to a single contractor."""
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        base = (
            "SELECT cc.id, cc.contractor_id, cc.issue_id, cc.filed_by, cc.complaint_type, "
            "cc.description, cc.status, cc.reviewed_by, cc.reviewed_at, cc.created_at, "
            "c.company_name, i.title AS issue_title "
            "FROM contractor_complaints cc "
            "JOIN contractors c ON c.id = cc.contractor_id "
            "JOIN issues i ON i.id = cc.issue_id"
        )
        if contractor_id is not None:
            cursor.execute(base + " WHERE cc.contractor_id = %s ORDER BY cc.created_at DESC", (contractor_id,))
        else:
            cursor.execute(base + " ORDER BY cc.created_at DESC")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def review_contractor_complaint(complaint_id: int, status: str, reviewed_by: str) -> bool:
    """Mark a complaint as Reviewed or Dismissed by an admin."""
    if status not in {"Reviewed", "Dismissed"}:
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT contractor_id FROM contractor_complaints WHERE id = %s", (complaint_id,))
        complaint = cursor.fetchone()
        if not complaint:
            return False
        cursor.execute(
            "UPDATE contractor_complaints SET status = %s, reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP WHERE id = %s",
            (status, reviewed_by, complaint_id),
        )
        connection.commit()
        contractor_id = complaint[0]
    finally:
        cursor.close()
        connection.close()
    recalculate_contractor_score(contractor_id)
    return True


def update_contractor_status(contractor_id: int, status: str, reason: str = "") -> bool:
    """Block or activate a contractor."""
    if status not in {"Active", "Blocked", "Pending"}:
        return False
    if not _DB_AVAILABLE:
        contractor = next((item for item in _MEM_CONTRACTORS if item["id"] == contractor_id), None)
        if contractor is None:
            return False
        contractor["approval_status"] = status
        contractor["block_reason"] = reason if status == "Blocked" else None
        return True
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM contractors WHERE id = %s", (contractor_id,))
        if not cursor.fetchone():
            return False
        cursor.execute(
            "UPDATE contractors SET approval_status = %s, block_reason = %s WHERE id = %s",
            (status, reason if status == "Blocked" else None, contractor_id),
        )
        connection.commit()
        return True
    finally:
        cursor.close()
        connection.close()


def recalculate_contractor_score(contractor_id: int) -> None:
    """
    Recalculate and persist performance score.
    Score = completed_projects * 10 - confirmed_complaints * 5
    Also auto-blocks contractors with >= 3 confirmed (Reviewed) complaints.
    """
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT completed_projects FROM contractors WHERE id = %s", (contractor_id,)
        )
        row = cursor.fetchone()
        if not row:
            return
        completed = row["completed_projects"]
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM contractor_assignments WHERE contractor_id = %s AND status = 'Completed'",
            (contractor_id,),
        )
        completed = cursor.fetchone()["cnt"]
        cursor.execute(
            "UPDATE contractors SET completed_projects = %s WHERE id = %s",
            (completed, contractor_id),
        )
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM contractor_complaints WHERE contractor_id = %s AND status = 'Reviewed'",
            (contractor_id,),
        )
        confirmed_complaints = cursor.fetchone()["cnt"]
        score = completed * 10 - confirmed_complaints * 5
        cursor.execute(
            "UPDATE contractors SET performance_score = %s, complaint_count = %s WHERE id = %s",
            (score, confirmed_complaints, contractor_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def refresh_contractor_metrics() -> None:
    """Rebuild cached contractor totals from assignments and reviewed complaints."""
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE contractors c
            SET completed_projects = (
                    SELECT COUNT(*) FROM contractor_assignments ca
                    WHERE ca.contractor_id = c.id AND ca.status = 'Completed'
                ),
                complaint_count = (
                    SELECT COUNT(*) FROM contractor_complaints cc
                    WHERE cc.contractor_id = c.id AND cc.status = 'Reviewed'
                ),
                performance_score = (
                    (SELECT COUNT(*) FROM contractor_assignments ca
                     WHERE ca.contractor_id = c.id AND ca.status = 'Completed') * 10
                    - (SELECT COUNT(*) FROM contractor_complaints cc
                       WHERE cc.contractor_id = c.id AND cc.status = 'Reviewed') * 5
                )
            """
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def load_contractor_leaderboard() -> list[dict[str, Any]]:
    """Return one leaderboard entry per contractor identity, sorted by score."""
    refresh_contractor_metrics()
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, company_name, owner_name, license_no, district, specializations, "
            "performance_score, complaint_count, completed_projects, approval_status, block_reason "
            "FROM contractors "
            "ORDER BY CASE WHEN approval_status = 'Blocked' THEN 1 ELSE 0 END, "
            "performance_score DESC, completed_projects DESC"
        )
        contractors = cursor.fetchall()
        unique_contractors = {}
        for contractor in contractors:
            identity = (
                str(contractor.get("company_name") or "").strip().casefold(),
                str(contractor.get("owner_name") or "").strip().casefold(),
                str(contractor.get("district") or "").strip().casefold(),
            )
            existing = unique_contractors.get(identity)
            if existing is None or contractor["id"] > existing["id"]:
                unique_contractors[identity] = contractor
        return sorted(
            unique_contractors.values(),
            key=lambda contractor: (
                contractor.get("approval_status") == "Blocked",
                -(contractor.get("performance_score") or 0),
                -(contractor.get("completed_projects") or 0),
                contractor.get("company_name") or "",
            ),
        )
    finally:
        cursor.close()
        connection.close()


def update_offer_commitment(offer_id: int, status: str, note: str) -> bool:
    if not _DB_AVAILABLE:
        o = next((item for item in _MEM_OFFERS if item["id"] == offer_id), None)
        if o:
            o["status"] = status
            o["commitment_note"] = note
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE support_offers SET status = %s, commitment_note = %s WHERE id = %s", (status, note, offer_id))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def create_notification(recipient: str, message: str, related_type: str = "", related_id: int | None = None) -> None:
    if not _DB_AVAILABLE:
        nid = len(_MEM_NOTIFICATIONS) + 1
        _MEM_NOTIFICATIONS.append({"id": nid, "recipient": recipient, "message": message, "related_type": related_type, "related_id": related_id, "is_read": False, "created_at": "just now"})
        return
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO notifications (recipient, message, related_type, related_id) VALUES (%s, %s, %s, %s)", (recipient, message, related_type, related_id))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def load_notifications(recipient: str) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [n for n in _MEM_NOTIFICATIONS if n["recipient"].casefold() == recipient.casefold()]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, message, related_type, related_id, is_read, created_at FROM notifications WHERE recipient = %s ORDER BY created_at DESC, id DESC", (recipient,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def mark_notification_read(notification_id: int, recipient: str) -> bool:
    if not _DB_AVAILABLE:
        notification = next(
            (
                n for n in _MEM_NOTIFICATIONS
                if n["id"] == notification_id
                and n["recipient"].casefold() == recipient.casefold()
            ),
            None,
        )
        if notification:
            notification["is_read"] = True
            return True
        return False

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read = TRUE WHERE id = %s AND recipient = %s",
            (notification_id, recipient),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def mark_all_notifications_read(recipient: str) -> bool:
    if not _DB_AVAILABLE:
        changed = False
        for notification in _MEM_NOTIFICATIONS:
            if (
                notification["recipient"].casefold() == recipient.casefold()
                and not notification["is_read"]
            ):
                notification["is_read"] = True
                changed = True
        return changed

    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read = TRUE "
            "WHERE recipient = %s AND is_read = FALSE",
            (recipient,),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def load_messages(user: str) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return [m for m in _MEM_MESSAGES if m["sender"].casefold() == user.casefold() or m["recipient"].casefold() == user.casefold()]
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, sender, recipient, message, related_type, related_id, created_at FROM messages WHERE sender = %s OR recipient = %s ORDER BY created_at DESC, id DESC", (user, user))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def create_message(sender: str, recipient: str, message: str, related_type: str = "", related_id: int | None = None) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        mid = len(_MEM_MESSAGES) + 1
        rec = {"id": mid, "sender": sender, "recipient": recipient, "message": message, "related_type": related_type, "related_id": related_id, "created_at": "just now"}
        _MEM_MESSAGES.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO messages (sender, recipient, message, related_type, related_id) VALUES (%s, %s, %s, %s, %s)", (sender, recipient, message, related_type, related_id))
        connection.commit()
        return {"id": cursor.lastrowid, "sender": sender, "recipient": recipient, "message": message, "related_type": related_type, "related_id": related_id}
    finally:
        cursor.close()
        connection.close()


def add_issue_support(issue_id: int, user: str) -> tuple[bool, int]:
    if not _DB_AVAILABLE:
        return True, 1
    connection = connect()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO issue_supporters (issue_id, user_email) VALUES (%s, %s)", (issue_id, user))
        except IntegrityError:
            connection.rollback()
            cursor.execute("SELECT supporters FROM issues WHERE id = %s", (issue_id,))
            row = cursor.fetchone()
            return False, int(row[0]) if row else 0
        cursor.execute("UPDATE issues SET supporters = supporters + 1 WHERE id = %s", (issue_id,))
        cursor.execute("SELECT supporters FROM issues WHERE id = %s", (issue_id,))
        row = cursor.fetchone()
        connection.commit()
        return True, int(row[0]) if row else 0
    finally:
        cursor.close()
        connection.close()


def import_account(email: str, password_hash: str, salt: str) -> None:
    if not _DB_AVAILABLE:
        _MEM_ACCOUNTS[email.strip().lower()] = {"email": email.strip().lower(), "password_hash": password_hash, "salt": salt}
        return
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO accounts (email, password_hash, salt) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), salt = VALUES(salt)",
            (email, password_hash, salt),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def get_account(email: str) -> dict[str, str] | None:
    if not _DB_AVAILABLE:
        return _MEM_ACCOUNTS.get(email.strip().lower())
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT email, password_hash, salt FROM accounts WHERE email = %s", (email,))
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def create_account_record(email: str, password_hash: str, salt: str) -> bool:
    if not _DB_AVAILABLE:
        em = email.strip().lower()
        if em in _MEM_ACCOUNTS:
            return False
        _MEM_ACCOUNTS[em] = {"email": em, "password_hash": password_hash, "salt": salt}
        return True
    connection = connect()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO accounts (email, password_hash, salt) VALUES (%s, %s, %s)", (email, password_hash, salt))
            connection.commit()
            return True
        except IntegrityError:
            connection.rollback()
            return False
    finally:
        cursor.close()
        connection.close()


def create_session_record(user_email: str) -> str:
    session_id = secrets.token_hex(32)
    if not _DB_AVAILABLE:
        _MEM_SESSIONS[session_id] = user_email
        return session_id
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO sessions (session_id, user_email) VALUES (%s, %s)", (session_id, user_email))
        connection.commit()
        return session_id
    finally:
        cursor.close()
        connection.close()


def get_session_user(session_id: str) -> str | None:
    if not session_id:
        return None
    if not _DB_AVAILABLE:
        return _MEM_SESSIONS.get(session_id)
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT user_email FROM sessions WHERE session_id = %s", (session_id,))
        row = cursor.fetchone()
        return str(row[0]) if row else None
    finally:
        cursor.close()
        connection.close()


def delete_session_record(session_id: str) -> None:
    if not session_id:
        return
    if not _DB_AVAILABLE:
        _MEM_SESSIONS.pop(session_id, None)
        return
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def check_rate_limit(client_key: str, max_requests: int = 30, window_seconds: int = 60) -> bool:
    if not _DB_AVAILABLE:
        return True
    connection = connect()
    now = datetime.now(timezone.utc)
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT client_key, request_count, reset_at FROM rate_limits WHERE client_key = %s", (client_key,))
        row = cursor.fetchone()
        if not row:
            reset_at = (now + timedelta(seconds=window_seconds)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO rate_limits (client_key, request_count, reset_at) VALUES (%s, 1, %s)", (client_key, reset_at))
            connection.commit()
            return True

        reset_at_dt = row["reset_at"]
        if isinstance(reset_at_dt, str):
            reset_at_dt = datetime.strptime(reset_at_dt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        elif reset_at_dt.tzinfo is None:
            reset_at_dt = reset_at_dt.replace(tzinfo=timezone.utc)

        if now > reset_at_dt:
            new_reset_at = (now + timedelta(seconds=window_seconds)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE rate_limits SET request_count = 1, reset_at = %s WHERE client_key = %s", (new_reset_at, client_key))
            connection.commit()
            return True

        if row["request_count"] >= max_requests:
            return False

        cursor.execute("UPDATE rate_limits SET request_count = request_count + 1 WHERE client_key = %s", (client_key,))
        connection.commit()
        return True
    finally:
        cursor.close()
        connection.close()


def create_university_report(issue_id: int, university_id: int, submitted_by: str, title: str, summary: str, deliverables: str = "") -> dict[str, Any]:
    if not _DB_AVAILABLE:
        report = {
            "id": len(_MEM_UNIVERSITY_REPORTS) + 1,
            "issue_id": issue_id,
            "university_id": university_id,
            "submitted_by": submitted_by,
            "title": title,
            "summary": summary,
            "deliverables": deliverables,
            "created_at": "just now",
        }
        _MEM_UNIVERSITY_REPORTS.append(report)
        return report
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO university_reports (issue_id, university_id, submitted_by, title, summary, deliverables)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (issue_id, university_id, submitted_by, title, summary, deliverables),
        )
        report_id = cursor.lastrowid
        connection.commit()
        return {
            "id": report_id,
            "issue_id": issue_id,
            "university_id": university_id,
            "submitted_by": submitted_by,
            "title": title,
            "summary": summary,
            "deliverables": deliverables,
        }
    finally:
        cursor.close()
        connection.close()


def load_university_reports(issue_id: int | None = None) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        from community import ISSUES
        reports = []
        universities = {university["id"]: university for university in _MEM_UNIVERSITIES}
        issues = {issue["id"]: issue for issue in ISSUES}
        for report in _MEM_UNIVERSITY_REPORTS:
            if issue_id is not None and report.get("issue_id") != issue_id:
                continue
            issue = issues.get(report.get("issue_id"), {})
            university = universities.get(report.get("university_id"), {})
            reports.append({
                **report,
                "issue_title": issue.get("title", "Civic challenge"),
                "issue_district": issue.get("district", "Ranchi"),
                "issue_category": issue.get("category", "General"),
                "university_name": university.get("name", "University"),
            })
        return reports
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT r.id, r.issue_id, r.university_id, r.submitted_by, r.title, r.summary, r.deliverables, r.created_at,
                   i.title AS issue_title, i.district AS issue_district, i.category AS issue_category,
                   u.name AS university_name
            FROM university_reports r
            JOIN issues i ON i.id = r.issue_id
            JOIN universities u ON u.id = r.university_id
        """
        params = []
        if issue_id:
            query += " WHERE r.issue_id = %s"
            params.append(issue_id)
        query += " ORDER BY r.created_at DESC"
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_university_assignment_responses() -> list[dict[str, Any]]:
    global _DB_AVAILABLE
    if not _DB_AVAILABLE:
        universities = {item["id"]: item for item in _MEM_UNIVERSITIES}
        issues = {item["id"]: item for item in _MEM_ISSUES}
        responses = []
        for assignment in _MEM_ASSIGNMENTS.values():
            university = universities.get(assignment.get("university_id"), {})
            issue = issues.get(assignment.get("issue_id"), {})
            responses.append({
                "issue_id": assignment.get("issue_id"),
                "university_id": assignment.get("university_id"),
                "status": assignment.get("status", "Assigned"),
                "response_reason": assignment.get("response_reason", ""),
                "assigned_at": "just now",
                "issue_title": issue.get("title", "Civic challenge"),
                "issue_district": issue.get("district", "Ranchi"),
                "issue_category": issue.get("category", "General"),
                "university_name": university.get("name", "University"),
                "university_email": university.get("contact_email", ""),
            })
        return responses
    try:
        connection = connect()
    except Exception:
        _DB_AVAILABLE = False
        return load_university_assignment_responses()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT a.issue_id, a.university_id, a.status, a.response_reason, a.assigned_at,
                   i.title AS issue_title, i.district AS issue_district, i.category AS issue_category,
                   u.name AS university_name, u.contact_email AS university_email
            FROM issue_assignments a
            JOIN issues i ON i.id = a.issue_id
            JOIN universities u ON u.id = a.university_id
            ORDER BY a.assigned_at DESC
            """
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


