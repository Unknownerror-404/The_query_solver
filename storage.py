"""MySQL persistence for the civic-map application."""

from __future__ import annotations

import os
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
                contact_email VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_assignments (
                issue_id INT PRIMARY KEY,
                university_id INT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Assigned',
                assigned_by VARCHAR(255) NOT NULL,
                assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _issue(row: tuple[Any, ...]) -> dict[str, Any]:
    keys = ("id", "title", "category", "area", "district", "block", "lat", "lng", "description", "supporters", "age", "proof_id", "proof_status", "proof_message", "moderation_status", "moderation_reason", "moderated_by")
    issue = {key: value for key, value in zip(keys, row) if value is not None}
    for coordinate in ("lat", "lng"):
        if isinstance(issue.get(coordinate), Decimal):
            issue[coordinate] = float(issue[coordinate])
    return issue


def load_issues() -> list[dict[str, Any]]:
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, title, category, area, district, block, latitude, longitude, description, supporters, age, proof_id, proof_status, proof_message, moderation_status, moderation_reason, moderated_by FROM issues ORDER BY id")
        return [_issue(row) for row in cursor.fetchall()]
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
            (title, category, area, district, block, latitude, longitude, description, supporters, age, proof_id, proof_type, proof_data, proof_status, proof_message, moderation_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 'just now', %s, %s, %s, %s, %s, 'Pending')
            """,
            (issue["title"], issue["category"], issue.get("area", ""), issue.get("district", "Ranchi"), issue.get("block", ""), issue["lat"], issue["lng"], issue.get("description", ""), issue.get("proof_id"), issue.get("_proof_type"), issue.get("_proof_data"), issue.get("proof_status"), issue.get("proof_message")),
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
        cursor.execute("SELECT id, name, district, domains, contact_email FROM universities ORDER BY name")
        return cursor.fetchall()
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
        cursor.execute("SELECT issue_id, university_id, status, assigned_by FROM issue_assignments")
        return {row["issue_id"]: row for row in cursor.fetchall()}
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
        cursor.execute("INSERT IGNORE INTO accounts (email, password_hash, salt) VALUES (%s, %s, %s)", (email, password_hash, salt))
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
