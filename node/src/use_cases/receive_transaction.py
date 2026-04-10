import logging

from src.domain.transaction import Transaction
from src.repositories.transaction_repository import TransactionInMemoryRepository
from src.repositories.block_repository import BlockInMemoryRepository
from src.crypto.validator import VoteValidator

logger = logging.getLogger(__name__)


class ReceiveTransaction:
    """Validates and adds a transaction to the local mempool."""

    def __init__(
        self,
        tx_repository: TransactionInMemoryRepository,
        block_repository: BlockInMemoryRepository,
        validator: VoteValidator,
    ):
        self.tx_repo = tx_repository
        self.block_repo = block_repository
        self.validator = validator

    def execute(self, tx: Transaction) -> bool:
        chain_voter_ids = self.block_repo.get_all_voter_ids()
        mempool_has = self.tx_repo.has_voter(tx.voter_id)

        ok, reason = self.validator.validate_transaction(
            tx.model_dump(), chain_voter_ids, mempool_has,
        )
        if not ok:
            logger.warning(f"Transaction rejected ({tx.voter_id}): {reason}")
            return False

        try:
            self.tx_repo.add(tx)
            logger.info(f"Transaction accepted: voter={tx.voter_id} tx_id={tx.tx_id[:12]}...")
            return True
        except ValueError:
            return False
