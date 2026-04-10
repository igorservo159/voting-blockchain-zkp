import hashlib
import json
from datetime import datetime

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """A vote transaction containing ZKP ballot data."""

    tx_id: str = ""
    voter_id: str
    ballot_data: dict
    timestamp: datetime = Field(default_factory=datetime.now)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Transaction):
            return False
        return self.tx_id == other.tx_id

    def __hash__(self) -> int:
        return hash(self.tx_id)

    def compute_tx_id(self) -> str:
        raw = json.dumps(
            {"voter_id": self.voter_id, "ballot_data": self.ballot_data,
             "timestamp": str(self.timestamp)},
            sort_keys=True, default=str,
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def model_post_init(self, __context: object) -> None:
        if not self.tx_id:
            self.tx_id = self.compute_tx_id()
