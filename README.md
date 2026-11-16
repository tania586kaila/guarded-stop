# Guarded Stop — the AI-guarded stop order

**A DEX stop order with an AI guard in the loop: a price breach only *alarms* the order — an on-chain-posted AI verdict decides whether it actually sells, so flash wicks don't dump you at the bottom, but real trend reversals execute in seconds.**

Built for the **Reactive Omni Buildathon — Reactive Meets AI** track (DoraHacks, Nov 5 – Dec 5, 2026). All contracts run on testnets only: **Reactive Lasna** (chainId 5318007) + **Base Sepolia** (chainId 84532). No mainnet, no real funds.

![Track](https://img.shields.io/badge/track-Reactive_Meets_AI-blue)
![Lasna](https://img.shields.io/badge/Reactive_Lasna-5318007-purple)
![Base Sepolia](https://img.shields.io/badge/Base_Sepolia-84532-blue)
![Tests](https://img.shields.io/badge/foundry_tests-10%2F10_passing-brightgreen)
![Verified](https://img.shields.io/badge/sourcify-4%2F4_verified-brightgreen)
![Solidity](https://img.shields.io/badge/solidity-%5E0.8.29-lightgrey)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Repository layout

| Path | What |
|---|---|
| [`contracts/`](contracts/) | Foundry project: the four contracts + unit tests (`forge test`, 10/10). Dependencies are git submodules — clone with `--recurse-submodules`. |
| [`ai-service/`](ai-service/) | The off-chain AI guard: synthetic-data generation, the locally-trained wick-vs-reversal model, and the service that posts verdicts on-chain. |
| [`web/`](web/) | Single-file demo page replaying both on-chain acts with tx-linked evidence. |
| [`docs/`](docs/) | [`DESIGN.md`](docs/DESIGN.md) (original design/plan) and [`DEPLOYMENT.md`](docs/DEPLOYMENT.md) (deployment log, full-loop tx evidence, incident log), plus `deployment.json` and the raw `evidence-*.json` files. |

## The problem

A plain threshold stop order (like the classic Uniswap V2 stop-order demo) has two failure modes:

1. **Wicks.** Thin pools spike through the stop price for a second and bounce back. The mechanical stop sells at the worst possible price.
2. **Slow real drops.** A fixed threshold can't tell a bounce from a regime change.

Telling a wick from a reversal means reading the *shape* of the price series around the breach — exactly what a small time-series model is good at, and exactly what a contract cannot do (subscriptions don't even support range comparisons).

## How it works

```
Base Sepolia                                   Lasna (Reactive)              Base Sepolia
┌────────────┐  StopOrderPlaced   ┌─────────────────────────┐
│  MockPool  │ ─────────────────▶ │  GuardedStopReactive    │
│  (demo     │  PriceUpdate       │  pending-order state    │
│   pair +   │ ─────────────────▶ │  machine:               │
│   orders)  │                    │  MONITORING → PENDING   │
└────────────┘                    │       │        ▲        │
      ▲                           │  EXECUTE│        │VETO    │
      │ settle                    │       ▼        │        │
      │                    ┌─────────────┐   requestCallbackV_1_0 │
┌────────────┐  Decision- │  AISignal   │ ─────────┼────────────┐
│ AI guard   │  Posted    └─────────────┘          ▼            ▼
│ (off-chain │ ─────────────────▶ (event)   ┌─────────────────────────┐
│  service)  │                              │  StopExecutor (callback)│
└────────────┘                              │  double-guard verified  │
                                            └─────────────────────────┘
Cron100 on Lasna sweeps timeouts: no AI answer inside the decision window
→ the user's pre-committed fail-safe applies (default: do NOT sell).
```

| Contract | Chain | Role |
|---|---|---|
| `MockPool` | Base Sepolia | Scripted price feed + stop-order registry. Stands in for a Uniswap V2 pair (emits a Pair-shaped `Sync` alongside `PriceUpdate`) because a real testnet pool can't stage wick/reversal scripts on cue. Swap path: point the Reactive contract at a real pair and its `Sync` topic. |
| `AISignal` | Base Sepolia | On-chain inbox for AI verdicts: `postDecision(orderId, verdict, score, reasonHash)`, `verdict ∈ {EXECUTE, VETO, HOLD}`. Every decision is an auditable event with the model version and a hash of the features + explanation. |
| `GuardedStopReactive` | Lasna | The core state machine (not a forwarder): subscribes to `StopOrderPlaced`, `PriceUpdate`, `DecisionPosted`, and Cron100. Breach → `PENDING`; `EXECUTE` in-window → `requestCallbackV_1_0`; `VETO` → back to `MONITORING`; timeout → fail-safe. |
| `StopExecutor` | Base Sepolia | `AbstractCallback` (Omni two-arg constructor). `executeStop` is guarded by **both** `onlyServiceProvider` and `onlyCallbackSender`, then settles the order in `MockPool` and emits `StopExecuted`. |

The AI guard service (off-chain, in [`ai-service/`](ai-service/)) watches pending orders, builds features from the recent price series (drawdown depth, breach duration, bounce speed, volatility shock), classifies wick vs. reversal with a small locally-trained model (synthetic labelled series, no paid API key, CPU inference in milliseconds), and posts its verdict via `AISignal`.

### Why this needs a ~1-second chain

A wick lives for seconds. The whole loop — breach event → AI inference → decision on-chain → Lasna reaction → Base callback — has to finish while the verdict is still true. On a ~7s-block chain the pending window would expire before the second hop lands; Omni's ~1s blocks with instant finality are what make "wait for the AI, then decide" a viable stop-order design at all.

## How this maps to the judging criteria

| Criterion | Where it shows |
|---|---|
| **Execution** | Real reactive transactions and callbacks on Lasna + Base Sepolia with tx hashes for both demo scripts (wick → vetoed, position kept; real drop → executed in seconds), plus measured end-to-end latency. *(Done 2026-11-16 — see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) §3.)* |
| **Integration** | The Reactive contract *is* the pending-order state machine — subscriptions, decision window, timeout fail-safe — not a bolted-on forwarder. The AI verdict is a first-class on-chain event that changes the contract's execution path. |
| **Usefulness** | Wick-triggered stop-outs are a well-known DEX pain; the guard keeps the position on noise and still exits on real reversals. The fail-safe is the user's own pre-committed policy, defaulting to "don't sell on silence". |
| **Craft** | Foundry project, 10 unit tests covering every state-machine path, this README with a reproducible local run, Sourcify-verified contracts *(all four verified)*, a replayable demo page ([`web/index.html`](web/index.html)), and a <3 min demo video *(script prepared; recording pending)*. |

## Quickstart

### 1. Contracts — build & test (local, no chain needed)

Prereqs: [Foundry](https://book.getfoundry.sh/) (`forge` 1.x). Dependencies are git submodules (`reactive-lib-omni`, `forge-std`).

```bash
git clone --recurse-submodules <this-repo-url> guarded-stop
cd guarded-stop/contracts
# (already cloned without submodules? run: git submodule update --init)
forge build
forge test -v
```

Expected: **10 tests pass**, covering breach→PENDING, VETO→no execution, EXECUTE→callback request (payload, recipient, gas limit asserted), timeout fail-safe (default no-sell and opt-in sell), HOLD→EXECUTE, end-to-end callback settlement, and both callback guards.

Tests etch a `MockSystemContract` onto the real system-contract address (`0x8888…8888`), so constructor subscriptions and `requestCallbackV_1_0` calls behave as they would on Lasna and can be asserted directly.

### 2. AI guard service — reproduce the model & dry-run

```bash
cd ../ai-service
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python gen_data.py     # 1,200 synthetic series (wick/trend/chop), seed 42
.venv/bin/python train.py        # → model.joblib + evaluation.md
.venv/bin/python guard.py --dry-run   # replays wick → VETO and trend → EXECUTE locally, posts nothing
```

Held-out results (test n=300): accuracy **0.9967**, EXECUTE recall **1.0000**, VETO recall **0.9950** — on synthetic data, stated as such in [`ai-service/evaluation.md`](ai-service/evaluation.md). The trained `model.joblib` and the generated dataset (`data/dataset.npz`, ~1 MB) are included so the dry-run works without retraining.

**Live mode** (testnet): copy `ai-service/.env.example` to `.env`, fill in the Base Sepolia RPC and the deployed `MockPool` / `AISignal` addresses (see Deployment below), register the guard's wallet via `AISignal.setPoster(...)`, then run `.venv/bin/python guard.py`. The guard signs with a wallet file at the repo root (`../evm-wallet.json`, gitignored — bring your own testnet wallet). It watches pending orders and posts verdicts on-chain exactly as in the dry-run, only for real. Never commit a filled `.env` or a wallet file.

### 3. Demo page — replay both on-chain acts

Single static file, no build step. Serve the **repo root** (so the doc links resolve) and open the page:

```bash
cd ..   # repo root
python3 -m http.server 8000
# → http://localhost:8000/web/index.html
```

It replays the exact price series fed on-chain for both acts (wick → VETO, trend → EXECUTE), with every step linked to its transaction on Reactscan / BaseScan, the measured loop latencies, and — if the RPC is reachable — a live read of the two orders' final state.

## Deployment (testnet — deployed 2026-11-16)

**Status: ✅ deployed and both demo acts executed end-to-end on
testnet.** All four contracts are Sourcify-verified. Full tx-level
evidence, measured latencies, and an honest incident log (including the
reactive-contract debt outage that ate two attempts) are in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md); machine-readable deployment
record and raw per-act evidence sit next to it in `docs/`.

| Contract | Chain | Address |
|---|---|---|
| MockPool | Base Sepolia (84532) | `0x61E94433Ea4B03185c8272CC4D4B0F537C89528c` |
| AISignal | Base Sepolia (84532) | `0xe194670A23B15a748c12c9dEA510B93F3bdd46C0` |
| GuardedStopReactive | Lasna (5318007) | `0x74797ad794C71D7f58d0a0109192fc83AAb5fE3A` |
| StopExecutor | Base Sepolia (84532) | `0x098D7c8f80F699508be44B1145D41394faD17cDe` |

Full-loop highlights (all timestamps/block proofs in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) §3):

- **Wick act (order 3):** breach → AI **VETO** (score 1000) →
  `OrderVetoed` on Lasna in the same second as the decision post;
  position kept (`active=true, settled=false`); no `StopExecuted`.
- **Trend act (order 6):** breach → AI **EXECUTE** (score 1000) →
  `ExecutionRequested` on Lasna → callback `StopExecuted` on Base
  Sepolia **1 s after the decision** (sell settled @ 73.6956);
  order `settled=true`, reactive state `Executed`.
- Decision → destination-chain settlement is ~1–2 s; the ~40 s
  end-to-end figure is the AI's 30-tick observation window at demo
  feed cadence, not chain latency.

Deployment order, per the Omni docs' cycle-breaking order (executed by
a local ops runner that is not part of this repo — see the layout note
in `docs/DEPLOYMENT.md`):

1. Fund the deployer wallet with lREACT (Sepolia-ETH faucet exchange, 1 ETH → 100 lREACT) and Base Sepolia ETH (official OptimismPortal bridge from Sepolia).
2. Deploy `MockPool` + `AISignal` on Base Sepolia.
3. Deploy `GuardedStopReactive` on Lasna (payable, funded with lREACT) — it subscribes in its constructor.
4. Deploy `StopExecutor` on Base Sepolia with the Base Sepolia callback proxy (`0x476F44b11F5C942c58f4c8E3d0300E5710743585`) and the Reactive contract's address; fund it with Base Sepolia ETH (the callback recipient pays for callback execution).
5. Backfill: `GuardedStopReactive.setExecutor(executor)` and `MockPool.setExecutor(executor)`.
6. Run the two demo scripts (wick / real drop) and collect the full-loop tx hashes.

⚠️ **Runbook lesson:** deliveries cost ≈ 0.011 lREACT each and a
reactive contract **in debt receives no deliveries** (and missed origin
events are not backfilled). Keep ≳ 1.4 lREACT of headroom per 120-tick
act, top up early, and call `coverDebt()` if the balance ever runs dry
— see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) §4.

Testnet deployer wallet (public address): `0xa1b25c5A83Bc5FAe2Ddd3EB94412C3971a54F425` — testnet only, never send mainnet funds to it.

## Tech notes (Omni API, not legacy)

This codebase deliberately uses the **Omni** API from `reactive-lib-omni`: `AbstractReactive` + `onlySystem`, `SYSTEM.requestCallbackV_1_0(...)`, `AbstractCallback(proxy, sender)` with the dual modifiers, and the payload rule that the first callback argument is an `address(0)` placeholder the network overwrites with the Reactive contract's address. The legacy demos repo (`vmOnly`, emitted `Callback` events, single-arg `AbstractCallback`) was used only as a logic reference.

## Status

- ✅ Phase 1 — scaffold, 4 contracts, unit tests green.
- ✅ Phase 2 — AI guard service (synthetic data + local model, dry-run green).
- ✅ Phase 3 — Lasna + Base Sepolia deployment with full-loop tx hashes for both acts (wick → VETO, trend → EXECUTE + callback sell), Sourcify-verified contracts (see Deployment section above and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)).
- ✅ Phase 4 — demo frontend ([`web/index.html`](web/index.html): replay of both on-chain acts with tx-linked evidence), BUIDL copy draft and <3 min video script (kept with the submission materials, not in this repo).
- ⏭ Remaining — record the demo video, submit the BUIDL on DoraHacks (internal deadline Dec 3).

## License

MIT — see [`LICENSE`](LICENSE).
