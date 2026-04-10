# Explicacao dos Zero-Knowledge Proofs

Este documento explica a matematica por tras das provas de conhecimento zero usadas no sistema de votacao.

## Por que ZKP?

Queremos que o voto seja **secreto** (ninguem sabe em quem voce votou) mas **verificavel** (qualquer um pode confirmar que voce votou em exatamente um candidato). ZKPs permitem provar uma afirmacao sem revelar a informacao subjacente.

## Parametros publicos (p, q, g, h)

Todos os participantes compartilham:
- **p**: primo grande (safe prime, p = 2q + 1)
- **q**: ordem do subgrupo (q = (p-1)/2)
- **g**: gerador do subgrupo de ordem q
- **h**: segundo gerador, com a propriedade crucial: **ninguem conhece x tal que h = g^x**

Se alguem soubesse esse `x`, poderia quebrar o binding do commitment e forjar votos. Por isso, em producao, `h` e gerado via cerimonia multi-party (trusted setup). No nosso projeto, usamos hash deterministico ("nothing-up-my-sleeve").

Os parametros sao fixos e identicos para todos os componentes. Isso e necessario porque os commits e provas so fazem sentido no mesmo grupo matematico.

## 1. Pedersen Commitment

Para cada candidato j, o eleitor computa:

```
C_j = g^v_j * h^r_j mod p
```

onde `v_j` e 0 ou 1 (1 se votou nesse candidato), e `r_j` e aleatorio secreto.

**Propriedades:**
- **Perfectly hiding**: dado C, todos os valores v sao igualmente provaveis (seguranca incondicional)
- **Computationally binding**: mudar v depois de fazer o commit exige resolver log discreto
- **Aditivamente homomorfico**: `C(a) * C(b) = C(a+b)` (com as randomnesses somando)

## 2. OR Proof (Chaum-Pedersen disjuntivo)

Para cada commitment C_j, o eleitor prova: "C_j esconde 0 OU C_j esconde 1" — sem revelar qual.

**Como funciona:**
- O prover roda DOIS sub-proofs em paralelo:
  - Sub-proof 0: "C = h^r" (C esconde 0, pois g^0 = 1)
  - Sub-proof 1: "C/g = h^r" (C esconde 1)
- Para o branch VERDADEIRO: computa um proof honesto (Schnorr)
- Para o branch FALSO: SIMULA um proof (possivel porque Schnorr tem simulador)
- Os sub-desafios satisfazem: `c0 + c1 = H(g, h, C, a0, a1) mod q` (Fiat-Shamir)

O verificador nao consegue distinguir qual branch e real — isso e a propriedade Zero-Knowledge.

**Verificacao:**
1. `h^r0 * C^c0 == a0` (branch 0)
2. `h^r1 * (C/g)^c1 == a1` (branch 1)
3. `c0 + c1 == H(g, h, C, a0, a1) mod q` (consistencia)

## 3. Sum Proof (Schnorr)

Depois de criar K commitments (um por candidato), o eleitor prova que a soma dos valores e exatamente 1.

O produto de todos os commitments:
```
P = C_0 * C_1 * ... * C_{K-1} = g^(soma_v) * h^(soma_r)
```

Se soma_v = 1, entao `P/g = h^(soma_r)`. Provamos conhecimento do log discreto de P/g na base h via Schnorr padrao.

**Verificacao:**
1. Recomputa `target = P * g^{-1} mod p`
2. Verifica `h^r * target^c == a`
3. Verifica que c bate com Fiat-Shamir

## 4. Fiat-Shamir Heuristic

Transforma proofs interativos em nao-interativos: em vez de um verificador enviar um desafio aleatorio, derivamos o desafio deterministicamente via SHA-256 do transcript (todos os valores publicos da prova).

## Fluxo completo de um voto

1. Eleitor escolhe candidato j (ex: Carol, indice 2)
2. Para cada candidato: `C_j = g^v * h^r mod p` (v=1 para Carol, v=0 para os outros)
3. Para cada C_j: gera OR proof provando v=0 ou v=1
4. Gera sum proof provando que soma dos v = 1
5. Envia (commitments, or_proofs, sum_proof) — **nunca envia o indice do candidato**
6. Qualquer no pode verificar as proofs sem saber em quem o eleitor votou

## Limitacao: apuracao

Para contar os votos sem revelar quem votou em quem, seria necessario **threshold decryption** ou **MPC** entre multiplas autoridades — cada uma decifrando sua "fatia" do resultado agregado sem ver votos individuais. Isso esta fora do escopo deste trabalho. O sistema conta apenas o numero total de votos confirmados.
