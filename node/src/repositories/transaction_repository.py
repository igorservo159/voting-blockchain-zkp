from __future__ import annotations

from src.domain.transaction import Transaction


class TransactionInMemoryRepository:
    """Thread-safe-ish mempool (single-threaded asyncio, so no lock needed)."""

    def __init__(self) -> None:
        self._mempool: list[Transaction] = []

    def add(self, tx: Transaction) -> None:
        if tx in self._mempool:
            raise ValueError("Transaction already in mempool")
        self._mempool.append(tx)

    def list(self) -> list[Transaction]:
        return list(self._mempool)

    def remove(self, tx_id: str) -> None:
        for tx in self._mempool:
            if tx.tx_id == tx_id:
                self._mempool.remove(tx)
                return
        raise ValueError("Transaction not found")

    def has_voter(self, voter_id: str) -> bool:
        return any(tx.voter_id == voter_id for tx in self._mempool)

    def get_size(self) -> int:
        return len(self._mempool)

    def clear(self) -> None:
        self._mempool.clear()
