import json
import logging
import asyncio

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )
        while True:
            try:
                await self.producer.start()
                logger.info("Kafka producer started")
                break
            except (KafkaConnectionError, Exception) as e:
                logger.error(f"Kafka producer connect failed, retrying in 2s: {e}")
                await asyncio.sleep(2)

    async def stop(self) -> None:
        if self.producer:
            await self.producer.stop()

    async def publish(self, message: BaseModel, topic: str) -> None:
        if not self.producer:
            await self.start()
        data = message.model_dump()
        await self.producer.send_and_wait(topic, data)
        logger.info(f"Published to {topic}")
