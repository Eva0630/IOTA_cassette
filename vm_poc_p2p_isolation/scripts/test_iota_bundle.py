"""test_iota_bundle.py - Kerl / bundle-hash test vectors and offline bundle checks.

Run:  python test_iota_bundle.py      (or: python -m unittest test_iota_bundle -v)

Vector sources (all published by the IOTA Foundation's PyOTA, now archived at
github.com/iotaledger-archive/iota.py, branch master):
  [K1] test/crypto/kerl/pykerl_test.py  test_correct_hash_function  (raw Keccak-384 of b"Message")
  [K2] test/crypto/kerl/pykerl_test.py  test_correct_first / test_output_greater_243 /
       test_input_greater_243
  [K3] test/crypto/kerl/test_vectors/generate_trytes_and_hashes.csv        (rows 1-3)
  [K4] test/crypto/kerl/test_vectors/generate_trytes_and_multi_squeeze.csv (row 1)
  [K5] test/crypto/kerl/test_vectors/generate_multi_trytes_and_hash.csv    (row 1)
  [B1] test/transaction/creation_test.py  test_finalize_insecure_bundle
       (zero-value single-tx bundle that needs the obsoleteTag increment)
  [B2] test/transaction/validator_test.py BundleValidatorTestCase.setUp
       (valid 8-transaction bundle generated with iota.lib.js; full 2673-tryte
       transactions stored in test_vectors/pyota_validator_bundle.txt)
"""
import hashlib
import os
import random
import unittest

import iota_bundle as ib

HERE = os.path.dirname(os.path.abspath(__file__))


class KeccakTests(unittest.TestCase):
    def test_permutation_matches_stdlib_sha3(self):
        # same permutation, NIST padding -> must equal hashlib.sha3_384
        rnd = random.Random(1)
        for n in (0, 1, 47, 48, 103, 104, 105, 208, 500):
            data = bytes(rnd.randrange(256) for _ in range(n))
            k = ib.Keccak384(pad=0x06)
            k.update(data)
            self.assertEqual(k.digest(), hashlib.sha3_384(data).digest(), n)

    def test_keccak384_vector_K1(self):
        k = ib.Keccak384()
        k.update(b"Message")
        self.assertEqual(k.digest().hex(),
                         "0c8d6ff6e6a1cf18a0d55b20f0bca160d0d1c914a5e842f3"
                         "707a25eeb20a279f6b4e83eda8e43a67697832c7f69f53ca")

    def test_matches_pycryptodome_if_installed(self):
        try:
            from Crypto.Hash import keccak
        except ImportError:
            self.skipTest("pycryptodome not installed (optional cross-check)")
        rnd = random.Random(2)
        for n in (0, 48, 96, 104, 300):
            data = bytes(rnd.randrange(256) for _ in range(n))
            k = ib.Keccak384()
            k.update(data)
            self.assertEqual(k.digest(), keccak.new(digest_bits=384, data=data).digest())


class KerlTests(unittest.TestCase):
    def test_K2_correct_first(self):
        self.assertEqual(
            ib.kerl_hash_trytes("EMIDYNHBWMBCXVDEFOFWINXTERALUKYYPPHKP9JJ"
                                "FGJEIUY9MUDVNFZHMMWZUYUSWAIOWEVTHNWMHANBH"),
            "EJEAOOZYSAWFPZQESYDHZCGYNSTWXUMVJOVDWUNZ"
            "JXDGWCLUFGIMZRMGCAZGKNPLBRLGUNYWKLJTYEAQX")

    def test_K2_output_greater_243(self):
        self.assertEqual(
            ib.kerl_hash_trytes("9MIDYNHBWMBCXVDEFOFWINXTERALUKYYPPHKP9JJ"
                                "FGJEIUY9MUDVNFZHMMWZUYUSWAIOWEVTHNWMHANBH", 162),
            "G9JYBOMPUXHYHKSNRNMMSSZCSHOFYOYNZRSZMAAYWDYEIMVVOGKPJB"
            "VBM9TDPULSFUNMTVXRKFIDOHUXXVYDLFSZYZTWQYTE9SPYYWYTXJYQ"
            "9IFGYOLZXWZBKWZN9QOOTBQMWMUBLEWUEEASRHRTNIQWJQNDWRYLCA")

    def test_K2_input_greater_243(self):
        self.assertEqual(
            ib.kerl_hash_trytes("G9JYBOMPUXHYHKSNRNMMSSZCSHOFYOYNZRSZMAAYWDYEIMVVOGKPJB"
                                "VBM9TDPULSFUNMTVXRKFIDOHUXXVYDLFSZYZTWQYTE9SPYYWYTXJYQ"
                                "9IFGYOLZXWZBKWZN9QOOTBQMWMUBLEWUEEASRHRTNIQWJQNDWRYLCA", 162),
            "LUCKQVACOGBFYSPPVSSOXJEKNSQQRQKPZC9NXFSMQNRQCGGUL9OHVV"
            "KBDSKEQEBKXRNUJSRXYVHJTXBPDWQGNSCDCBAIRHAQCOWZEBSNHIJI"
            "GPZQITIBJQ9LNTDIBTCQ9EUWKHFLGFUVGGUWJONK9GBCDUIMAYMMQX")

    def test_K3_csv_rows(self):
        rows = [
            ("GYOMKVTSNHVJNCNFBBAH9AAMXLPLLLROQY99QN9DLSJUHDPBLCFFAIQXZA9BKMBJCYSFHFPXAHDWZFEIZ",
             "OXJCNFHUNAHWDLKKPELTBFUCVW9KLXKOGWERKTJXQMXTKFKNWNNXYD9DMJJABSEIONOSJTTEVKVDQEWTW"),
            ("ZMRSKGXE9ZPORJRBRQDWEMEOVSCE9FRANHIAEIZKLETIGITFPQHYSXFYKUMSREDJNVGUXTZEFDRZZWPJG",
             "BAQNPLEGMSYJRGPE9AMDHHMJFBPCRLRTDFUZWFMBOGJCYCE9QHXZFYFFOKYUOZC9WCCEZ9XDMYXMXWEDA"),
            ("KIPLDOXKXVWNJ9ZCCQPQDHYGCVHZTOMOFAWEZF9KKGPOWHEOUPJKPIWEPJXE9ZQI9GBCZFEJBXZLMNF9S",
             "DU9VPTG9FPTCFMDCAJNFZCIFTADKJRFGWHUNRRRTJHUDDZSFADIGEIEEOKMEAPILDIEZXYPKXMBIODJEC"),
        ]
        for inp, out in rows:
            self.assertEqual(ib.kerl_hash_trytes(inp), out)

    def test_K4_multi_squeeze(self):
        inp = "HYZY9CAVTNFQCDYFUHASZZHARFNIIGYGFLHLNMHQNAONHNLODAAFFVMDKBIVZEWEIPVHVWNHVZSUFTWLC"
        out = ("IWDWJCUUE9EBBYAEDXPDNAKTJAVY9IFOUZBNRIHMZ9NWOGOL9GYKZZ9ZLXHAI9PVPSLEAUGX9TQKMIUAX"
               "ANLYSAFQ9RJKFEADAZDTLPMYCYSGTRIOUWFKZPWJIEQHDTREOPHSUMAGIZLVIRMZGAVKODZAYBUISSQNX"
               "PWDQRZKKM9XGZTBCORFDRYFUDZSJQDGZJ9LCXJRMNEOKQDEODIGHBT9XZDIVZECQQKIUQDDYCSLOFSSYW")
        self.assertEqual(ib.kerl_hash_trytes(inp, 243), out)

    def test_K5_multi_trytes(self):
        inp = ("WMDBVBFWABDYUWRBKHNZWWTHEXPGIZJBAA9FLZXXSNQYQRW9VOQVCRAHIMZQSM9PUUTRHFDFHTQBZJEKHGQKN"
               "9NDUGSHRXWVNMSXUXTQR9RK9NYK9SYPEQFBIXAWCELQCBOGJMMDTYGLDLHVRVNAHKW9QIDQ9YCAWDMNAEFTA"
               "VLNFJCEXXM9CVPIODJJNKYKZYTEJUIA9DESWZEXYIADLRRTKQYKOFGEAYIJLONFOCUIORKZGEO")
        self.assertEqual(len(inp), 243)
        self.assertEqual(ib.kerl_hash_trytes(inp),
                         "ENUJQUMNJKKXIUPPNW9CUTNASXZTEYDYCKPMCNBJGYKZRTAABPYSWIUOJVVRSVCCKOARLXX99EFYSLBYX")

    def test_byte_conversion_round_trip(self):
        for i in range(-128, 128):
            b = bytes([i & 0xFF]) * 48
            self.assertEqual(ib.kerl_trits_to_bytes(ib.kerl_bytes_to_trits(b)), b)
        rnd = random.Random(3)
        for _ in range(20):
            t = [rnd.randrange(-1, 2) for _ in range(243)]
            t[242] = 0
            self.assertEqual(ib.kerl_bytes_to_trits(ib.kerl_trits_to_bytes(t)), t)


class TernaryTests(unittest.TestCase):
    def test_round_trips(self):
        s = ib.TRYTE_ALPHABET * 3
        self.assertEqual(ib.trits_to_trytes(ib.trytes_to_trits(s)), s)
        for v in (0, 1, -1, 13, -13, 14, 1509136296, 2**40, -(3**26)):
            self.assertEqual(ib.trytes_to_int(ib.int_to_trytes(v, 27)), v)

    def test_same_encoding_as_old_scripts(self):
        # the previous send_audit_event.int_to_trytes; chain_time.py decodes this format
        import chain_time
        for v in (0, 5, 1790000000, 1790000000123):
            self.assertEqual(chain_time._decode(ib.int_to_trytes(v, 9)), v)

    def test_add_trits(self):
        self.assertEqual(ib.trits_to_int(ib.add_trits(ib.int_to_trits(41, 9), [1])), 42)
        # wrap-around on overflow (PyOTA add_trits semantics)
        top = (3 ** 3 - 1) // 2
        self.assertEqual(ib.trits_to_int(ib.add_trits(ib.int_to_trits(top, 3), [1])), -top)


class BundleVectorTests(unittest.TestCase):
    def test_B1_insecure_bundle_increments_obsolete_tag(self):
        h, txs = ib.build_bundle([{
            "address": "9XV9RJGFJJZWITDPKSQXRTHCKJAIZZY9BYLBEQUXUNCLITRQDR9CCD99AANMXYEKD9GLJGVB9HIAGRIBQ",
            "tag": "PPDIDNQDJZGUQKOWJ9JZRCKOVGP"}], timestamp=1509136296)
        self.assertEqual(h, "NYSJSEGCWESDAFLIFCNJFWGZ9PCYDOT9VCSALKBD"
                            "9UUNKBJAJCB9KVMTHZDPRDDXC9UFJQBJBQFUPJKFC")
        t = ib.parse_transaction(txs[0])
        self.assertEqual(t["obsolete_tag"], "ZTDIDNQDJZGUQKOWJ9JZRCKOVGP")   # legacy tag bumped
        self.assertEqual(t["tag"], "PPDIDNQDJZGUQKOWJ9JZRCKOVGP")            # real tag untouched
        self.assertEqual(t["bundle"], h)

    def test_B2_real_bundle_hash_recomputes(self):
        with open(os.path.join(HERE, "test_vectors", "pyota_validator_bundle.txt")) as f:
            txs = f.read().split()
        self.assertEqual(len(txs), 8)
        self.assertEqual(ib.validate_bundle(txs), [])
        parsed = [ib.parse_transaction(t) for t in txs]
        self.assertEqual(ib.bundle_hash_of(parsed), parsed[0]["bundle"])
        # changing any essence field must break it
        t0 = txs[0]
        bad = t0[:2187] + ("A" if t0[2187] != "A" else "B") + t0[2188:]
        self.assertTrue(ib.validate_bundle([bad] + txs[1:]))


class BuildTests(unittest.TestCase):
    ADDR = "HOUSEHOLDA" + "9" * 71

    def test_single_tx(self):
        h, txs = ib.build_message_bundle(self.ADDR, "LEDGERANCHOR", "ABC", timestamp=1790000000)
        self.assertEqual(len(txs), 1)
        self.assertEqual(len(txs[0]), 2673)
        self.assertTrue(txs[0].startswith("ABC9"))
        self.assertNotEqual(h, "9" * 81)
        self.assertFalse(ib.is_insecure_hash(h))
        self.assertEqual(ib.validate_bundle(txs), [])
        t = ib.parse_transaction(txs[0])
        self.assertEqual((t["value"], t["current_index"], t["last_index"], t["timestamp"]),
                         (0, 0, 0, 1790000000))

    def test_long_message_multi_tx(self):
        msg = "".join(random.Random(4).choice(ib.TRYTE_ALPHABET[1:]) for _ in range(5000))
        h, txs = ib.build_message_bundle(self.ADDR, "X", msg, timestamp=1790000000)
        self.assertEqual(len(txs), 3)
        self.assertEqual(ib.validate_bundle(txs), [])
        joined = "".join(t[:2187] for t in txs)
        self.assertEqual(joined[:5000], msg)
        self.assertEqual(set(joined[5000:]), {"9"})
        order = ib.order_for_attach(txs)
        self.assertEqual([ib.parse_transaction(t)["current_index"] for t in order], [2, 1, 0])

    def test_never_insecure(self):
        for i in range(40):
            h, _ = ib.build_message_bundle(self.ADDR, "T", ib.int_to_trytes(i, 5), timestamp=1790000000 + i)
            self.assertNotIn(13, ib.normalize(h))

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            ib.build_message_bundle("abc", "T", "")
        with self.assertRaises(ValueError):
            ib.build_message_bundle(self.ADDR, "T" * 28, "")


class FakeIri:
    """Mimics IRI 1.8 attachToTangle chaining (no PoW) and records calls."""
    def __init__(self, states=None, reject_tips=False):
        self.calls, self.states, self.reject_tips = [], states, reject_tips
        self.trunk, self.branch = "T" * 81, "B" * 81

    def post(self, url, json=None, headers=None, timeout=None):
        cmd = json["command"]
        self.calls.append(json)
        if cmd == "getTransactionsToApprove":
            d = {"trunkTransaction": self.trunk, "branchTransaction": self.branch}
        elif cmd == "attachToTangle":
            out, prev = [], None
            for i, t in enumerate(json["trytes"]):
                tr = json["trunkTransaction"] if prev is None else prev
                br = json["branchTransaction"] if prev is None else json["trunkTransaction"]
                t = t[:2430] + tr + br + t[2592:2619] + ib.int_to_trytes(1790000000000, 9) + t[2628:]
                out.append(t)
                prev = ib.int_to_trytes(i + 1, 27) * 3   # fake tx hash
            d = {"trytes": list(reversed(out))}
        elif cmd == "getNodeInfo":
            d = {"latestSolidSubtangleMilestone": "M" * 81, "latestSolidSubtangleMilestoneIndex": 7}
        elif cmd == "getInclusionStates":
            if self.reject_tips and "tips" in json:
                d = {"error": "Invalid parameters"}
            else:
                d = {"states": self.states}
        else:
            d = {}

        class R:
            def json(self_inner):
                return d
        return R()


class NodeHelperTests(unittest.TestCase):
    def test_attach_and_send(self):
        msg = "A" * 3000
        h, txs = ib.build_message_bundle(BuildTests.ADDR, "T", msg, timestamp=1790000000)
        iri = FakeIri()
        attached = ib.attach_and_send("http://x", txs, post=iri.post)
        cmds = [c["command"] for c in iri.calls]
        self.assertEqual(cmds, ["getTransactionsToApprove", "attachToTangle",
                                "storeTransactions", "broadcastTransactions"])
        sent = iri.calls[1]["trytes"]
        self.assertEqual([ib.parse_transaction(t)["current_index"] for t in sent], [1, 0])
        self.assertEqual([ib.parse_transaction(t)["current_index"] for t in attached], [0, 1])
        self.assertEqual(ib.parse_transaction(attached[1])["trunk"], "T" * 81)   # last tx -> tips
        self.assertEqual(ib.parse_transaction(attached[0])["branch"], "T" * 81)
        self.assertEqual(ib.validate_bundle(attached), [])
        self.assertEqual(ib.parse_transaction(attached[0])["bundle"], h)

    def test_inclusion_states_uses_solid_milestone(self):
        iri = FakeIri(states=[True, False])
        self.assertEqual(ib.inclusion_states("http://x", ["A" * 81, "B" * 81], post=iri.post), [True, False])
        self.assertEqual(iri.calls[-1]["tips"], ["M" * 81])

    def test_inclusion_states_falls_back_without_tips(self):
        iri = FakeIri(states=[True], reject_tips=True)
        self.assertEqual(ib.inclusion_states("http://x", ["A" * 81], post=iri.post), [True])
        self.assertNotIn("tips", iri.calls[-1])

    def test_node_error_raises(self):
        class Err(FakeIri):
            def post(self, url, json=None, headers=None, timeout=None):
                class R:
                    def json(self_inner):
                        return {"error": "boom"}
                return R()
        with self.assertRaises(ib.IriError):
            ib.attach_and_send("http://x", ib.build_message_bundle(BuildTests.ADDR, "T", "")[1], post=Err().post)


if __name__ == "__main__":
    unittest.main(verbosity=2)
