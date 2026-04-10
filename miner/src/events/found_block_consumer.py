from __future__ import annotations
from typing import TYPE_CHECKING

from src.events.kafka_consumer import BaseKafkaConsumer

if TYPE_CHECKING:
    from src.use_cases.mining_service import MiningService


class FoundBlockConsumer(BaseKafkaConsumer):
    def __init__(self, mining_service: MiningService, **kwargs: str):
        self.mining_service = mining_service
        super().__init__(**kwargs)

    async def process_message(self, data: dict) -> None:
        await self.mining_service.on_block_found(data)
