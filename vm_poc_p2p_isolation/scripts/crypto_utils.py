"""
crypto_utils.py
Per-household AES-256-GCM encryption for audit records.

- One master key (env var AUDIT_MASTER_KEY, 64 hex chars) held by the backend/Admin.
- Each household key = HMAC-SHA256(master_key, "household-key:<household_id>").
- The household id is bound into the ciphertext as AAD, so a record moved to
  another household's address cannot be decrypted.
- Output format: "ENC1:" + base64(nonce || ciphertext || tag), plain ASCII so it
  fits the existing ascii_to_trytes() encoding.
"""
import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "ENC1:"
NONCE_LEN = 12
MAX_CHARS = 2187 // 2   # message field = 2187 trytes, 2 trytes per character


def _master_key() -> bytes:
    hex_key = os.environ.get("AUDIT_MASTER_KEY")
    if not hex_key:
        raise RuntimeError(
            "AUDIT_MASTER_KEY is not set. Run: export AUDIT_MASTER_KEY=$(cat ~/.audit_master_key)")
    key = bytes.fromhex(hex_key)
    if len(key) < 32:
        raise RuntimeError("AUDIT_MASTER_KEY must be at least 32 bytes (64 hex chars)")
    return key


def household_key(household_id: str) -> bytes:
    msg = f"household-key:{household_id}".encode("utf-8")
    return hmac.new(_master_key(), msg, hashlib.sha256).digest()


def encrypt(plain_text: str, household_id: str) -> str:
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(household_key(household_id)).encrypt(
        nonce, plain_text.encode("utf-8"), household_id.encode("utf-8"))
    out = PREFIX + base64.b64encode(nonce + ct).decode("ascii")
    if len(out) > MAX_CHARS:
        raise ValueError(f"Record too long for one transaction ({len(out)} > {MAX_CHARS} chars)")
    return out


def decrypt(cipher_text: str, household_id: str) -> str:
    if not cipher_text.startswith(PREFIX):
        raise ValueError("Not an ENC1 record")
    blob = base64.b64decode(cipher_text[len(PREFIX):])
    nonce, ct = blob[:NONCE_LEN], blob[NONCE_LEN:]
    plain = AESGCM(household_key(household_id)).decrypt(
        nonce, ct, household_id.encode("utf-8"))
    return plain.decode("utf-8")


def read_record(raw_text: str, household_id: str) -> str:
    """Safe reader for query results: handles legacy plaintext and decrypt failures."""
    if not raw_text.startswith(PREFIX):
        return "[LEGACY-PLAINTEXT] " + raw_text
    try:
        return decrypt(raw_text, household_id)
    except (InvalidTag, ValueError):
        return "[UNREADABLE: decrypt failed]"
