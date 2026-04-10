import logging
import random

import httpx

from src.domain.block import Block
from src.repositories.block_repository import BlockInMemoryRepository
from src.repositories.transaction_repository import TransactionInMemoryRepository
from src.repositories.mining_block_repository import MiningBlockInMemoryRepository
from src.crypto.validator import VoteValidator

logger = logging.getLogger(__name__)


class ReceiveBlock:
    """Handles incoming mined blocks: validate, accept, handle forks, consensus."""

    def __init__(
        self,
        block_repository: BlockInMemoryRepository,
        transaction_repository: TransactionInMemoryRepository,
        mining_block_repository: MiningBlockInMemoryRepository,
        validator: VoteValidator,
        peer_urls: list[str],
        difficulty: int,
    ):
        self.block_repo = block_repository
        self.tx_repo = transaction_repository
        self.mb_repo = mining_block_repository
        self.validator = validator
        self.peer_urls = peer_urls
        self.difficulty = difficulty

    async def execute(self, block: Block) -> str:
        """Returns a status string: 'accepted', 'rejected:<reason>', or 'fork'."""
        logger.info(f"Received block index={block.index}, hash={block.hash[:12]}...")

        if not self._validate_hash(block):
            logger.warning(f"Block {block.index} rejected: hash mismatch")
            return "rejected:hash_mismatch"
        if not self._validate_pow(block):
            logger.warning(f"Block {block.index} rejected: PoW invalid")
            return "rejected:pow_invalid"
        if not self._validate_zkp(block):
            logger.warning(f"Block {block.index} rejected: ZKP invalid")
            return "rejected:zkp_invalid"

        last = self.block_repo.get_last_block()
        expected_prev = last.hash if last else "0"

        if block.previous_hash == expected_prev:
            accepted = self._accept_block(block)
            if accepted:
                logger.info(f"Block {block.index} accepted")
                return "accepted"
            else:
                logger.info(f"Block {block.index} already in chain (duplicate)")
                return "rejected:duplicate"
        else:
            logger.warning(f"Fork detected at block {block.index}")
            await self._handle_fork(block)
            return "fork"

    # -- Validation ----------------------------------------------------------

    def _validate_hash(self, block: Block) -> bool:
        return block.compute_hash() == block.hash

    def _validate_pow(self, block: Block) -> bool:
        return block.is_hash_valid(self.difficulty)

    def _validate_zkp(self, block: Block) -> bool:
        """Re-validate every transaction's ZKP proofs."""
        for tx in block.transactions:
            ok, reason = self.validator.validate_ballot_data(tx.ballot_data)
            if not ok:
                logger.warning(f"ZKP invalid for tx {tx.tx_id[:12]}: {reason}")
                return False
        return True

    # -- Acceptance ----------------------------------------------------------

    def _accept_block(self, block: Block) -> bool:
        try:
            self.block_repo.add(block)
        except ValueError:
            return False
        for tx in block.transactions:
            try:
                self.tx_repo.remove(tx.tx_id)
            except ValueError:
                pass
        self.mb_repo.clear()
        return True

    # -- Fork handling -------------------------------------------------------

    async def _handle_fork(self, incoming: Block) -> None:
        current_chain = self.block_repo.get_chain()
        fork_chain = self._build_fork_chain(incoming, current_chain)

        if fork_chain is None:
            logger.warning("Cannot reconstruct fork chain — running consensus")
            await self._run_consensus()
            return

        fork_point = self._find_fork_point(fork_chain, current_chain)
        current_branch = len(current_chain) - fork_point
        fork_branch = len(fork_chain) - fork_point

        logger.info(f"Fork: current={current_branch}, incoming={fork_branch}, point={fork_point}")

        if fork_branch > current_branch:
            logger.info("Switching to longer fork")
            self._return_exclusive_txs(current_chain[fork_point:], fork_chain[fork_point:])
            self.block_repo.replace_chain(fork_chain)
        elif fork_branch == current_branch:
            logger.info("Tie — keeping current chain")
            self._return_exclusive_txs([incoming], current_chain)
        else:
            logger.info("Current chain longer — discarding incoming")

        await self._run_consensus()

    def _build_fork_chain(self, incoming: Block, chain: list[Block]) -> list[Block] | None:
        for i, block in enumerate(chain):
            if block.hash == incoming.previous_hash:
                return chain[: i + 1] + [incoming]
        if incoming.previous_hash == "0":
            return [incoming]
        return None

    def _find_fork_point(self, a: list[Block], b: list[Block]) -> int:
        for i in range(min(len(a), len(b))):
            if a[i].hash != b[i].hash:
                return i
        return min(len(a), len(b))

    def _return_exclusive_txs(self, discarded: list[Block], kept: list[Block]) -> None:
        kept_ids = {tx.tx_id for blk in kept for tx in blk.transactions}
        for blk in discarded:
            for tx in blk.transactions:
                if tx.tx_id not in kept_ids:
                    try:
                        self.tx_repo.add(tx)
                        logger.info(f"Returned tx {tx.tx_id[:12]} to mempool")
                    except ValueError:
                        pass

    # -- Consensus -----------------------------------------------------------

    async def _run_consensus(self) -> None:
        if len(self.peer_urls) < 2:
            return

        selected = random.sample(self.peer_urls, min(2, len(self.peer_urls)))
        logger.info(f"Consensus with peers: {selected}")

        chains = []
        for url in selected:
            chain = await self._fetch_chain(url)
            if chain is not None:
                chains.append(chain)

        if len(chains) < 2:
            return

        chain_a, chain_b = chains[0], chains[1]
        if len(chain_a) != len(chain_b):
            return
        if not all(a.hash == b.hash for a, b in zip(chain_a, chain_b)):
            return

        my_chain = self.block_repo.get_chain()
        same = len(my_chain) == len(chain_a) and all(
            m.hash == a.hash for m, a in zip(my_chain, chain_a)
        )
        if not same:
            logger.info("Adopting majority chain")
            fp = self._find_fork_point(my_chain, chain_a)
            self._return_exclusive_txs(my_chain[fp:], chain_a[fp:])
            self.block_repo.replace_chain(chain_a)
            self.mb_repo.clear()

    async def _fetch_chain(self, url: str) -> list[Block] | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url}/blocks")
                resp.raise_for_status()
                return [Block(**b) for b in resp.json()]
        except Exception as e:
            logger.error(f"Failed to fetch chain from {url}: {e}")
            return None
