from __future__ import annotations

from src.domain.mining_block import MiningBlock


class MiningBlockInMemoryRepository:
    def __init__(self) -> None:
        self._mining_blocks: list[MiningBlock] = []

    def add(self, mb: MiningBlock) -> None:
        if mb in self._mining_blocks:
            raise ValueError("Mining block already exists")
        self._mining_blocks.append(mb)

    def list(self) -> list[MiningBlock]:
        return list(self._mining_blocks)

    def clear(self) -> None:
        self._mining_blocks.clear()
