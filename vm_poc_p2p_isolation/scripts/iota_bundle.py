"""
iota_bundle.py
Legacy IOTA (IRI 1.8.x) zero-value bundle construction, stdlib only.

Why this exists: the earlier scripts left the bundle hash as "9"*81. IRI's bundle
validator recomputes the bundle hash from the transactions, so such transactions are
invalid bundles: tip selection never picks them and no milestone ever confirms them.

What is here:
  * tryte <-> trit <-> integer conversion (balanced ternary, little-endian)
  * Keccak-384 (original Keccak padding 0x01, NOT NIST SHA3's 0x06) in pure Python
  * Kerl (Keccak-384 sponge over 243-trit blocks with IOTA's trit<->byte conversion)
  * bundle essence / bundle hash, including the "normalized hash must not contain
    13 ('M')" rule: on an insecure hash the tail's obsoleteTag is incremented and
    the hash recomputed (same as PyOTA ProposedBundle.finalize / iota.lib.js)
  * 2673-tryte transaction assembly; long messages are split into several
    2187-tryte fragments = several transactions in one bundle
  * IRI HTTP helpers: attach (getTransactionsToApprove + attachToTangle +
    storeTransactions + broadcastTransactions) and milestone confirmation
    (getInclusionStates against the latest solid milestone)

Transaction layout (trytes):
  signatureMessageFragment 0..2187, address ..2268, value ..2295, obsoleteTag ..2322,
  timestamp ..2331, currentIndex ..2340, lastIndex ..2349, bundle ..2430,
  trunk ..2511, branch ..2592, tag ..2619, attachmentTimestamp ..2628,
  attachmentTimestampLowerBound ..2637, attachmentTimestampUpperBound ..2646, nonce ..2673
"""
import time

TRYTE_ALPHABET = "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"
HASH_TRITS = 243
HASH_TRYTES = 81
FRAGMENT_TRYTES = 2187
TX_TRYTES = 2673

# (name, length in trytes) in transaction order
TX_FIELDS = [
    ("signature_message_fragment", 2187), ("address", 81), ("value", 27),
    ("obsolete_tag", 27), ("timestamp", 9), ("current_index", 9), ("last_index", 9),
    ("bundle", 81), ("trunk", 81), ("branch", 81), ("tag", 27),
    ("attachment_timestamp", 9), ("attachment_timestamp_lower", 9),
    ("attachment_timestamp_upper", 9), ("nonce", 27),
]
assert sum(n for _, n in TX_FIELDS) == TX_TRYTES

# ---------------------------------------------------------------- ternary conversion

_TRYTE_TO_TRITS = {}
for _i, _c in enumerate(TRYTE_ALPHABET):
    _v = _i if _i <= 13 else _i - 27
    _t = []
    for _ in range(3):
        _r = ((_v + 1) % 3) - 1
        _t.append(_r)
        _v = (_v - _r) // 3
    _TRYTE_TO_TRITS[_c] = _t


def tryte_value(ch):
    """Balanced value of one tryte: '9'=0, 'A'..'M'=1..13, 'N'..'Z'=-13..-1."""
    i = TRYTE_ALPHABET.index(ch)
    return i if i <= 13 else i - 27


def trytes_to_trits(trytes):
    out = []
    for c in trytes:
        try:
            out.extend(_TRYTE_TO_TRITS[c])
        except KeyError:
            raise ValueError(f"not a tryte: {c!r}")
    return out


def trits_to_trytes(trits):
    if len(trits) % 3:
        raise ValueError("trit count must be a multiple of 3")
    out = []
    for i in range(0, len(trits), 3):
        v = trits[i] + trits[i + 1] * 3 + trits[i + 2] * 9
        out.append(TRYTE_ALPHABET[v % 27])
    return "".join(out)


def int_to_trits(value, length):
    """Balanced ternary, least significant trit first, fixed length."""
    out = []
    v = value
    for _ in range(length):
        r = ((v + 1) % 3) - 1
        out.append(r)
        v = (v - r) // 3
    if v != 0:
        raise ValueError(f"{value} does not fit in {length} trits")
    return out


def trits_to_int(trits):
    total = 0
    for t in reversed(trits):
        total = total * 3 + t
    return total


def int_to_trytes(value, length):
    return trits_to_trytes(int_to_trits(value, length * 3))


def trytes_to_int(trytes):
    return trits_to_int(trytes_to_trits(trytes))


def add_trits(left, right):
    """Balanced-ternary addition, result has len(left) trits (overflow wraps), as PyOTA add_trits."""
    out = []
    carry = 0
    for i in range(len(left)):
        s = left[i] + (right[i] if i < len(right) else 0) + carry
        r = ((s + 1) % 3) - 1
        carry = (s - r) // 3
        out.append(r)
    return out


def pad_trytes(trytes, length):
    if len(trytes) > length:
        raise ValueError(f"{len(trytes)} trytes do not fit in a {length}-tryte field")
    return trytes.ljust(length, "9")


def check_trytes(trytes, name="value"):
    if any(c not in TRYTE_ALPHABET for c in trytes):
        raise ValueError(f"{name} contains non-tryte characters")
    return trytes

# ---------------------------------------------------------------- Keccak-384

_MASK64 = (1 << 64) - 1
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
        [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]   # _ROT[x][y]


def _round_constants():
    out, r = [], 1
    for _ in range(24):
        rc = 0
        for j in range(7):
            r = ((r << 1) ^ ((r >> 7) * 0x71)) % 256
            if r & 2:
                rc ^= 1 << ((1 << j) - 1)
        out.append(rc)
    return out


_RC = _round_constants()


def _rol(v, n):
    return ((v << n) | (v >> (64 - n))) & _MASK64 if n else v


def _keccak_f(a):
    """Keccak-f[1600] on 25 lanes, a[x + 5*y]."""
    for rc in _RC:
        c = [a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [a[i] ^ d[i % 5] for i in range(25)]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol(a[x + 5 * y], _ROT[x][y])
        a = [b[i] ^ ((~b[(i + 1) % 5 + 5 * (i // 5)]) & b[(i + 2) % 5 + 5 * (i // 5)])
             for i in range(25)]
        a[0] ^= rc
    return a


class Keccak384:
    """Incremental Keccak-384. pad=0x01 is original Keccak (what Kerl uses);
    pad=0x06 gives NIST SHA3-384 (only used to self-test the permutation)."""
    RATE = 104   # bytes: (1600 - 2*384) / 8

    def __init__(self, pad=0x01):
        self.pad = pad
        self.reset()

    def reset(self):
        self.state = [0] * 25
        self.buf = b""

    def _absorb_block(self, state, block):
        state = list(state)
        for i in range(self.RATE // 8):
            state[i] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        return _keccak_f(state)

    def update(self, data):
        self.buf += bytes(data)
        while len(self.buf) >= self.RATE:
            self.state = self._absorb_block(self.state, self.buf[:self.RATE])
            self.buf = self.buf[self.RATE:]

    def digest(self):
        """Non-destructive (like hashlib's digest())."""
        block = bytearray(self.buf) + bytearray(self.RATE - len(self.buf))
        block[len(self.buf)] ^= self.pad
        block[-1] ^= 0x80
        state = self._absorb_block(self.state, bytes(block))
        return b"".join(lane.to_bytes(8, "little") for lane in state)[:48]

# ---------------------------------------------------------------- Kerl

def kerl_trits_to_bytes(trits):
    """243 trits (balanced, LSB first) -> 48 bytes, signed big-endian 384-bit int
    (PyOTA kerl.conv.convertToBytes). Kerl zeroes the last trit before calling this."""
    if len(trits) != HASH_TRITS:
        raise ValueError("need 243 trits")
    return trits_to_int(trits).to_bytes(48, "big", signed=True)


def kerl_bytes_to_trits(data):
    """48 bytes (signed big-endian 384-bit int) -> 243 trits (PyOTA convertToTrits)."""
    return int_to_trits(int.from_bytes(data, "big", signed=True), HASH_TRITS)


class Kerl:
    def __init__(self):
        self.k = Keccak384()

    def absorb(self, trits):
        if len(trits) % HASH_TRITS:
            raise ValueError("Kerl absorbs multiples of 243 trits")
        for i in range(0, len(trits), HASH_TRITS):
            block = list(trits[i:i + HASH_TRITS])
            block[-1] = 0   # Kerl ignores the 243rd trit
            self.k.update(kerl_trits_to_bytes(block))

    def squeeze(self, length=HASH_TRITS):
        if length % HASH_TRITS:
            raise ValueError("Kerl squeezes multiples of 243 trits")
        out = []
        while len(out) < length:
            d = self.k.digest()
            t = kerl_bytes_to_trits(d)
            t[-1] = 0
            out.extend(t)
            self.k.reset()
            self.k.update(bytes(b ^ 0xFF for b in d))
        return out


def kerl_hash_trytes(trytes, squeeze_trytes=HASH_TRYTES):
    k = Kerl()
    k.absorb(trytes_to_trits(trytes))
    return trits_to_trytes(k.squeeze(squeeze_trytes * 3))

# ---------------------------------------------------------------- bundle

def normalize(bundle_hash):
    """Normalized bundle hash (81 ints in -13..13), as IRI/PyOTA/iota.lib.js."""
    vals = [tryte_value(c) for c in bundle_hash]
    out = []
    for i in range(3):
        chunk = vals[27 * i:27 * (i + 1)]
        s = sum(chunk)
        while s > 0:
            s -= 1
            for j in range(27):
                if chunk[j] > -13:
                    chunk[j] -= 1
                    break
        while s < 0:
            s += 1
            for j in range(27):
                if chunk[j] < 13:
                    chunk[j] += 1
                    break
        out.extend(chunk)
    return out


def is_insecure_hash(bundle_hash):
    return 13 in normalize(bundle_hash)


def essence_trits(address, value, obsolete_tag, timestamp, current_index, last_index):
    """486 trits: address(243) value(81) obsoleteTag(81) timestamp(27) currentIndex(27) lastIndex(27)."""
    return (trytes_to_trits(address) + int_to_trits(value, 81) + trytes_to_trits(obsolete_tag)
            + int_to_trits(timestamp, 27) + int_to_trits(current_index, 27)
            + int_to_trits(last_index, 27))


def parse_transaction(tx):
    if len(tx) != TX_TRYTES:
        raise ValueError(f"transaction must be {TX_TRYTES} trytes, got {len(tx)}")
    out, pos = {}, 0
    for name, n in TX_FIELDS:
        out[name] = tx[pos:pos + n]
        pos += n
    for name in ("value", "timestamp", "current_index", "last_index", "attachment_timestamp"):
        out[name] = trytes_to_int(out[name])
    return out


def bundle_hash_of(txs):
    """Recompute the bundle hash of parsed transactions (dicts from parse_transaction or
    build_bundle's internal form), ordered by current_index."""
    k = Kerl()
    for t in sorted(txs, key=lambda t: t["current_index"]):
        k.absorb(essence_trits(t["address"], t["value"], t["obsolete_tag"], t["timestamp"],
                               t["current_index"], t["last_index"]))
    return trits_to_trytes(k.squeeze())


def validate_bundle(tx_trytes_list):
    """Offline structural check of a zero-value bundle (what IRI's BundleValidator
    recomputes, minus signatures/PoW). Returns a list of problems (empty = OK)."""
    problems = []
    try:
        txs = sorted((parse_transaction(t) for t in tx_trytes_list), key=lambda t: t["current_index"])
    except ValueError as e:
        return [str(e)]
    last = len(txs) - 1
    for i, t in enumerate(txs):
        if t["current_index"] != i or t["last_index"] != last:
            problems.append(f"index {i}: currentIndex/lastIndex = {t['current_index']}/{t['last_index']}")
        if t["bundle"] != txs[0]["bundle"]:
            problems.append(f"index {i}: bundle field differs from the tail")
    if sum(t["value"] for t in txs) != 0:
        problems.append("values do not sum to 0")
    computed = bundle_hash_of(txs)
    if computed != txs[0]["bundle"]:
        problems.append(f"bundle hash mismatch: field={txs[0]['bundle']} computed={computed}")
    return problems


def split_message(message_trytes):
    """Split into 2187-tryte fragments (at least one), last one padded with '9'."""
    check_trytes(message_trytes, "message")
    if not message_trytes:
        return ["9" * FRAGMENT_TRYTES]
    return [pad_trytes(message_trytes[i:i + FRAGMENT_TRYTES], FRAGMENT_TRYTES)
            for i in range(0, len(message_trytes), FRAGMENT_TRYTES)]


def build_bundle(transfers, timestamp=None, max_tag_increments=100000):
    """Build a finalized zero-value bundle.

    transfers: list of dicts {"address": 81 trytes, "message": trytes (any length),
               "tag": <=27 trytes}. Each transfer becomes one or more transactions
               (one per 2187-tryte message fragment).
    Returns (bundle_hash, [tx trytes ordered by currentIndex, i.e. tail first]).
    trunk/branch/attachment fields/nonce are left as 9s for attachToTangle to fill.
    """
    if timestamp is None:
        timestamp = int(time.time())
    txs = []
    for tr in transfers:
        address = check_trytes(tr["address"], "address")
        if len(address) == 90:
            address = address[:81]   # strip checksum
        if len(address) != 81:
            raise ValueError("address must be 81 trytes")
        tag = pad_trytes(check_trytes(tr.get("tag", ""), "tag"), 27)
        for frag in split_message(tr.get("message", "")):
            txs.append({"signature_message_fragment": frag, "address": address, "value": 0,
                        "obsolete_tag": tag, "tag": tag, "timestamp": timestamp})
    if not txs:
        raise ValueError("bundle needs at least one transfer")
    last = len(txs) - 1
    for i, t in enumerate(txs):
        t["current_index"], t["last_index"] = i, last

    for _ in range(max_tag_increments):
        bundle_hash = bundle_hash_of(txs)
        if not is_insecure_hash(bundle_hash):
            break
        # insecure (normalized hash has a 13 / 'M'): bump the tail's obsoleteTag
        tail = txs[0]
        tail["obsolete_tag"] = trits_to_trytes(add_trits(trytes_to_trits(tail["obsolete_tag"]), [1]))
    else:
        raise RuntimeError("could not find a secure bundle hash")

    out = []
    for t in txs:
        out.append(t["signature_message_fragment"] + t["address"] + int_to_trytes(0, 27)
                   + t["obsolete_tag"] + int_to_trytes(t["timestamp"], 9)
                   + int_to_trytes(t["current_index"], 9) + int_to_trytes(t["last_index"], 9)
                   + bundle_hash + "9" * 81 + "9" * 81 + t["tag"]
                   + "9" * 9 + "9" * 9 + "9" * 9 + "9" * 27)
    assert all(len(x) == TX_TRYTES for x in out)
    return bundle_hash, out


def build_message_bundle(address, tag, message_trytes, timestamp=None):
    """Convenience: one transfer (possibly several transactions) to one address."""
    return build_bundle([{"address": address, "tag": tag, "message": message_trytes}], timestamp)


def order_for_attach(tx_trytes_list):
    """IRI's attachToTangle chains the list in the order given: the FIRST element gets
    trunk=trunkTransaction, each following one gets trunk=previous tx. So the bundle
    must be passed highest currentIndex first (as PyOTA/iota.lib.js do). IRI returns
    the result in reverse, i.e. tail (index 0) first."""
    return sorted(tx_trytes_list, key=lambda t: trytes_to_int(t[2331:2340]), reverse=True)

# ---------------------------------------------------------------- IRI HTTP helpers

IRI_HEADERS = {"Content-Type": "application/json", "X-IOTA-API-Version": "1"}


class IriError(Exception):
    pass


def iri_call(url, body, post=None, timeout=60):
    if post is None:
        import requests
        post = requests.post
    r = post(url, json=body, headers=IRI_HEADERS, timeout=timeout)
    data = r.json()
    if not isinstance(data, dict):
        raise IriError(f"{body.get('command')}: unexpected response {data!r}")
    if "error" in data or "exception" in data:
        raise IriError(f"{body.get('command')}: {data.get('error') or data.get('exception')}")
    return data


def attach_and_send(url, tx_trytes_list, mwm=9, depth=3, post=None, log=None):
    """getTransactionsToApprove -> attachToTangle -> storeTransactions -> broadcastTransactions.
    Returns the attached trytes, tail first. Raises IriError on any node error."""
    gta = iri_call(url, {"command": "getTransactionsToApprove", "depth": depth}, post)
    trunk, branch = gta["trunkTransaction"], gta["branchTransaction"]
    if log:
        log(f"   tips: trunk={trunk[:20]}... branch={branch[:20]}...")
    att = iri_call(url, {"command": "attachToTangle", "trunkTransaction": trunk,
                         "branchTransaction": branch, "minWeightMagnitude": mwm,
                         "trytes": order_for_attach(tx_trytes_list)}, post, timeout=300)
    attached = att.get("trytes") or []
    if len(attached) != len(tx_trytes_list):
        raise IriError(f"attachToTangle returned {len(attached)} of {len(tx_trytes_list)} transactions")
    attached = sorted(attached, key=lambda t: trytes_to_int(t[2331:2340]))
    problems = validate_bundle(attached)
    if problems:
        raise IriError("attached bundle failed local validation: " + "; ".join(problems))
    iri_call(url, {"command": "storeTransactions", "trytes": attached}, post)
    iri_call(url, {"command": "broadcastTransactions", "trytes": attached}, post)
    return attached


def latest_solid_milestone(url, post=None):
    info = iri_call(url, {"command": "getNodeInfo"}, post)
    return info.get("latestSolidSubtangleMilestone"), info.get("latestSolidSubtangleMilestoneIndex")


def inclusion_states(url, tx_hashes, post=None):
    """Milestone confirmation via getInclusionStates.
    IRI <=1.8.x documents a required `tips` list; we pass the latest SOLID milestone, so
    `true` means "referenced (confirmed) by that milestone". If the node rejects the
    tips parameter (newer API variants ignore/forbid it), retry without it.
    Returns list[bool] (same order as tx_hashes)."""
    ms, _ = latest_solid_milestone(url, post)
    body = {"command": "getInclusionStates", "transactions": list(tx_hashes)}
    try:
        if ms and ms != "9" * 81:
            data = iri_call(url, dict(body, tips=[ms]), post)
        else:
            data = iri_call(url, body, post)
    except IriError:
        data = iri_call(url, body, post)
    states = data.get("states")
    if not isinstance(states, list) or len(states) != len(tx_hashes):
        raise IriError(f"getInclusionStates: unexpected states {states!r}")
    return [bool(s) for s in states]
