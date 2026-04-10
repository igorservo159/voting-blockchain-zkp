from __future__ import annotations
from typing import TYPE_CHECKING

from src.events.kafka_consumer import BaseKafkaConsumer

if TYPE_CHECKING:
    from src.use_cases.mining_job_service import MiningJobService


class MiningBlockConsumer(BaseKafkaConsumer):
    def __init__(
        self,
        mining_job_service: MiningJobService,
        bootstrap_servers: str,
        group_id: str,
        topic: str,
    ):
        self.mining_job_service = mining_job_service
        super().__init__(bootstrap_servers, group_id, topic)

    async def process_message(self, data: dict) -> None:
        await self.mining_job_service.on_mining_job_received(data)
