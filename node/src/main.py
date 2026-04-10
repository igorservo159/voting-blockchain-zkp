import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from src.config import settings
from src.domain import Transaction, Block

from src.crypto.election_params import get_election_params
from src.crypto.validator import VoteValidator

from src.repositories import (
    BlockInMemoryRepository,
    TransactionInMemoryRepository,
    MiningBlockInMemoryRepository,
)

from src.events.kafka_publisher import KafkaPublisher
from src.events.kafka_consumer import BaseKafkaConsumer
from src.events.mining_block_consumer import MiningBlockConsumer

from src.jobs.job_manager import AsyncIOJobManager

from src.use_cases.receive_transaction import ReceiveTransaction
from src.use_cases.upload_transaction import UploadTransaction
from src.use_cases.mining_job_service import MiningJobService
from src.use_cases.receive_block import ReceiveBlock

from src.api.websocket import WebSocketBroadcaster
from src.api.schemas import TransactionRequest, BallotRequest

# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

params = get_election_params()
validator = VoteValidator(params, settings.candidate_list)

tx_repo = TransactionInMemoryRepository()
block_repo = BlockInMemoryRepository()
mb_repo = MiningBlockInMemoryRepository()

publisher = KafkaPublisher(bootstrap_servers=settings.KAFKA_BROKER)
job_manager = AsyncIOJobManager()
ws_broadcaster = WebSocketBroadcaster()

mining_job_service = MiningJobService(
    transaction_repository=tx_repo,
    mining_block_repository=mb_repo,
    block_repository=block_repo,
    publisher=publisher,
    job_manager=job_manager,
    mining_jobs_topic=settings.MINING_JOBS_TOPIC,
    batch_size=settings.BATCH_SIZE,
    mining_timeout_seconds=settings.MINING_TIMEOUT_SECONDS,
    jitter_max_seconds=settings.JITTER_MAX_SECONDS,
    node_id=settings.NODE_ID,
)

upload_tx_use_case = UploadTransaction(
    tx_repository=tx_repo,
    block_repository=block_repo,
    publisher=publisher,
    validator=validator,
    mining_job_service=mining_job_service,
    transactions_topic=settings.TRANSACTIONS_TOPIC,
)

receive_tx_use_case = ReceiveTransaction(
    tx_repository=tx_repo,
    block_repository=block_repo,
    validator=validator,
)

receive_block_use_case = ReceiveBlock(
    block_repository=block_repo,
    transaction_repository=tx_repo,
    mining_block_repository=mb_repo,
    validator=validator,
    peer_urls=settings.PEER_URLS,
    difficulty=settings.DIFFICULTY,
)

# -- Kafka consumers that also broadcast via WebSocket -----------------------

class _TxConsumer(BaseKafkaConsumer):
    async def process_message(self, data: dict) -> None:
        tx = Transaction(**data)
        accepted = receive_tx_use_case.execute(tx)
        if accepted:
            await mining_job_service.on_transaction_received()
            await ws_broadcaster.broadcast("new_transaction", {
                "voter_id": tx.voter_id,
                "tx_id": tx.tx_id[:16],
            })


class _BlockConsumer(BaseKafkaConsumer):
    async def process_message(self, data: dict) -> None:
        block = Block(**data)
        status = await receive_block_use_case.execute(block)
        if status == "accepted":
            await ws_broadcaster.broadcast("new_block", {
                "index": block.index,
                "hash": block.hash[:16],
                "txs": len(block.transactions),
                "nonce": block.nonce,
                "miner_id": block.miner_id,
            })
        elif status == "fork":
            await ws_broadcaster.broadcast("fork_detected", {
                "index": block.index,
                "hash": block.hash[:16],
            })


tx_consumer = _TxConsumer(
    bootstrap_servers=settings.KAFKA_BROKER,
    group_id=settings.NODE_ID,
    topic=settings.TRANSACTIONS_TOPIC,
)

mb_consumer = MiningBlockConsumer(
    mining_job_service=mining_job_service,
    bootstrap_servers=settings.KAFKA_BROKER,
    group_id=settings.NODE_ID,
    topic=settings.MINING_JOBS_TOPIC,
)

block_consumer = _BlockConsumer(
    bootstrap_servers=settings.KAFKA_BROKER,
    group_id=settings.NODE_ID,
    topic=settings.FOUND_BLOCKS_TOPIC,
)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    await publisher.start()

    tasks = [
        asyncio.create_task(tx_consumer.start()),
        asyncio.create_task(mb_consumer.start()),
        asyncio.create_task(block_consumer.start()),
    ]

    yield

    await publisher.stop()
    await tx_consumer.stop()
    await mb_consumer.stop()
    await block_consumer.stop()

    for t in tasks:
        t.cancel()
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title=f"Voting Node {settings.NODE_ID}", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.post("/transactions")
async def upload_transaction(req: TransactionRequest):
    tx = Transaction(voter_id=req.voter_id, ballot_data=req.ballot_data)
    try:
        result = await upload_tx_use_case.execute(tx)
        return {"status": "accepted", "tx_id": result.tx_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/blocks")
async def list_blocks():
    return [b.model_dump() for b in block_repo.list()]


@app.get("/transactions")
async def list_transactions():
    return [tx.model_dump() for tx in tx_repo.list()]


@app.get("/status")
async def status():
    last = block_repo.get_last_block()
    return {
        "node_id": settings.NODE_ID,
        "chain_length": len(block_repo.list()),
        "last_block_hash": last.hash[:16] if last else "genesis",
        "mempool_size": tx_repo.get_size(),
        "difficulty": settings.DIFFICULTY,
        "candidates": settings.candidate_list,
        "peers": settings.PEER_URLS,
    }


@app.get("/tally")
async def tally():
    """Count confirmed ballots in the blockchain.

    Per-candidate breakdown is not possible with Pedersen commitments alone
    (perfectly hiding).  A real election system would use exponential ElGamal
    with threshold decryption so trustees can jointly decrypt the aggregate
    without revealing individual votes.
    """
    candidates = settings.candidate_list
    total = 0
    for block in block_repo.list():
        total += len(block.transactions)
    return {
        "total_confirmed_votes": total,
        "candidates": candidates,
        "note": "Pedersen commitments are perfectly hiding — per-candidate "
                "tallying requires threshold decryption (e.g. ElGamal + "
                "distributed key ceremony), which is outside the scope of "
                "this distributed-systems project.",
    }


@app.post("/generate-ballot")
async def generate_ballot(req: BallotRequest):
    """Generate a ZKP ballot (client helper — in production this runs client-side)."""
    from src.crypto.ballot_builder import create_ballot
    from src.crypto.serialization import ballot_to_dict
    commitments, or_proofs, sum_proof, _ = create_ballot(
        params, req.candidate_index, req.num_candidates,
    )
    return ballot_to_dict("", commitments, or_proofs, sum_proof)


@app.get("/health")
async def health():
    return {"status": "ok", "node_id": settings.NODE_ID}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_broadcaster.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive
    except WebSocketDisconnect:
        ws_broadcaster.disconnect(ws)
