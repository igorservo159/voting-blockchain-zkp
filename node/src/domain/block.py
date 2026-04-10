import hashlib
import json
from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.transaction import Transaction


class Block(BaseModel):
    """A mined block in the blockchain."""

    index: int
    timestamp: datetime = Field(default_factory=datetime.now)
    transactions: list[Transaction] = []
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    miner_id: str = ""

    def compute_hash(self) -> str:
        data = json.dumps(
            {
                "index": self.index,
                "timestamp": str(self.timestamp),
                "transactions": [tx.model_dump() for tx in self.transactions],
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True, default=str,
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def is_hash_valid(self, difficulty: int) -> bool:
        return self.hash.startswith("0" * difficulty)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Block):
            return False
        return self.hash == other.hash

    def __hash__(self) -> int:
        return hash(self.hash)
