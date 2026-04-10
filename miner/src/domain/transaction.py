from datetime import datetime
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    tx_id: str = ""
    voter_id: str = ""
    ballot_data: dict = {}
    timestamp: datetime = Field(default_factory=datetime.now)
