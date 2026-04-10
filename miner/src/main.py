import asyncio
import logging
import signal

from src.config import settings
from src.events.kafka_publisher import KafkaPublisher
from src.events.mining_job_consumer import MiningJobConsumer
from src.events.found_block_consumer import FoundBlockConsumer
from src.use_cases.mining_service import MiningService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info(f"Starting {settings.MINER_ID} (difficulty={settings.DIFFICULTY})")

    publisher = KafkaPublisher(bootstrap_servers=settings.KAFKA_BROKER)
    mining_service = MiningService(
        publisher=publisher,
        found_blocks_topic=settings.FOUND_BLOCKS_TOPIC,
        difficulty=settings.DIFFICULTY,
        miner_id=settings.MINER_ID,
    )

    job_consumer = MiningJobConsumer(
        mining_service=mining_service,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id=settings.MINER_ID,
        topic=settings.MINING_JOBS_TOPIC,
    )
    block_consumer = FoundBlockConsumer(
        mining_service=mining_service,
        bootstrap_servers=settings.KAFKA_BROKER,
        group_id=settings.MINER_ID,
        topic=settings.FOUND_BLOCKS_TOPIC,
    )

    await publisher.start()

    tasks = [
        asyncio.create_task(job_consumer.start()),
        asyncio.create_task(block_consumer.start()),
    ]

    logger.info(f"{settings.MINER_ID} is running")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()

    logger.info("Shutting down...")
    await job_consumer.stop()
    await block_consumer.stop()
    await publisher.stop()
    for t in tasks:
        t.cancel()
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    logger.info(f"{settings.MINER_ID} stopped")


if __name__ == "__main__":
    asyncio.run(main())
