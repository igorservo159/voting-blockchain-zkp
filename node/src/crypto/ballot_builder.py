"""Client-side ballot construction (used by the UI, not by nodes)."""

from src.crypto.election_params import ElectionParameters
from src.crypto.primitives import OrProof, SumProof, commit, prove_01, prove_sum


def create_ballot(
    params: ElectionParameters,
    candidate_index: int,
    num_candidates: int,
) -> tuple[list[int], list[OrProof], SumProof, list[int]]:
    """Create a ballot with commitments and ZK proofs.

    Returns (commitments, or_proofs, sum_proof, randomnesses).
    Only commitments and proofs are public. Randomnesses stay secret.
    """
    pedersen_list = [
        commit(params, 1 if j == candidate_index else 0)
        for j in range(num_candidates)
    ]
    commitment_points = [pc.commitment for pc in pedersen_list]
    randomnesses = [pc.randomness for pc in pedersen_list]

    or_proofs = [
        prove_01(params, pc.commitment, pc.value, pc.randomness)
        for pc in pedersen_list
    ]
    sum_proof = prove_sum(params, commitment_points, randomnesses)

    return commitment_points, or_proofs, sum_proof, randomnesses
