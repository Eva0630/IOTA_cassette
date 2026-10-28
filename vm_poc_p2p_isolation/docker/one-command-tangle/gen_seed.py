#!/usr/bin/env python3
"""Generate a random 81-tryte IOTA seed (e.g. for COMPASS_SEED) using the OS CSPRNG.

    python3 gen_seed.py

WARNING: the Compass seed (together with layers/) determines the coordinator address
that every IRI node trusts (--testnet-coordinator). Changing COMPASS_SEED means a NEW
chain: new layers/, new coordinator address in both compose files, wiped db/ + state/.
Do not change the seed of a running chain (e.g. the Pi before a demo) unless you are
resetting the chain anyway.
"""
import secrets

ALPHABET = "9ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def generate_seed(length=81):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


if __name__ == "__main__":
    print(generate_seed())
