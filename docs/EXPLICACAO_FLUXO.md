# Explicacao do Fluxo: Como o Sistema Funciona

Este documento explica em detalhe o fluxo end-to-end do sistema, o papel do Kafka, e por que separamos os componentes da forma que separamos. Use-o para estudar antes da apresentacao.

---

## 1. Para que serve o Kafka?

**Kafka e um message broker**: um servidor que recebe mensagens em "topicos" (filas nomeadas) e entrega pra quem estiver inscrito naquele topico. Pensa nele como um **mural de recados** central:
- Quem tem algo a dizer **publica** num topico (produtor).
- Quem quer ouvir aquele tipo de mensagem **assina** o topico (consumidor).
- Os dois nem precisam saber que o outro existe.

Tres propriedades que importam pra gente:
- **Desacoplamento**: o no que publica uma transacao nao precisa conhecer os outros nos. Ele joga no topico `transactions` e pronto.
- **Persistencia**: se um no cair, as mensagens ficam guardadas no Kafka. Quando ele voltar, le do ponto onde parou. Nao perde dado.
- **Ordem garantida** dentro de uma particao: importante pra blockchain (mineracao precisa concordar sobre a ordem dos eventos).

### Antes (projeto antigo, sis-dist)
P2P **direto via HTTP**. O no A faz `POST /transactions/broadcast` em B e C. Se B estiver fora do ar, perdeu a mensagem. Se A nao souber que C existe, C nunca recebe. Cada no precisa de uma lista de peers e fica fazendo requisicoes sincronas.

### Depois (com Kafka)
Nenhum no conhece outro no diretamente para trocar dados. Todos falam so com o Kafka:
- Quero anunciar uma transacao? Publico em `transactions`. Quem quiser, le.
- Quero anunciar um bloco minerado? Publico em `found_blocks`. Quem quiser, le.
- Sou minerador procurando trabalho? Assino `mining_jobs` e fico esperando.

O resultado e um **sistema mais distribuido de verdade**, nao um monte de servidores HTTP se cutucando.

---

## 2. Os tres topicos Kafka

| Topico | Quem publica | Quem consome | Conteudo |
|--------|-------------|-------------|----------|
| `transactions` | No (quando recebe voto do cliente) | Todos os nos | Cedula com ZKP |
| `mining_jobs` | No (quando o mempool tem batch suficiente) | Mineradores | `MiningBlock` (bloco candidato sem nonce) |
| `found_blocks` | Minerador (quando achou nonce valido) | Todos os nos | `Block` (bloco com PoW pronto) |

---

## 3. Fluxo end-to-end de um voto

Suponha que **a Maria quer votar na Carol**. Temos 3 nos (`node1`, `node2`, `node3`) e 3 mineradores (`miner1`, `miner2`, `miner3`) rodando.

### Etapa A — Cliente gera a cedula com ZKP

A Maria abre a UI, escolhe Carol e clica "Votar". O codigo faz:

1. Pega os parametros publicos da eleicao `(p, q, g, h)` — os mesmos que todos os nos conhecem.
2. Chama `create_ballot(params, candidate_index=2, K=3)`:
   - Gera **3 commitments Pedersen**: `C_0 = g^0*h^r0`, `C_1 = g^0*h^r1`, `C_2 = g^1*h^r2`. Quem olha de fora nao distingue qual deles esconde o `1`.
   - Gera **3 OR proofs** (uma por commitment) provando "este commit esconde 0 OU 1, sem dizer qual".
   - Gera **1 sum proof** provando "a soma dos valores commitados e exatamente 1" (ou seja, votou em UM candidato, nem zero, nem dois).
3. Empacota tudo num JSON e faz `POST /transactions` em **um no qualquer** (via UI).

**O indice do candidato (2 = Carol) NUNCA sai da maquina da Maria.** So a Maria sabe em quem ela votou. Isso e a magica do ZKP.

### Etapa B — No recebe a transacao e publica no Kafka

`node1` recebe a requisicao em `/transactions`:

1. **Valida a cedula**: chama `VoteValidator.validate_ballot_data()` que roda `verify_01()` em cada commitment + `verify_sum()`. Se qualquer prova falhar, rejeita 400.
2. **Checa double-vote local**: `voter_id` da Maria ja esta na cadeia local? Ja esta no mempool? Rejeita.
3. Se passou, cria o objeto `Transaction(tx_id, voter_id, ballot_data, timestamp)`.
4. **Publica no topico `transactions` do Kafka**. Acabou o trabalho dele aqui.
5. Responde 201 pra UI.

**Repare**: `node1` NAO faz broadcast HTTP pra `node2` e `node3`. Ele so joga no Kafka.

### Etapa C — Todos os nos consomem `transactions`

Os 3 nos (incluindo o `node1` que publicou) tem um **consumidor Kafka** assinado em `transactions`. Quando a mensagem chega:

1. Cada no **revalida a cedula independentemente** (ZKP + double-vote contra cadeia local + mempool local).
2. Se passar, adiciona ao **proprio mempool**.

Agora os 3 nos tem a Maria no mempool. Note que o `node1` tambem consome o que ele mesmo publicou — isso e normal e mais simples do que ele tratar a tx em dois caminhos diferentes.

### Etapa D — Algum no decide criar um job de mineracao

Cada no tem um **`MiningJobService`** rodando. Esse servico observa o mempool e decide quando "fechar um lote":

- **Se o mempool tem `BATCH_SIZE` (ex: 3) transacoes** → fecha o lote.
- **Ou se passou `MINING_TIMEOUT_SECONDS` desde a primeira tx no mempool** → fecha o lote (pra nao esperar pra sempre).

Quando decide fechar:

1. Pega as N transacoes do mempool e monta um **`MiningBlock`** (bloco SEM nonce ainda):
   ```
   MiningBlock(
     index = chain.last.index + 1,
     transactions = [tx1, tx2, tx3],
     previous_hash = chain.last.hash,
     node_id = "node1"
   )
   ```
2. **Aplica jitter**: dorme um tempinho aleatorio (0-2s). Isso evita que os 3 nos publiquem o mesmo `MiningBlock` ao mesmo tempo e os 3 mineradores trabalhem em paralelo no mesmo bloco.
3. Depois do jitter, **reve o mempool**: outro no ja publicou um job identico nesse meio tempo? Se sim, desiste.
4. Se nao, **publica o `MiningBlock` no topico `mining_jobs`**.

### Etapa E — Mineradores recebem o job e competem

Os 3 mineradores estao todos assinados em `mining_jobs`. Quando chega um `MiningBlock`:

1. Cada minerador comeca a **rodar PoW**: incrementa `nonce` de 0 em diante, calcula `SHA256(index, txs, previous_hash, nonce)`, e para quando o hash comeca com 4 zeros.
2. Isso e **assincrono**: o minerador usa `asyncio.sleep(0)` a cada 1000 nonces pra liberar o event loop e poder receber cancelamentos.
3. **Enquanto mineram, tambem escutam o topico `found_blocks`**. Se outro minerador achou o nonce primeiro (mesmo `index` e mesmas txs), recebem essa notificacao e **cancelam a tarefa local** — nao adianta continuar minerando algo que ja foi.
4. Quem achar primeiro: monta o `Block` final com o `nonce` e o `hash`, e **publica em `found_blocks`**.

**Comparacao importante**: no projeto antigo, cada no tinha sua **thread** de mineracao embutida e checava um `stop_event` a cada 500 nonces. Agora a mineracao e **um servico separado**, **assincrono** (nao thread), e o cancelamento vem via mensagem Kafka, nao via flag de thread compartilhada.

### Etapa F — Nos recebem o bloco e atualizam a cadeia

Os 3 nos estao assinados em `found_blocks`. Quando chega o bloco minerado:

1. **Re-validam tudo do bloco**:
   - Recomputa o hash a partir do conteudo, compara com o declarado.
   - Verifica que o hash bate com a dificuldade do PoW (4 zeros a esquerda).
   - **Re-roda a validacao ZKP de cada transacao** dentro do bloco.
   - Verifica que `previous_hash` bate com o tip atual da cadeia local.
   - Verifica double-vote contra a cadeia local.
2. Se tudo OK: `chain.add_block(block)` e **remove as txs do mempool local**.
3. Se `previous_hash` NAO bate: significa que apareceu um **fork**. O no dispara **resolucao de consenso**: pergunta aos peers via HTTP qual a cadeia mais longa, e troca a sua se for o caso.
4. Notifica a UI via WebSocket que tem bloco novo.

A Maria agora ve o voto dela confirmado na cadeia, e ninguem — nem o operador dos nos — sabe em quem ela votou.

---

## 4. Por que separar Node, Miner e UI?

Numa eleicao, existem **tres papeis distintos**:

| Papel | Quem e | O que faz |
|-------|--------|-----------|
| **Eleitor (cliente/UI)** | A Maria | Cria a cedula, esconde o voto com ZKP |
| **Validador (Node)** | A justica eleitoral | Recebe cedulas, valida ZKP, mantem a cadeia |
| **Minerador** | Qualquer um com CPU | Faz PoW, garante imutabilidade |

Se um unico processo faz **os tres**, voce esta dando a um unico agente o poder de:
- Decidir o conteudo de uma transacao (fingir que e eleitor)
- Decidir se essa transacao e valida (juiz e parte)
- Decidir em qual bloco ela vai entrar
- Decidir o nonce e fechar o bloco

Ou seja, **toda a separacao de poderes evapora**. Por isso:
- **A UI gera cedulas** — os nos **nao tem** o codigo do `create_ballot` em seus use cases. Eles so sabem **verificar**, nao gerar.
- **O Node mantem a cadeia** — ele nao minera nada.
- **O Miner e stateless** — so sabe pegar MiningBlock, rodar PoW, e devolver Block.

Cada um faz uma coisa so. Auditavel, testavel, e defensavel quando o prof perguntar "por que essa separacao?"

---

## 5. Os parametros publicos (p, q, g, h) — por que sao fixos?

Os parametros definem o **grupo matematico** onde toda a criptografia acontece. Para uma eleicao funcionar, **todo mundo** precisa estar fazendo contas no mesmo grupo.

Se a Maria usar um `p` e o no usar outro, o commitment que ela mandou nao vai bater com nada — a verificacao falha sempre. **Os parametros sao parte do "contrato publico" da eleicao.**

A nuance importante: `h` precisa ter "log discreto desconhecido em relacao a g". Se alguem souber `x` tal que `h = g^x`, essa pessoa consegue trapacear (quebra o binding do commitment). No nosso projeto, `h` e derivado via SHA-256 de uma string fixa ("nothing-up-my-sleeve"), o que e aceitavel para fins educacionais. Em producao, seria gerado via cerimonia multi-party (trusted setup).

---

## 6. Comparacao direta: antes x depois

| Aspecto | Antes (sis-dist) | Depois (com Kafka) |
|---------|-----------------|-------------------|
| Como nos trocam tx | `POST /transactions/broadcast` em cada peer | Publica em `transactions`, todos consomem |
| Como nos trocam blocos | `POST /blocks/new` em cada peer | Publica em `found_blocks`, todos consomem |
| Quem minera | Cada no tem uma thread interna | Mineradores sao processos separados |
| Como o minerador e interrompido | Flag de thread `stop_event` | Mensagem em `found_blocks` cancela `asyncio.Task` |
| Lista de peers | Cada no tem hardcoded a lista | Ninguem conhece ninguem — so o broker |
| Se um no cai | Mensagens perdidas | Mensagens ficam no Kafka, ele le quando voltar |
| Quando um bloco e fechado | "10 txs ou nada" | `BATCH_SIZE` ou `TIMEOUT` (mais realista) |
| Bloco antes de minerar | Nao existe — vira `Block` direto | `MiningBlock` (sem nonce/hash) → vira `Block` |
| Colisoes de mineracao | Frequentes | Reduzidas pelo **jitter** + dedup |

---

## 7. Sobre o Kafka como ponto central

"Mas se o Kafka cai, tudo cai. Cade a descentralizacao?"

Boa observacao. Em producao real (Bitcoin, Ethereum), nao se usa um broker central — cada no fala P2P direto. **Mas para um trabalho de Sistemas Distribuidos**, o Kafka serve como uma demonstracao didatica limpa de:
- Pub/sub e comunicacao assincrona
- Desacoplamento entre produtores e consumidores
- Persistencia e tolerancia a falhas no canal

O foco da disciplina e "como componentes distribuidos se coordenam", nao "como evitar um SPOF". O Kafka deixa essa coordenacao visivel e didatica (voce pode ate abrir o Kafka UI e literalmente ver as mensagens passando pelos topicos).
