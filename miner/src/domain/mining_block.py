from datetime import datetime
from pydantic import BaseModel, Field
from src.domain.transaction import Transaction


class MiningBlock(BaseModel):
    index: int
    timestamp: datetime = Field(default_factory=datetime.now)
    transactions: list[Transaction] = []
    previous_hash: str
    node_id: str = ""
