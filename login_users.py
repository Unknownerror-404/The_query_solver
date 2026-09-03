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
DEMO_EMAIL = "citizen@example.com"
DEMO_PASSWORD = "map123"
PROFESSIONAL_DEMO_EMAIL = "engineer@example.gov"
PROFESSIONAL_DEMO_PASSWORD = "gov12345"
ADMIN_EMAILS = {"admin@jharkhand.gov.in"}
VERIFIED_PROFESSIONALS = {
    PROFESSIONAL_DEMO_EMAIL: {
        "name": "Arun Mehta",
        "organization": "Bengaluru Urban Transport Authority",
        "affiliation": "Government transport professional",
        "verification": "Verified by organization",
    }
}
CSV_FIELDS = ("email", "password_hash", "salt")
HASH_ITERATIONS = 310_000


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    used_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(used_salt), HASH_ITERATIONS)
    return digest.hex(), used_salt


def _ensure_accounts_file() -> None:
    if ACCOUNTS_FILE.exists():
        with ACCOUNTS_FILE.open(newline="", encoding="utf-8") as file:
            accounts = list(csv.DictReader(file))
        if not any(account.get("email", "").lower() == PROFESSIONAL_DEMO_EMAIL for account in accounts):
            professional_hash, professional_salt = _hash_password(PROFESSIONAL_DEMO_PASSWORD)
            with ACCOUNTS_FILE.open("a", newline="", encoding="utf-8") as file:
                csv.DictWriter(file, fieldnames=CSV_FIELDS).writerow({"email": PROFESSIONAL_DEMO_EMAIL, "password_hash": professional_hash, "salt": professional_salt})
        return
    password_hash, salt = _hash_password(DEMO_PASSWORD)
    professional_hash, professional_salt = _hash_password(PROFESSIONAL_DEMO_PASSWORD)
    with ACCOUNTS_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow({"email": DEMO_EMAIL, "password_hash": password_hash, "salt": salt})
        writer.writerow({"email": PROFESSIONAL_DEMO_EMAIL, "password_hash": professional_hash, "salt": professional_salt})


def _ensure_accounts() -> None:
    initialise()
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
