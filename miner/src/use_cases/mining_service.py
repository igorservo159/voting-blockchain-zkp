import asyncio
import hashlib
import json
import logging

from src.domain.mining_block import MiningBlock
from src.domain.block import Block
from src.events.kafka_publisher import KafkaPublisher

logger = logging.getLogger(__name__)

_YIELD_INTERVAL = 1_000


class MiningService:
    """
    Core PoW mining logic.

    Receives MiningBlock jobs, iterates nonces until finding a valid hash.
    Cancels stale mining when another miner finds the block first.
    Uses asyncio.Event for cooperative cancellation.
    """

    def __init__(
        self,
        publisher: KafkaPublisher,
        found_blocks_topic: str,
        difficulty: int,
        miner_id: str,
    ):
        self.publisher = publisher
        self.found_blocks_topic = found_blocks_topic
        self.difficulty = difficulty
        self.miner_id = miner_id

        self._cancel_event = asyncio.Event()
        self._current_task: asyncio.Task | None = None
        self._current_block: MiningBlock | None = None

    async def on_mining_job_received(self, data: dict) -> None:
        incoming = MiningBlock(**data)
        logger.info(
            f"Mining job: index={incoming.index}, txs={len(incoming.transactions)}, "
            f"prev={incoming.previous_hash[:8]}..."
        )
        self._cancel_current()
        self._current_block = incoming
        self._cancel_event.clear()
        self._current_task = asyncio.create_task(self._mine(incoming))

    async def on_block_found(self, data: dict) -> None:
        block = Block(**data)
        logger.info(f"Block found by network: index={block.index}, hash={block.hash[:8]}...")
        if self._current_block and self._current_block.index == block.index:
            logger.info("Another miner won — cancelling our mining")
            self._cancel_current()

    async def _mine(self, block: MiningBlock) -> None:
        target = "0" * self.difficulty

        try:
            numeric_id = int(self.miner_id)
        except ValueError:
            numeric_id = hash(self.miner_id) % 10
        
        start_nonce = numeric_id * 1_000_000
        nonce = start_nonce

        logger.info(f"Mining started: index={block.index}, difficulty={self.difficulty}")

        try:
            while True:
                if self._cancel_event.is_set():
                    logger.info(f"Mining cancelled: index={block.index}")
                    return

                hash_hex = self._compute_hash(block, nonce)

                if hash_hex.startswith(target):
                    logger.info(f"Block mined! index={block.index}, nonce={nonce}, hash={hash_hex[:16]}...")
                    found = Block(
                        index=block.index,
                        timestamp=block.timestamp,
                        transactions=block.transactions,
                        previous_hash=block.previous_hash,
                        nonce=nonce,
                        hash=hash_hex,
                        miner_id=self.miner_id,
                    )
                    await self.publisher.publish(found, self.found_blocks_topic)
                    self._current_block = None
                    return

                nonce += 1
                if nonce % _YIELD_INTERVAL == 0:
                    await asyncio.sleep(0)

        except asyncio.CancelledError:
            logger.info(f"Mining task cancelled: index={block.index}")
        except Exception as e:
            logger.error(f"Mining error: {e}", exc_info=True)

    def _cancel_current(self) -> None:
        self._cancel_event.set()
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        self._current_task = None
        self._current_block = None

    @staticmethod
    def _compute_hash(block: MiningBlock, nonce: int) -> str:
        data = json.dumps(
            {
                "index": block.index,
                "timestamp": str(block.timestamp),
                "transactions": [tx.model_dump() for tx in block.transactions],
                "previous_hash": block.previous_hash,
                "nonce": nonce,
            },
            sort_keys=True, default=str,
        )
        return hashlib.sha256(data.encode()).hexdigest()
