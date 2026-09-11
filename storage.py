"""MySQL persistence for the civic-map application."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error, IntegrityError


load_dotenv(Path(__file__).resolve().with_name(".env"))


MYSQL_CONFIG = {
    "host": os.getenv("CIVIC_MAP_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("CIVIC_MAP_DB_PORT", "3306")),
    "user": os.getenv("CIVIC_MAP_DB_USER", "root"),
    "password": os.getenv("CIVIC_MAP_DB_PASSWORD", ""),
    "database": os.getenv("CIVIC_MAP_DB_NAME", "sih26"),
}


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
    ensure_database()
    connection = connect()
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
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _issue(row: tuple[Any, ...]) -> dict[str, Any]:
    keys = ("id", "title", "category", "area", "district", "block", "lat", "lng", "description", "supporters", "age", "proof_id", "proof_status", "proof_message", "predicted_category", "category_confidence", "priority_score", "priority_label", "matching_explanation", "moderation_status", "moderation_reason", "moderated_by", "reporter")
    issue = {key: value for key, value in zip(keys, row) if value is not None}
    for coordinate in ("lat", "lng"):
        if isinstance(issue.get(coordinate), Decimal):
            issue[coordinate] = float(issue[coordinate])
    if isinstance(issue.get("category_confidence"), Decimal):
        issue["category_confidence"] = float(issue["category_confidence"])
    return issue


def load_issues() -> list[dict[str, Any]]:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, title, category, area, district, block, latitude, longitude, description, supporters, age, proof_id, proof_status, proof_message, predicted_category, category_confidence, priority_score, priority_label, matching_explanation, moderation_status, moderation_reason, moderated_by, reporter FROM issues ORDER BY id")
        return [_issue(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def load_user_issues(reporter: str) -> list[dict[str, Any]]:
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT i.id, i.title, i.description, i.district, i.block, i.category, i.moderation_status, i.moderation_reason, a.status AS assignment_status, u.name AS university_name, t.id AS team_id, t.name AS team_name, t.status AS team_status, ca.id AS contractor_assignment_id, ca.contractor_id, c.company_name AS contractor_name, ca.status AS contractor_assignment_status, ca.completion_note AS contractor_completion_note, ca.progress_image_type AS contractor_progress_image_type FROM issues i LEFT JOIN issue_assignments a ON a.issue_id = i.id LEFT JOIN universities u ON u.id = a.university_id LEFT JOIN project_teams t ON t.issue_id = i.id AND t.university_id = a.university_id LEFT JOIN contractor_assignments ca ON ca.issue_id = i.id LEFT JOIN contractors c ON c.id = ca.contractor_id WHERE LOWER(i.reporter) = LOWER(%s) ORDER BY i.id DESC", (reporter,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

def insert_issue(issue: dict[str, Any]) -> dict[str, Any]:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO issues
            (title, category, ai_category, ai_confidence, category_mismatch, ai_tags, tagging_model, area, district, block, latitude, longitude, description, supporters, age, proof_id, proof_type, proof_data, proof_status, proof_message, predicted_category, priority_score, priority_label, matching_explanation, moderation_status, reporter)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 'just now', %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending', %s)
            """,
            (
                issue["title"],
                issue["category"],
                issue.get("problem_type"),
                issue.get("tag_confidence"),
                issue.get("category_mismatch", False),
                issue.get("problem_tags"),
                issue.get("tag_version"),
                issue.get("area", ""),
                issue.get("district", "Ranchi"),
                issue.get("block", ""),
                issue["lat"],
                issue["lng"],
                issue.get("description", ""),
                issue.get("proof_id"),
                issue.get("_proof_type"),
                issue.get("_proof_data"),
                issue.get("proof_status"),
                issue.get("proof_message"),
                issue.get("predicted_category"),
                issue.get("priority_score"),
                issue.get("priority_label"),
                issue.get("matching_explanation"),
                issue.get("reporter"),
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
        saved.pop("_proof_type", None)
        saved.pop("_proof_data", None)
        saved.update({
            "id": issue_id,
            "supporters": 1,
            "age": "just now",
        })
        return saved
    finally:
        cursor.close()
        connection.close()


def update_issue(issue: dict[str, Any]) -> None:
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
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT issue_id, university_id, status, response_reason, assigned_by FROM issue_assignments")
        return {row["issue_id"]: row for row in cursor.fetchall()}
    finally:
        cursor.close()
        connection.close()


def load_university_assignments(contact_email: str) -> list[dict[str, Any]]:
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
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, team_id, title, due_date, status, deliverable, testing_result, completed_at, deliverable_type FROM milestones WHERE team_id = %s ORDER BY due_date, id", (team_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_milestone_deliverable(milestone_id: int) -> tuple[str, bytes] | None:
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
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, team_id, status, changed_by, note, changed_at FROM project_status_history WHERE team_id = %s ORDER BY changed_at DESC, id DESC", (team_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_dashboard_metrics() -> dict[str, Any]:
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
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, name, partner_type, district, domains, contact_email, approval_status FROM industry_partners ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_partner_offers(contact_email: str) -> list[dict[str, Any]]:
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


def create_support_offer(
    issue_id: int,
    partner_id: int,
    support_type: str,
    details: str,
    funding_amount: int = 0,
    resources: str = "",
    timeline: str = "",
) -> dict[str, Any]:
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


def create_industry_partner(name: str, partner_type: str, district: str, domains: str, contact_email: str) -> dict[str, Any]:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO industry_partners (name, partner_type, district, domains, contact_email, approval_status) VALUES (%s, %s, %s, %s, %s, 'Pending')", (name, partner_type, district, domains, contact_email))
        connection.commit()
        return {"id": cursor.lastrowid, "name": name, "partner_type": partner_type, "district": district, "domains": domains, "contact_email": contact_email, "approval_status": "Pending"}
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
    refresh_contractor_metrics()
    connection = connect()
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
    connection = connect()
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
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO notifications (recipient, message, related_type, related_id) VALUES (%s, %s, %s, %s)", (recipient, message, related_type, related_id))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def load_notifications(recipient: str) -> list[dict[str, Any]]:
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, message, related_type, related_id, is_read, created_at FROM notifications WHERE recipient = %s ORDER BY created_at DESC, id DESC", (recipient,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def load_messages(user: str) -> list[dict[str, Any]]:
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, sender, recipient, message, related_type, related_id, created_at FROM messages WHERE sender = %s OR recipient = %s ORDER BY created_at DESC, id DESC", (user, user))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def create_message(sender: str, recipient: str, message: str, related_type: str = "", related_id: int | None = None) -> dict[str, Any]:
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
    connection = connect()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT email, password_hash, salt FROM accounts WHERE email = %s", (email,))
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def create_account_record(email: str, password_hash: str, salt: str) -> bool:
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
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def check_rate_limit(client_key: str, max_requests: int = 30, window_seconds: int = 60) -> bool:
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
    connection = connect()
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


