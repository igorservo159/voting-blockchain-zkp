from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from src.domain.block import Block
from src.events.kafka_consumer import BaseKafkaConsumer

if TYPE_CHECKING:
    from src.use_cases.receive_block import ReceiveBlock

logger = logging.getLogger(__name__)


class FoundBlockConsumer(BaseKafkaConsumer):
    def __init__(
        self,
        receive_block: ReceiveBlock,
        bootstrap_servers: str,
        group_id: str,
        topic: str,
    ):
        self.receive_block = receive_block
        super().__init__(bootstrap_servers, group_id, topic)

    async def process_message(self, data: dict) -> None:
        logger.info(f"Block from Kafka: index={data.get('index')}")
        block = Block(**data)
        await self.receive_block.execute(block)
