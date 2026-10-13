"""test_encryption.py - unit tests for crypto_utils (no blockchain needed)."""
import sys
from cryptography.exceptions import InvalidTag
from crypto_utils import encrypt, decrypt, read_record, MAX_CHARS

failed = 0

def check(name, ok):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        failed += 1

msg = '{"household":"A","actor":"user_123","action":"unlock_door","result":"success"}'
c = encrypt(msg, "A")

check("round trip", decrypt(c, "A") == msg)
check("ciphertext does not contain the plaintext", "unlock_door" not in c)
check("same input gives different ciphertext (random nonce)", encrypt(msg, "A") != c)

try:
    decrypt(c, "B")
    check("household B key cannot decrypt A's record", False)
except InvalidTag:
    check("household B key cannot decrypt A's record", True)

tampered = list(c)
i = len(c) - 6
tampered[i] = "A" if tampered[i] != "A" else "B"
try:
    decrypt("".join(tampered), "A")
    check("tampered ciphertext is rejected", False)
except (InvalidTag, ValueError):
    check("tampered ciphertext is rejected", True)

check("read_record: wrong household -> UNREADABLE",
      read_record(c, "B").startswith("[UNREADABLE"))
check("read_record: old plaintext -> LEGACY",
      read_record('{"household":"A"}', "A").startswith("[LEGACY-PLAINTEXT]"))
check("read_record: correct household -> plaintext", read_record(c, "A") == msg)

zh = '{"事件":"開門","結果":"成功"}'
check("non-ASCII text works", decrypt(encrypt(zh, "A"), "A") == zh)

try:
    encrypt("x" * 2000, "A")
    check("oversized record is rejected", False)
except ValueError:
    check("oversized record is rejected", True)

print(f"\n{'ALL PASSED' if failed == 0 else str(failed) + ' FAILED'}  (max record = {MAX_CHARS} chars)")
sys.exit(1 if failed else 0)
