# Blockchain de Votacao com Zero-Knowledge Proofs

Rede blockchain distribuida para votacao eletronica com **sigilo criptografico** (ZKP) e **Proof of Work**. Desenvolvido para a disciplina de **Sistemas Distribuidos** no DCA/UFRN.

## O que e?

Um sistema onde votos sao registrados como transacoes em uma blockchain descentralizada. O diferencial: **ninguem sabe em quem voce votou** — nem os nos, nem os mineradores, nem quem audita a chain — mas qualquer pessoa pode verificar que seu voto e valido (exatamente um candidato, valor 0 ou 1). Isso e possivel gracas a **Zero-Knowledge Proofs** (Pedersen commitments + Chaum-Pedersen OR proofs + Schnorr sum proofs).

## Arquitetura

```
┌──────────┐     ┌──────────────────┐     ┌──────────────┐     ┌──────────────┐
│    UI    │────>│  Node (1, 2, 3)  │<───>│    Kafka     │<───>│ Miner (1,2,3)│
│          │     │                  │     │              │     │              │
│ Gera     │     │ Valida ZKP,      │     │ transactions │     │ PoW          │
│ cedula   │     │ mempool, chain,  │     │ mining_jobs  │     │              │
│          │     │ consenso         │     │ found_blocks │     │              │
└──────────┘     └──────────────────┘     └──────────────┘     └──────────────┘
```

| Servico | Tecnologia | Funcao |
|---------|-----------|--------|
| **Node** | FastAPI + asyncio | Mantem a chain, valida ZKP, gerencia mempool, resolve forks |
| **Miner** | asyncio + aiokafka | Recebe jobs, roda PoW, publica blocos minerados |
| **Kafka** | Confluent (KRaft) | Backbone de eventos — desacopla nos e mineradores |
| **UI** | FastAPI + Jinja2 + HTMX | Dashboard para votar, visualizar chain e simular ataques |

### Topicos Kafka

| Topico | Produtor | Consumidor | Conteudo |
|--------|---------|-----------|----------|
| `transactions` | Node (ao receber voto) | Todos os nodes | Transacao com cedula ZKP |
| `mining_jobs` | Node (batch pronto) | Todos os miners | MiningBlock (sem nonce) |
| `found_blocks` | Miner (achou nonce) | Todos os nodes | Block finalizado |

## Como executar

### Pre-requisitos
- Docker e Docker Compose

### Passo a passo

```bash
# 1. Clonar e entrar na pasta
cd voting-blockchain-zkp

# 2. Configurar ambiente
cp .env.example .env

# 3. Subir tudo (3 nodes + 3 miners + Kafka + UI)
docker compose up --build

# 4. Acessar
#    Dashboard:  http://localhost:8501
#    Node 1 API: http://localhost:8001/docs
#    Node 2 API: http://localhost:8002/docs
#    Node 3 API: http://localhost:8003/docs
#    Kafka UI:   http://localhost:8080
```

## Endpoints da API (cada node)

| Metodo | Endpoint | Descricao |
|--------|---------|-----------|
| `POST` | `/transactions` | Submeter voto (voter_id + ballot_data) |
| `POST` | `/generate-ballot` | Gerar cedula ZKP (candidate_index, num_candidates) |
| `GET` | `/blocks` | Chain completa |
| `GET` | `/transactions` | Mempool |
| `GET` | `/status` | Status do no |
| `GET` | `/tally` | Contagem de votos confirmados |
| `GET` | `/health` | Health check |
| `WS` | `/ws` | WebSocket para eventos em tempo real |

### Exemplo: formato de `/status`
```json
{
  "node_id": "node1",
  "chain_length": 5,
  "last_block_hash": "0000a3f2b1c4...",
  "mempool_size": 2,
  "difficulty": 4,
  "candidates": ["Alice", "Bob", "Carol"],
  "peers": ["http://node2:8000", "http://node3:8000"]
}
```

### Exemplo: formato de `/blocks`
```json
[
  {
    "index": 0,
    "timestamp": "2026-04-09T...",
    "transactions": [],
    "previous_hash": "0",
    "nonce": 0,
    "hash": "0000..."
  }
]
```

## Variaveis de ambiente

| Variavel | Default | Descricao |
|---------|---------|-----------|
| `KAFKA_BROKER` | `kafka:29092` | Endereco do broker |
| `TOTAL_NODES` | `3` | Numero de nos na rede |
| `DIFFICULTY` | `4` | Zeros no inicio do hash (PoW) |
| `BATCH_SIZE` | `3` | Txs por bloco |
| `MINING_TIMEOUT_SECONDS` | `20` | Timeout para fechar bloco com < batch_size txs |
| `JITTER_MAX_SECONDS` | `2` | Atraso aleatorio antes de publicar mining job |
| `CANDIDATES` | `Alice,Bob,Carol` | Lista de candidatos |

## Estrutura do projeto

```
voting-blockchain-zkp/
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/
│   ├── EXPLICACAO_FLUXO.md    # Fluxo end-to-end detalhado
│   └── EXPLICACAO_ZKP.md      # Matematica dos ZKPs
├── node/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── config.py           # pydantic-settings
│       ├── main.py             # FastAPI app + wiring
│       ├── domain/             # Block, Transaction, MiningBlock (Pydantic)
│       ├── crypto/             # ZKP: primitives, ballot_builder, validator
│       ├── repositories/       # In-memory repos (chain, mempool, mining blocks)
│       ├── events/             # Kafka publisher + consumers
│       ├── jobs/               # AsyncIO job manager (timeout/jitter)
│       ├── use_cases/          # upload_tx, receive_tx, receive_block, mining_job
│       └── api/                # Schemas, WebSocket broadcaster
├── miner/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── config.py
│       ├── main.py             # asyncio entrypoint
│       ├── domain/             # Minimal Block/MiningBlock/Transaction
│       ├── events/             # Kafka consumers + publisher
│       └── use_cases/          # MiningService (PoW + cancellation)
└── ui/
    ├── Dockerfile
    ├── app.py                  # FastAPI + Jinja2
    ├── templates/index.html    # Dashboard SPA
    └── static/style.css        # Dark theme
```

---
