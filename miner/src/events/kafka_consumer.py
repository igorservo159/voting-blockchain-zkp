import json
import logging
import asyncio
from abc import abstractmethod

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

logger = logging.getLogger(__name__)


class BaseKafkaConsumer:
    def __init__(self, bootstrap_servers: str, group_id: str, topic: str):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topic = topic
        self.consumer: AIOKafkaConsumer | None = None
        self.is_running = False

    async def start(self) -> None:
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        while True:
            try:
                await self.consumer.start()
                logger.info(f"Consumer ({self.topic}) started")
                break
            except (KafkaConnectionError, Exception) as e:
                logger.error(f"Consumer ({self.topic}) connect failed, retrying: {e}")
                await asyncio.sleep(2)

        self.is_running = True
        try:
            async for msg in self.consumer:
                if not self.is_running:
                    break
                await self.process_message(msg.value)
        except Exception as e:
            logger.error(f"Consumer ({self.topic}) error: {e}", exc_info=True)
        finally:
            await self.consumer.stop()

    async def stop(self) -> None:
        self.is_running = False
        if self.consumer:
            await self.consumer.stop()

    @abstractmethod
    async def process_message(self, data: dict) -> None: ...
