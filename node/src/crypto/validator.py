"""ZKP validation for vote transactions."""

import logging

from src.crypto.election_params import ElectionParameters
from src.crypto.primitives import verify_01, verify_sum
from src.crypto.serialization import dict_to_ballot_parts

logger = logging.getLogger(__name__)


class VoteValidator:
    def __init__(self, params: ElectionParameters, candidates: list[str]):
        self.params = params
        self.num_candidates = len(candidates)
        self.candidates = candidates

    def validate_ballot_data(self, ballot_data: dict) -> tuple[bool, str]:
        try:
            _, commitments, or_proofs, sum_proof = dict_to_ballot_parts(ballot_data)
        except (KeyError, ValueError) as e:
            return False, f"Malformed ballot: {e}"

        if len(commitments) != self.num_candidates:
            return False, f"Expected {self.num_candidates} commitments, got {len(commitments)}"
        if len(or_proofs) != self.num_candidates:
            return False, f"Expected {self.num_candidates} OR proofs, got {len(or_proofs)}"

        for j, (C, proof) in enumerate(zip(commitments, or_proofs)):
            if not verify_01(self.params, C, proof):
                return False, f"OR proof invalid for candidate {j} ({self.candidates[j]})"

        if not verify_sum(self.params, commitments, sum_proof):
            return False, "Sum proof invalid (vote count != 1)"

        return True, "Valid"

    def validate_transaction(
        self, tx_data: dict,
        chain_voter_ids: set[str],
        mempool_has_voter: bool,
    ) -> tuple[bool, str]:
        voter_id = tx_data.get("voter_id", "")
        if not voter_id:
            return False, "Missing voter_id"
        if voter_id in chain_voter_ids:
            return False, f"Voter '{voter_id}' already voted (in chain)"
        if mempool_has_voter:
            return False, f"Voter '{voter_id}' already has a pending vote"

        ballot_data = tx_data.get("ballot_data")
        if not ballot_data:
            return False, "Missing ballot_data"

        return self.validate_ballot_data(ballot_data)
