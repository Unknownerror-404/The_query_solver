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

ACCOUNTS_FILE = Path(__file__).with_name("accounts.csv")
DEMO_EMAIL = "citizen@example.com"
DEMO_PASSWORD = "map123"
CSV_FIELDS = ("email", "password_hash", "salt")
HASH_ITERATIONS = 310_000


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    used_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(used_salt), HASH_ITERATIONS)
    return digest.hex(), used_salt


def _ensure_accounts_file() -> None:
    if ACCOUNTS_FILE.exists():
        return
    password_hash, salt = _hash_password(DEMO_PASSWORD)
    with ACCOUNTS_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow({"email": DEMO_EMAIL, "password_hash": password_hash, "salt": salt})


def authenticate(email: str, password: str) -> bool:
    _ensure_accounts_file()
    email = email.strip().lower()
    with ACCOUNTS_FILE.open(newline="", encoding="utf-8") as file:
        for account in csv.DictReader(file):
            if account.get("email", "").lower() != email:
                continue
            password_hash, _ = _hash_password(password, account["salt"])
            return hmac.compare_digest(password_hash, account["password_hash"])
    return False


def create_account(email: str, password: str) -> tuple[bool, str]:
    _ensure_accounts_file()
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Enter a valid email address."
    if len(password) < 8:
        return False, "Password must contain at least 8 characters."
    with ACCOUNTS_FILE.open(newline="", encoding="utf-8") as file:
        accounts = list(csv.DictReader(file))
    if any(account.get("email", "").lower() == email for account in accounts):
        return False, "An account with that email already exists."
    password_hash, salt = _hash_password(password)
    with ACCOUNTS_FILE.open("a", newline="", encoding="utf-8") as file:
        csv.DictWriter(file, fieldnames=CSV_FIELDS).writerow({"email": email, "password_hash": password_hash, "salt": salt})
    return True, "Account created."


_ensure_accounts_file()
