"""
chain_time.py
Read the time fields of a raw transaction and return audit records in chronological order.

Transaction layout (2673 trytes): the message is at 0-2187, the sender's timestamp
(seconds) at 2322-2331, and the attachmentTimestamp (milliseconds, set by the node that
did the PoW) at 2619-2628. Both are balanced-ternary numbers, least significant tryte first.

NOTE: both clocks are declared by the machines that wrote them, so this is a display
order, not a tamper-proof proof of time.
"""
from datetime import datetime

ALPHABET = "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"
TS_START, TS_LEN = 2322, 9
ATT_START, ATT_LEN = 2619, 9
TX_LEN = 2673


def _decode(trytes: str) -> int:
    total = 0
    for k, ch in enumerate(trytes):
        i = ALPHABET.index(ch)
        total += (i if i <= 13 else i - 27) * (27 ** k)
    return total


def tx_timestamp(tx: str) -> int:
    return _decode(tx[TS_START:TS_START + TS_LEN])


def tx_attachment_ms(tx: str) -> int:
    return _decode(tx[ATT_START:ATT_START + ATT_LEN])


def sort_key(tx: str):
    """Sender time, then node attach time, then the raw trytes (so ties are deterministic)."""
    if len(tx) < TX_LEN:
        return (0, 0, tx)
    return (tx_timestamp(tx), tx_attachment_ms(tx), tx)


def format_time(seconds: int) -> str:
    try:
        return datetime.fromtimestamp(seconds).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
    except (OverflowError, OSError, ValueError):
        return "unknown-time"


def records_in_order(trytes_list, household_id):
    from audit_chain_utils import trytes_to_ascii
    from crypto_utils import read_record
    out = []
    for t in sorted(trytes_list, key=sort_key):
        text = read_record(trytes_to_ascii(t[:2187]), household_id)
        stamp = format_time(tx_timestamp(t)) if len(t) >= TX_LEN else "unknown-time"
        out.append(f"[{stamp}] {text}")
    return out
