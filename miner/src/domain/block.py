from datetime import datetime
from pydantic import BaseModel, Field
from src.domain.transaction import Transaction


class Block(BaseModel):
    index: int
    timestamp: datetime = Field(default_factory=datetime.now)
    transactions: list[Transaction] = []
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    miner_id: str = ""
