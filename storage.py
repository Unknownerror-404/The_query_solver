"""MySQL persistence for the civic-map application."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

import mysql.connector
from mysql.connector import Error, IntegrityError

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
_MEM_PROPOSALS: list[dict[str, Any]] = []
_MEM_RATE_LIMITS: dict[str, Any] = {}


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
    except Exception:
        _DB_AVAILABLE = False
        return
    _DB_AVAILABLE = True
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id INT PRIMARY KEY AUTO_INCREMENT,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(100) NOT NULL,
                area VARCHAR(255) NOT NULL,
                district VARCHAR(100) NOT NULL DEFAULT 'Ranchi',
                block VARCHAR(100) NOT NULL DEFAULT '',
                latitude DECIMAL(10, 7) NOT NULL,
                longitude DECIMAL(10, 7) NOT NULL,
                description TEXT NOT NULL,
                supporters INT NOT NULL DEFAULT 0,
                age VARCHAR(50) NOT NULL,
                proof_id VARCHAR(100),
                proof_type VARCHAR(30),
                proof_data LONGBLOB,
                proof_status VARCHAR(30),
                proof_message TEXT,
                moderation_status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                moderation_reason TEXT,
                moderated_by VARCHAR(255),
                 reporter VARCHAR(255),
                     created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for statement in (
            "ALTER TABLE issues ADD COLUMN district VARCHAR(100) NOT NULL DEFAULT 'Ranchi'",
            "ALTER TABLE issues ADD COLUMN block VARCHAR(100) NOT NULL DEFAULT ''",
            "ALTER TABLE issues ADD COLUMN proof_type VARCHAR(30)",
            "ALTER TABLE issues ADD COLUMN proof_data LONGBLOB",
            "ALTER TABLE issues ADD COLUMN moderation_status VARCHAR(30) NOT NULL DEFAULT 'Pending'",
            "ALTER TABLE issues ADD COLUMN moderation_reason TEXT",
            "ALTER TABLE issues ADD COLUMN moderated_by VARCHAR(255)",
                    "ALTER TABLE issues ADD COLUMN reporter VARCHAR(255)",
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
            CREATE TABLE IF NOT EXISTS universities (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                district VARCHAR(100) NOT NULL,
                domains TEXT NOT NULL,
                departments TEXT,
                laboratories TEXT,
                incubation_facilities TEXT,
                contact_email VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for statement in (
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
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS support_offers (
                id INT PRIMARY KEY AUTO_INCREMENT,
                issue_id INT NOT NULL,
                partner_id INT NOT NULL,
                support_type VARCHAR(50) NOT NULL,
                details TEXT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Offered',
                commitment_note TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
                FOREIGN KEY (partner_id) REFERENCES industry_partners(id) ON DELETE CASCADE
            )
            """
        )
        try:
            cursor.execute("ALTER TABLE support_offers ADD COLUMN commitment_note TEXT")
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
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _issue(row: tuple[Any, ...]) -> dict[str, Any]:
    keys = ("id", "title", "category", "area", "district", "block", "lat", "lng", "description", "supporters", "age", "proof_id", "proof_status", "proof_message", "moderation_status", "moderation_reason", "moderated_by", "reporter")
    issue = {key: value for key, value in zip(keys, row) if value is not None}
    for coordinate in ("lat", "lng"):
        if isinstance(issue.get(coordinate), Decimal):
            issue[coordinate] = float(issue[coordinate])
    return issue


def load_issues() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return list(_MEM_ISSUES)
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, title, category, area, district, block, latitude, longitude, description, supporters, age, proof_id, proof_status, proof_message, moderation_status, moderation_reason, moderated_by, reporter FROM issues ORDER BY id")
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
        cursor.execute("SELECT i.id, i.title, i.description, i.district, i.block, i.category, i.moderation_status, i.moderation_reason, a.status AS assignment_status, u.name AS university_name, t.id AS team_id, t.name AS team_name, t.status AS team_status FROM issues i LEFT JOIN issue_assignments a ON a.issue_id = i.id LEFT JOIN universities u ON u.id = a.university_id LEFT JOIN project_teams t ON t.issue_id = i.id AND t.university_id = a.university_id WHERE LOWER(i.reporter) = LOWER(%s) ORDER BY i.id DESC", (reporter,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def insert_issue(issue: dict[str, Any]) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        iid = max((i["id"] for i in _MEM_ISSUES), default=0) + 1
        saved = dict(issue)
        saved.update({"id": iid, "supporters": 1, "age": "just now", "moderation_status": "Pending"})
        _MEM_ISSUES.append(saved)
        return saved
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO issues
            (title, category, area, district, block, latitude, longitude, description, supporters, age, proof_id, proof_type, proof_data, proof_status, proof_message, moderation_status, reporter)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 'just now', %s, %s, %s, %s, %s, 'Pending', %s)
            """,
                (issue["title"], issue["category"], issue.get("area", ""), issue.get("district", "Ranchi"), issue.get("block", ""), issue["lat"], issue["lng"], issue.get("description", ""), issue.get("proof_id"), issue.get("_proof_type"), issue.get("_proof_data"), issue.get("proof_status"), issue.get("proof_message"), issue.get("reporter")),
        )
        connection.commit()
        saved = dict(issue)
        saved.pop("_proof_type", None)
        saved.pop("_proof_data", None)
        saved.update({"id": cursor.lastrowid, "supporters": 1, "age": "just now"})
        return saved
    finally:
        cursor.close()
        connection.close()


def update_issue(issue: dict[str, Any]) -> None:
    if not _DB_AVAILABLE:
        existing = next((i for i in _MEM_ISSUES if i["id"] == issue.get("id")), None)
        if existing:
            existing.update(issue)
        return
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE issues SET supporters = %s, proof_id = %s, proof_type = %s, proof_data = %s, proof_status = %s, proof_message = %s WHERE id = %s",
            (issue.get("supporters", 0), issue.get("proof_id"), issue.get("_proof_type"), issue.get("_proof_data"), issue.get("proof_status"), issue.get("proof_message"), issue["id"]),
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
        cursor.execute("SELECT id, name, district, domains, departments, laboratories, incubation_facilities, contact_email FROM universities ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def update_university(university_id: int, name: str, district: str, domains: str, departments: str, laboratories: str, incubation_facilities: str, contact_email: str) -> bool:
    if not _DB_AVAILABLE:
        u = next((item for item in _MEM_UNIVERSITIES if item["id"] == university_id), None)
        if u:
            u.update({"name": name, "district": district, "domains": domains, "departments": departments, "laboratories": laboratories, "incubation_facilities": incubation_facilities, "contact_email": contact_email})
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE universities SET name = %s, district = %s, domains = %s, departments = %s, laboratories = %s, incubation_facilities = %s, contact_email = %s WHERE id = %s",
            (name, district, domains, departments, laboratories, incubation_facilities, contact_email, university_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def create_university(name: str, district: str, domains: str, departments: str, laboratories: str, incubation_facilities: str, contact_email: str) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        uid = max((u["id"] for u in _MEM_UNIVERSITIES), default=0) + 1
        rec = {"id": uid, "name": name, "district": district, "domains": domains, "departments": departments, "laboratories": laboratories, "incubation_facilities": incubation_facilities, "contact_email": contact_email}
        _MEM_UNIVERSITIES.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO universities (name, district, domains, departments, laboratories, incubation_facilities, contact_email) VALUES (%s, %s, %s, %s, %s, %s, %s)", (name, district, domains, departments, laboratories, incubation_facilities, contact_email))
        connection.commit()
        return {"id": cursor.lastrowid, "name": name, "district": district, "domains": domains, "departments": departments, "laboratories": laboratories, "incubation_facilities": incubation_facilities, "contact_email": contact_email}
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
        return list(_MEM_TEAMS)
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, issue_id, university_id, name, faculty_mentor, status FROM project_teams ORDER BY id")
        teams = cursor.fetchall()
        for team in teams:
            cursor.execute("SELECT student_email FROM team_members WHERE team_id = %s ORDER BY student_email", (team["id"],))
            team["members"] = [row["student_email"] for row in cursor.fetchall()]
        return teams
    finally:
        cursor.close()
        connection.close()


def create_team(issue_id: int, university_id: int, name: str, faculty_mentor: str, members: list[str]) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        tid = max((t["id"] for t in _MEM_TEAMS), default=0) + 1
        rec = {"id": tid, "issue_id": issue_id, "university_id": university_id, "name": name, "faculty_mentor": faculty_mentor, "status": "Forming", "members": members, "ip_outcome": "", "startup_outcome": "", "impact_summary": ""}
        _MEM_TEAMS.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO project_teams (issue_id, university_id, name, faculty_mentor) VALUES (%s, %s, %s, %s)", (issue_id, university_id, name, faculty_mentor))
        team_id = cursor.lastrowid
        cursor.executemany("INSERT INTO team_members (team_id, student_email) VALUES (%s, %s)", [(team_id, member) for member in members])
        connection.commit()
        return {"id": team_id, "issue_id": issue_id, "university_id": university_id, "name": name, "faculty_mentor": faculty_mentor, "status": "Forming", "members": members}
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
        rec = {"id": mid, "team_id": team_id, "title": title, "due_date": due_date, "status": "Pending", "deliverable": deliverable, "testing_result": ""}
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
        return None
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


def update_team_outcomes(team_id: int, ip_outcome: str, startup_outcome: str, impact_summary: str) -> bool:
    if not _DB_AVAILABLE:
        t = next((item for item in _MEM_TEAMS if item["id"] == team_id), None)
        if t:
            t["ip_outcome"] = ip_outcome
            t["startup_outcome"] = startup_outcome
            t["impact_summary"] = impact_summary
            return True
        return False
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE project_teams SET ip_outcome = %s, startup_outcome = %s, impact_summary = %s WHERE id = %s", (ip_outcome, startup_outcome, impact_summary, team_id))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()


def load_industry_partners() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        return list(_MEM_INDUSTRY)
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, partner_type, district, domains, contact_email FROM industry_partners ORDER BY name")
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
        cursor.execute("SELECT o.id, o.issue_id, o.partner_id, o.support_type, o.details, o.status, o.commitment_note, i.title, i.district, i.block, p.name AS partner_name FROM support_offers o JOIN industry_partners p ON p.id = o.partner_id JOIN issues i ON i.id = o.issue_id WHERE LOWER(p.contact_email) = LOWER(%s) ORDER BY o.id DESC", (contact_email,))
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
        cursor.execute("SELECT o.id, o.issue_id, o.partner_id, o.support_type, o.details, o.status, o.commitment_note, o.created_at, i.title, i.district, i.block, i.category, p.name AS partner_name, p.partner_type, p.contact_email AS partner_email FROM support_offers o JOIN industry_partners p ON p.id = o.partner_id JOIN issues i ON i.id = o.issue_id ORDER BY o.id DESC")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_university_issue_offers(contact_email: str) -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        from community import ISSUES
        uni = next((u for u in _MEM_UNIVERSITIES if str(u.get("contact_email", "")).casefold() == contact_email.casefold()), None)
        if not uni:
            return []
        uni_assigned_issue_ids = {a["issue_id"] for a in _MEM_ASSIGNMENTS.values() if a["university_id"] == uni["id"]}
        results = []
        for o in _MEM_OFFERS:
            if o["issue_id"] in uni_assigned_issue_ids:
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
                    "issue_title": iss.get("title", f"Challenge #{o['issue_id']}"),
                    "district": iss.get("district", "Jharkhand"),
                    "category": iss.get("category", "General"),
                    "partner_name": p.get("name", "Industry Partner"),
                    "partner_type": p.get("partner_type", "Industry"),
                    "partner_email": p.get("contact_email", ""),
                })
        return results
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT o.id, o.issue_id, o.partner_id, o.support_type, o.details, o.status, o.commitment_note, o.created_at,
                   i.title AS issue_title, i.district, i.category, p.name AS partner_name, p.partner_type, p.contact_email AS partner_email
            FROM support_offers o
            JOIN issues i ON i.id = o.issue_id
            JOIN issue_assignments a ON a.issue_id = i.id
            JOIN universities u ON u.id = a.university_id
            JOIN industry_partners p ON p.id = o.partner_id
            WHERE LOWER(u.contact_email) = LOWER(%s)
            ORDER BY o.id DESC
            """,
            (contact_email,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_all_teams_with_details() -> list[dict[str, Any]]:
    if not _DB_AVAILABLE:
        from community import ISSUES
        for t in _MEM_TEAMS:
            uni = next((u for u in _MEM_UNIVERSITIES if u["id"] == t["university_id"]), {})
            iss = next((i for i in ISSUES if i.get("id") == t["issue_id"]), {})
            t["university_name"] = uni.get("name", "University")
            t["university_district"] = uni.get("district", "Jharkhand")
            t["issue_title"] = iss.get("title", f"Challenge #{t['issue_id']}")
            t["issue_category"] = iss.get("category", "General")
            t["issue_district"] = iss.get("district", "Jharkhand")
            t["issue_block"] = iss.get("block", "")
        return list(_MEM_TEAMS)
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT t.id, t.issue_id, t.university_id, t.name, t.faculty_mentor, t.status, t.ip_outcome, t.startup_outcome, t.impact_summary, t.created_at,
                   u.name AS university_name, u.district AS university_district,
                   i.title AS issue_title, i.category AS issue_category, i.district AS issue_district, i.block AS issue_block
            FROM project_teams t
            JOIN universities u ON u.id = t.university_id
            JOIN issues i ON i.id = t.issue_id
            ORDER BY t.id DESC
            """
        )
        teams = cursor.fetchall()
        for team in teams:
            cursor.execute("SELECT student_email FROM team_members WHERE team_id = %s ORDER BY student_email", (team["id"],))
            team["members"] = [row["student_email"] for row in cursor.fetchall()]
        return teams
    finally:
        cursor.close()
        connection.close()


def create_support_offer(issue_id: int, partner_id: int, support_type: str, details: str) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        oid = max((o["id"] for o in _MEM_OFFERS), default=0) + 1
        rec = {"id": oid, "issue_id": issue_id, "partner_id": partner_id, "support_type": support_type, "details": details, "status": "Offered", "commitment_note": ""}
        _MEM_OFFERS.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO support_offers (issue_id, partner_id, support_type, details) VALUES (%s, %s, %s, %s)", (issue_id, partner_id, support_type, details))
        connection.commit()
        return {"id": cursor.lastrowid, "issue_id": issue_id, "partner_id": partner_id, "support_type": support_type, "details": details, "status": "Offered"}
    finally:
        cursor.close()
        connection.close()


def create_industry_partner(name: str, partner_type: str, district: str, domains: str, contact_email: str) -> dict[str, Any]:
    if not _DB_AVAILABLE:
        pid = max((p["id"] for p in _MEM_INDUSTRY), default=0) + 1
        rec = {"id": pid, "name": name, "partner_type": partner_type, "district": district, "domains": domains, "contact_email": contact_email}
        _MEM_INDUSTRY.append(rec)
        return rec
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO industry_partners (name, partner_type, district, domains, contact_email) VALUES (%s, %s, %s, %s, %s)", (name, partner_type, district, domains, contact_email))
        connection.commit()
        return {"id": cursor.lastrowid, "name": name, "partner_type": partner_type, "district": district, "domains": domains, "contact_email": contact_email}
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
        cursor.execute("INSERT IGNORE INTO accounts (email, password_hash, salt) VALUES (%s, %s, %s)", (email, password_hash, salt))
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

