import logging

from src.domain.transaction import Transaction
from src.repositories.transaction_repository import TransactionInMemoryRepository
from src.repositories.block_repository import BlockInMemoryRepository
from src.events.kafka_publisher import KafkaPublisher
from src.crypto.validator import VoteValidator
from src.use_cases.mining_job_service import MiningJobService

logger = logging.getLogger(__name__)


class UploadTransaction:
    """Receives a transaction from a client (UI), validates, publishes to Kafka."""

    def __init__(
        self,
        tx_repository: TransactionInMemoryRepository,
        block_repository: BlockInMemoryRepository,
        publisher: KafkaPublisher,
        validator: VoteValidator,
        mining_job_service: MiningJobService,
        transactions_topic: str,
    ):
        self.tx_repo = tx_repository
        self.block_repo = block_repository
        self.publisher = publisher
        self.validator = validator
        self.mining_job_service = mining_job_service
        self.transactions_topic = transactions_topic

    async def execute(self, tx: Transaction) -> Transaction:
        chain_voter_ids = self.block_repo.get_all_voter_ids()
        mempool_has = self.tx_repo.has_voter(tx.voter_id)

        ok, reason = self.validator.validate_transaction(
            tx.model_dump(), chain_voter_ids, mempool_has,
        )
        if not ok:
            raise ValueError(reason)

        self.tx_repo.add(tx)
        await self.publisher.publish(tx, self.transactions_topic)
        await self.mining_job_service.on_transaction_received()
        logger.info(f"Transaction uploaded: voter={tx.voter_id}")
        return tx
