import asyncio
import random
import logging

from src.domain.mining_block import MiningBlock
from src.domain.transaction import Transaction
from src.repositories.transaction_repository import TransactionInMemoryRepository
from src.repositories.mining_block_repository import MiningBlockInMemoryRepository
from src.repositories.block_repository import BlockInMemoryRepository
from src.events.kafka_publisher import KafkaPublisher
from src.jobs.job_manager import AsyncIOJobManager

logger = logging.getLogger(__name__)


class MiningJobService:
    """Monitors mempool and publishes MiningBlocks to Kafka for miners."""

    def __init__(
        self,
        transaction_repository: TransactionInMemoryRepository,
        mining_block_repository: MiningBlockInMemoryRepository,
        block_repository: BlockInMemoryRepository,
        publisher: KafkaPublisher,
        job_manager: AsyncIOJobManager,
        mining_jobs_topic: str,
        batch_size: int,
        mining_timeout_seconds: float,
        jitter_max_seconds: float,
        node_id: str,
    ):
        self.tx_repo = transaction_repository
        self.mb_repo = mining_block_repository
        self.block_repo = block_repository
        self.publisher = publisher
        self.job_manager = job_manager
        self.mining_jobs_topic = mining_jobs_topic
        self.batch_size = batch_size
        self.mining_timeout_seconds = mining_timeout_seconds
        self.jitter_max_seconds = jitter_max_seconds
        self.node_id = node_id

    async def on_transaction_received(self) -> None:
        eligible = self._get_eligible_transactions()
        logger.info(f"Eligible txs: {len(eligible)} (batch_size={self.batch_size})")

        if len(eligible) >= self.batch_size:
            await self._create_mining_block()
            return

        if not self.job_manager.is_job_pending():
            logger.info(f"Starting timeout timer ({self.mining_timeout_seconds}s)")
            self.job_manager.schedule_job(
                delay=self.mining_timeout_seconds,
                callback=self._on_timeout,
            )

    async def on_mining_job_received(self, data: dict) -> None:
        incoming = MiningBlock(**data)
        logger.info(f"Mining block from {incoming.node_id} ({len(incoming.transactions)} txs)")
        try:
            self.mb_repo.add(incoming)
        except ValueError:
            return

        if self.job_manager.is_job_pending():
            eligible = self._get_eligible_transactions()
            if len(eligible) < self.batch_size:
                logger.info("Incoming job covers our txs — cancelling pending job")
                self.job_manager.cancel_job()

    async def _on_timeout(self) -> None:
        logger.info("Mining timeout reached")
        await self._create_mining_block()

    async def _create_mining_block(self) -> None:
        self.job_manager.cancel_job()

        eligible = self._get_eligible_transactions()
        if not eligible:
            return

        selected = eligible[: self.batch_size]
        last_block = self.block_repo.get_last_block()
        previous_hash = last_block.hash if last_block else "0"
        block_index = (last_block.index + 1) if last_block else 0

        candidate = MiningBlock(
            index=block_index,
            transactions=selected,
            previous_hash=previous_hash,
            node_id=self.node_id,
        )

        jitter = random.uniform(0, self.jitter_max_seconds)
        logger.info(f"Jitter: {jitter:.2f}s before publishing mining block")
        await asyncio.sleep(jitter)

        if self._is_duplicate(candidate):
            logger.info("Duplicate mining block — skipping")
        else:
            await self.publisher.publish(candidate, self.mining_jobs_topic)
            try:
                self.mb_repo.add(candidate)
            except ValueError:
                pass
            logger.info(f"Mining block published (index={block_index}, {len(selected)} txs)")

        remaining = self._get_eligible_transactions()
        if remaining:
            if len(remaining) >= self.batch_size:
                asyncio.create_task(self._create_mining_block())
            else:
                self.job_manager.schedule_job(
                    delay=self.mining_timeout_seconds,
                    callback=self._on_timeout,
                )

    def _get_eligible_transactions(self) -> list[Transaction]:
        all_txs = self.tx_repo.list()
        used_ids: set[str] = set()
        for mb in self.mb_repo.list():
            for tx in mb.transactions:
                used_ids.add(tx.tx_id)
        return [tx for tx in all_txs if tx.tx_id not in used_ids]

    def _is_duplicate(self, candidate: MiningBlock) -> bool:
        return any(candidate.has_same_content(mb) for mb in self.mb_repo.list())
