"""CSV-backed local accounts for the civic map.

The CSV stores email addresses and salted PBKDF2 password hashes, never plain
text passwords. It is created automatically beside this file on first run.
For production, use a database and keep the account file outside source
control. The included demo account is intended only for local development.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import secrets
from pathlib import Path

try:
    from .storage import create_account_record, get_account, import_account, initialise
except ImportError:
    from storage import create_account_record, get_account, import_account, initialise

ACCOUNTS_FILE = Path(__file__).with_name("accounts.csv")
ADMIN_EMAILS = {"admin@jharkhand.gov.in"}
PROFESSIONAL_DEMO_EMAIL = "engineer@example.gov"
VERIFIED_PROFESSIONALS = {
    PROFESSIONAL_DEMO_EMAIL: {
        "name": "Arun Mehta",
        "organization": "Bengaluru Urban Transport Authority",
        "affiliation": "Government transport professional",
        "verification": "Verified by organization",
    }
}
DEFAULT_ACCOUNTS = {
    "citizen@example.com": "map123",
    "engineer@example.gov": "gov12345",
    "admin@jharkhand.gov.in": "gov12345",
    "innovation@bitmesra.ac.in": "map12345",
    "innovation@cuj.ac.in": "map12345",
    "innovation@nitjsr.ac.in": "map12345",
    "partner@jin.example": "partner123",
    "connect@alf.example": "partner123",
    "innovation@etm.example": "partner123",
}
CSV_FIELDS = ("email", "password_hash", "salt")
HASH_ITERATIONS = 310_000


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    used_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(used_salt), HASH_ITERATIONS)
    return digest.hex(), used_salt


def _ensure_accounts_file() -> None:
    existing_emails = set()
    if ACCOUNTS_FILE.exists():
        with ACCOUNTS_FILE.open(newline="", encoding="utf-8") as file:
            existing_emails = {account.get("email", "").strip().lower() for account in csv.DictReader(file)}
    else:
        with ACCOUNTS_FILE.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()

    missing = {email: pwd for email, pwd in DEFAULT_ACCOUNTS.items() if email.lower() not in existing_emails}
    if missing:
        with ACCOUNTS_FILE.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            for email, pwd in missing.items():
                p_hash, p_salt = _hash_password(pwd)
                writer.writerow({"email": email, "password_hash": p_hash, "salt": p_salt})


def _ensure_accounts() -> None:
    try:
        initialise()
    except Exception:
        pass
    _ensure_accounts_file()
    with ACCOUNTS_FILE.open(newline="", encoding="utf-8") as file:
        for account in csv.DictReader(file):
            import_account(account["email"].strip().lower(), account["password_hash"], account["salt"])


def authenticate(email: str, password: str) -> bool:
    _ensure_accounts()
    email = email.strip().lower()
    account = get_account(email)
    if account is None:
        return False
    password_hash, _ = _hash_password(password, account["salt"])
    return hmac.compare_digest(password_hash, account["password_hash"])


def create_account(email: str, password: str) -> tuple[bool, str]:
    _ensure_accounts()
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Enter a valid email address."
    if len(password) < 8:
        return False, "Password must contain at least 8 characters."
    password_hash, salt = _hash_password(password)
    if not create_account_record(email, password_hash, salt):
        return False, "An account with that email already exists."
    return True, "Account created."


def professional_profile(email: str) -> dict | None:
    return VERIFIED_PROFESSIONALS.get(email.strip().lower())


def is_admin(email: str) -> bool:
    return email.strip().lower() in ADMIN_EMAILS


_ensure_accounts()
