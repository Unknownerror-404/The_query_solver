"""Database backup utility for the Societal Innovation Collaboration Portal.

Run with: python backup_db.py
Creates timestamped SQL dumps in a backups/ directory.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = BASE_DIR / "backups"

DB_HOST = os.getenv("CIVIC_MAP_DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("CIVIC_MAP_DB_PORT", "3306")
DB_USER = os.getenv("CIVIC_MAP_DB_USER", "root")
DB_PASS = os.getenv("CIVIC_MAP_DB_PASSWORD", "Mi123456#")
DB_NAME = os.getenv("CIVIC_MAP_DB_NAME", "sih26")


def backup_database() -> Path | None:
    """Export MySQL database schema and data into a SQL file."""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"{DB_NAME}_backup_{timestamp}.sql"

    cmd = [
        "mysqldump",
        f"-h{DB_HOST}",
        f"-P{DB_PORT}",
        f"-u{DB_USER}",
        f"-p{DB_PASS}",
        "--databases",
        DB_NAME,
    ]

    try:
        with backup_file.open("w", encoding="utf-8") as out:
            result = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            print(f"[OK] Database backup created at: {backup_file}")
            return backup_file
        else:
            print(f"[ERROR] mysqldump failed: {result.stderr}")
            if backup_file.exists():
                backup_file.unlink()
            return None
    except FileNotFoundError:
        print("[WARNING] mysqldump CLI tool not found in PATH. Using fallback Python export.")
        return python_fallback_backup(backup_file)


def python_fallback_backup(output_file: Path) -> Path | None:
    """Fallback database schema/table dumper using mysql-connector."""
    try:
        import mysql.connector

        connection = mysql.connector.connect(
            host=DB_HOST, port=int(DB_PORT), user=DB_USER, password=DB_PASS, database=DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

        with output_file.open("w", encoding="utf-8") as f:
            f.write(f"-- Backup of database `{DB_NAME}`\n")
            f.write(f"-- Generated on {datetime.now().isoformat()}\n\n")

            for table in tables:
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_stmt = cursor.fetchone()[1]
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n{create_stmt};\n\n")

                cursor.execute(f"SELECT * FROM `{table}`")
                rows = cursor.fetchall()
                for row in rows:
                    vals = ", ".join(repr(v) for v in row)
                    f.write(f"INSERT INTO `{table}` VALUES ({vals});\n")
                f.write("\n")

        cursor.close()
        connection.close()
        print(f"[OK] Python fallback backup created at: {output_file}")
        return output_file
    except Exception as err:
        print(f"[ERROR] Python fallback backup failed: {err}")
        return None


if __name__ == "__main__":
    backup_database()
