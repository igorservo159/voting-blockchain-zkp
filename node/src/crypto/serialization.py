"""Hex serialization for large ints in ZKP data structures."""

from src.crypto.primitives import OrProof, SumProof


def _h(n: int) -> str:
    return hex(n)


def _i(s: str) -> int:
    return int(s, 16)


def or_proof_to_dict(p: OrProof) -> dict:
    return {"a0": _h(p.a0), "a1": _h(p.a1), "c0": _h(p.c0),
            "c1": _h(p.c1), "r0": _h(p.r0), "r1": _h(p.r1)}


def dict_to_or_proof(d: dict) -> OrProof:
    return OrProof(a0=_i(d["a0"]), a1=_i(d["a1"]), c0=_i(d["c0"]),
                   c1=_i(d["c1"]), r0=_i(d["r0"]), r1=_i(d["r1"]))


def sum_proof_to_dict(p: SumProof) -> dict:
    return {"a": _h(p.a), "c": _h(p.c), "r": _h(p.r)}


def dict_to_sum_proof(d: dict) -> SumProof:
    return SumProof(a=_i(d["a"]), c=_i(d["c"]), r=_i(d["r"]))


def ballot_to_dict(voter_id: str, commitments: list[int],
                   or_proofs: list[OrProof], sum_proof: SumProof) -> dict:
    return {
        "voter_id": voter_id,
        "commitments": [_h(c) for c in commitments],
        "or_proofs": [or_proof_to_dict(p) for p in or_proofs],
        "sum_proof": sum_proof_to_dict(sum_proof),
    }


def dict_to_ballot_parts(d: dict) -> tuple[str, list[int], list[OrProof], SumProof]:
    return (
        d["voter_id"],
        [_i(c) for c in d["commitments"]],
        [dict_to_or_proof(p) for p in d["or_proofs"]],
        dict_to_sum_proof(d["sum_proof"]),
    )
