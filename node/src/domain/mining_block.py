from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.transaction import Transaction


class MiningBlock(BaseModel):
    """A candidate block sent to miners (no nonce/hash yet)."""

    index: int
    timestamp: datetime = Field(default_factory=datetime.now)
    transactions: list[Transaction] = []
    previous_hash: str
    node_id: str

    def has_same_content(self, other: "MiningBlock") -> bool:
        if self.previous_hash != other.previous_hash:
            return False
        self_ids = sorted(tx.tx_id for tx in self.transactions)
        other_ids = sorted(tx.tx_id for tx in other.transactions)
        return self_ids == other_ids
