"""
Zero-Knowledge Proof primitives for the voting system.

- Pedersen Commitments (perfectly hiding, computationally binding)
- 1-of-2 OR Proofs (Chaum-Pedersen disjunctive) — prove C hides 0 or 1
- Sum Proof (Schnorr) — prove the committed values sum to exactly 1
- Fiat-Shamir heuristic — non-interactive proofs via hash challenges
"""

import hashlib
import secrets
from dataclasses import dataclass

from src.crypto.election_params import ElectionParameters


# ---------------------------------------------------------------------------
# Fiat-Shamir
# ---------------------------------------------------------------------------

def hash_to_challenge(*values: int, modulus: int) -> int:
    hasher = hashlib.sha256()
    for v in values:
        hasher.update(v.to_bytes(64, "big", signed=False))
    return int.from_bytes(hasher.digest(), "big") % modulus


# ---------------------------------------------------------------------------
# Pedersen Commitment
# ---------------------------------------------------------------------------

@dataclass
class PedersenCommitment:
    value: int
    randomness: int
    commitment: int


def commit(params: ElectionParameters, value: int) -> PedersenCommitment:
    r = secrets.randbelow(params.q - 1) + 1
    C = (pow(params.g, value, params.p) * pow(params.h, r, params.p)) % params.p
    return PedersenCommitment(value=value, randomness=r, commitment=C)


# ---------------------------------------------------------------------------
# OR Proof  (C hides 0 or 1)
# ---------------------------------------------------------------------------

@dataclass
class OrProof:
    a0: int
    a1: int
    c0: int
    c1: int
    r0: int
    r1: int


def prove_01(params: ElectionParameters, C: int,
             value: int, randomness: int) -> OrProof:
    p, q, g, h = params.p, params.q, params.g, params.h
    assert value in (0, 1)

    if value == 0:
        k = secrets.randbelow(q - 1) + 1
        a0 = pow(h, k, p)
        c1 = secrets.randbelow(q)
        r1 = secrets.randbelow(q)
        C_over_g = (C * pow(g, p - 2, p)) % p
        a1 = (pow(h, r1, p) * pow(C_over_g, c1, p)) % p
        c = hash_to_challenge(g, h, C, a0, a1, modulus=q)
        c0 = (c - c1) % q
        r0 = (k - randomness * c0) % q
    else:
        c0 = secrets.randbelow(q)
        r0 = secrets.randbelow(q)
        a0 = (pow(h, r0, p) * pow(C, c0, p)) % p
        k = secrets.randbelow(q - 1) + 1
        a1 = pow(h, k, p)
        c = hash_to_challenge(g, h, C, a0, a1, modulus=q)
        c1 = (c - c0) % q
        r1 = (k - randomness * c1) % q

    return OrProof(a0=a0, a1=a1, c0=c0, c1=c1, r0=r0, r1=r1)


def verify_01(params: ElectionParameters, C: int, proof: OrProof) -> bool:
    p, q, g, h = params.p, params.q, params.g, params.h
    lhs0 = (pow(h, proof.r0, p) * pow(C, proof.c0, p)) % p
    C_over_g = (C * pow(g, p - 2, p)) % p
    lhs1 = (pow(h, proof.r1, p) * pow(C_over_g, proof.c1, p)) % p
    c = hash_to_challenge(g, h, C, proof.a0, proof.a1, modulus=q)
    return lhs0 == proof.a0 and lhs1 == proof.a1 and (proof.c0 + proof.c1) % q == c


# ---------------------------------------------------------------------------
# Sum Proof  (committed values sum to 1)
# ---------------------------------------------------------------------------

@dataclass
class SumProof:
    a: int
    c: int
    r: int


def prove_sum(params: ElectionParameters, commitments: list[int],
              randomnesses: list[int]) -> SumProof:
    p, q, g, h = params.p, params.q, params.g, params.h
    P = 1
    for C in commitments:
        P = (P * C) % p
    sum_r = sum(randomnesses) % q
    target = (P * pow(g, p - 2, p)) % p
    k = secrets.randbelow(q - 1) + 1
    a = pow(h, k, p)
    c = hash_to_challenge(g, h, target, a, modulus=q)
    r = (k - sum_r * c) % q
    return SumProof(a=a, c=c, r=r)


def verify_sum(params: ElectionParameters, commitments: list[int],
               proof: SumProof) -> bool:
    p, q, g, h = params.p, params.q, params.g, params.h
    P = 1
    for C in commitments:
        P = (P * C) % p
    target = (P * pow(g, p - 2, p)) % p
    c = hash_to_challenge(g, h, target, proof.a, modulus=q)
    if c != proof.c:
        return False
    lhs = (pow(h, proof.r, p) * pow(target, proof.c, p)) % p
    return lhs == proof.a
