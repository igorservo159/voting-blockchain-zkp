"""
Public election parameters shared by every component.

p: safe prime modulus (p = 2q + 1)
q: prime order of the subgroup
g: first generator of the order-q subgroup
h: second generator (nobody knows log_g(h))

In production, p should be >= 2048 bits and h should be generated via a
multi-party ceremony (trusted setup). For this educational project, we use
deterministic 256-bit parameters so every node/miner/UI produces identical
values without coordination.
"""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ElectionParameters:
    p: int
    q: int
    g: int
    h: int


def get_election_params() -> ElectionParameters:
    """Return hardcoded 256-bit safe-prime parameters."""
    p = 0xB7E9F735F74BF461EB409D67747A627534F17DED4BA95A60790F978549C8C24F
    q = (p - 1) // 2

    g = 25  # 5^2 — quadratic residue, in the order-q subgroup

    seed = hashlib.sha256(b"generator_h_zkp_election").digest()
    h_raw = int.from_bytes(seed, "big") % p
    h = pow(h_raw, 2, p)  # square to land in the subgroup

    assert h != 1 and pow(g, q, p) == 1 and pow(h, q, p) == 1
    return ElectionParameters(p=p, q=q, g=g, h=h)
