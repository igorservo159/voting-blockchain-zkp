from __future__ import annotations
from typing import TYPE_CHECKING

from src.domain.transaction import Transaction
from src.events.kafka_consumer import BaseKafkaConsumer

if TYPE_CHECKING:
    from src.use_cases.receive_transaction import ReceiveTransaction
    from src.use_cases.mining_job_service import MiningJobService


class TransactionConsumer(BaseKafkaConsumer):
    def __init__(
        self,
        receive_tx: ReceiveTransaction,
        mining_job_service: MiningJobService,
        bootstrap_servers: str,
        group_id: str,
        topic: str,
    ):
        self.receive_tx = receive_tx
        self.mining_job_service = mining_job_service
        super().__init__(bootstrap_servers, group_id, topic)

    async def process_message(self, data: dict) -> None:
        tx = Transaction(**data)
        accepted = self.receive_tx.execute(tx)
        if accepted:
            await self.mining_job_service.on_transaction_received()
