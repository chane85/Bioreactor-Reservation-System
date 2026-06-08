# Pure auth helpers extracted from Bioreactor_1.7_ori/auth.py — no streamlit dependency.

import hashlib
import hmac
import os
import yaml

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.normpath(os.path.join(_BACKEND_DIR, "..", "..", "Bioreactor_1.7_ori"))
)
USERS_FILE = os.path.join(DATA_DIR, "users.yaml")

PBKDF2_ITERATIONS = 200_000
PBKDF2_ALGO = "sha256"


def hash_password(plaintext: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, plaintext.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(plaintext: str, stored: str) -> bool:
    try:
        algo, iters_str, salt_hex, hash_hex = stored.split('$')
        if algo != "pbkdf2_sha256":
            return False
        iters    = int(iters_str)
        salt     = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual   = hashlib.pbkdf2_hmac(PBKDF2_ALGO, plaintext.encode('utf-8'), salt, iters)
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


def get_user(username: str) -> dict | None:
    try:
        with open(USERS_FILE, encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get('credentials', {}).get('usernames', {}).get(username)
    except Exception:
        return None
