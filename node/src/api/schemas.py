from pydantic import BaseModel


class TransactionRequest(BaseModel):
    voter_id: str
    ballot_data: dict


class BallotRequest(BaseModel):
    candidate_index: int
    num_candidates: int
