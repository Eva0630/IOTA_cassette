"""
audit_chain_utils.py
------------------------------------------------------------
UC5.3 跨屋隔離 - 正式命名規則 + 加密插槽

設計重點：
1. address 不直接用明文 household_id 拼字串，改用「雜湊 + 系統密鑰SALT」，
   避免外部只靠猜測 (HOUSEHOLDA, HOUSEHOLDB, HOUSEHOLDC...) 就能反推出
   其他家庭的 address，繞過應用層直接查詢 Tangle 節點。
2. tag 不涉及隱私識別，可以用明文分類事件類型，方便統計/掃描。
3. encrypt_message()/decrypt_message() 目前是 pass-through（不加密），
   但已經是正式的「插槽」，之後要換成 AES/RSA 只需要改這兩個函式，
   不用重構呼叫端。
------------------------------------------------------------
"""

import hashlib

# 這個 SALT 正式環境必須存在後端的環境變數/密鑰管理服務，
# 絕對不能寫死在程式碼或進版控，這裡先寫死只是為了讓範例可以直接執行。
SYSTEM_SALT = "REPLACE_ME_WITH_A_REAL_SECRET_SALT_IN_ENV_VAR"

TRYTE_ALPHABET = "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"

ACTION_TAG_MAP = {
    "unlock_door": "UNLOCKDOOR",
    "lock_door": "LOCKDOOR",
    "view_camera": "VIEWCAMERA",
    "alert_triggered": "ALERTTRIG",
    "admin_access": "ADMINACCESS",
}


def pad_trytes(trytes: str, length: int) -> str:
    return trytes.ljust(length, "9")[:length]


def ascii_to_trytes(text: str) -> str:
    trytes = ""
    for char in text:
        code = ord(char)
        if code > 255:
            raise ValueError(f"字元超出範圍: {char}")
        first = code % 27
        second = (code - first) // 27
        trytes += TRYTE_ALPHABET[first] + TRYTE_ALPHABET[second]
    return trytes


def trytes_to_ascii(trytes: str) -> str:
    text = ""
    for i in range(0, len(trytes) - 1, 2):
        pair = trytes[i:i + 2]
        first = TRYTE_ALPHABET.index(pair[0])
        second = TRYTE_ALPHABET.index(pair[1])
        code = first + second * 27
        if code == 0:
            break
        text += chr(code)
    return text


def _hash_to_trytes(text: str, length: int) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    trytes = ""
    for ch in digest:
        trytes += TRYTE_ALPHABET[int(ch, 16) % 27]
    return pad_trytes(trytes, length)


def household_to_address(household_id: str) -> str:
    raw = f"household:{household_id}:{SYSTEM_SALT}"
    return _hash_to_trytes(raw, 81)


def action_to_tag(action: str) -> str:
    tag_text = ACTION_TAG_MAP.get(action, "GENERICEVENT")
    return pad_trytes(tag_text, 27)


def encrypt_message(plain_text: str, household_id: str) -> str:
    return plain_text


def decrypt_message(cipher_text: str, household_id: str) -> str:
    return cipher_text


if __name__ == "__main__":
    for hid in ["A", "B", "C"]:
        addr = household_to_address(hid)
        print(f"household={hid} -> address={addr}")

    print()
    print("tag範例:")
    for action in ["unlock_door", "view_camera", "unknown_action"]:
        print(f"  {action} -> {action_to_tag(action)}")