from __future__ import annotations

from src.domain.block import Block


class BlockInMemoryRepository:
    def __init__(self) -> None:
        self._blocks: list[Block] = []

    def add(self, block: Block) -> None:
        if block in self._blocks:
            raise ValueError("Block already exists")
        self._blocks.append(block)

    def list(self) -> list[Block]:
        return list(self._blocks)

    def get_last_block(self) -> Block | None:
        return self._blocks[-1] if self._blocks else None

    def get_chain(self) -> list[Block]:
        return list(self._blocks)

    def replace_chain(self, new_chain: list[Block]) -> None:
        self._blocks = list(new_chain)

    def get_block_by_hash(self, hash: str) -> Block | None:
        for block in self._blocks:
            if block.hash == hash:
                return block
        return None

    def get_all_voter_ids(self) -> set[str]:
        ids: set[str] = set()
        for block in self._blocks:
            for tx in block.transactions:
                ids.add(tx.voter_id)
        return ids

    def get_all_tx_ids(self) -> set[str]:
        ids: set[str] = set()
        for block in self._blocks:
            for tx in block.transactions:
                ids.add(tx.tx_id)
        return ids
