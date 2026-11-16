# AI Guard Service — the off-chain AI in the Guarded Stop loop

The Python half of **Guarded Stop** (see `../README.md` and
`../docs/DESIGN.md` §3, concept A). It watches `MockPool` price/order events,
decides whether a stop breach is a flash wick or a real trend reversal with
a small locally-trained model, and posts the verdict on-chain through
`AISignal.postDecision(...)` — the event the Lasna Reactive contract reacts
to. No paid API key anywhere: training data is synthetic, inference is local
CPU, explanations are templates.

## Layout

| file | role |
|---|---|
| `gen_data.py` | Parametric synthetic series: `wick` / `trend` / `chop`, fixed-seed reproducible → `data/dataset.npz` + `data/dataset_meta.csv` |
| `features.py` | Feature extraction from the post-breach window (shared verbatim by training and live inference) |
| `train.py` | Trains the gradient-boosting classifier → `model.joblib` + `evaluation.md` |
| `explain.py` | Template explanations (bilingual one-liners); `LLMExplainer` is an interface stub for an optional free-LLM phrasing — never on the critical path |
| `guard.py` | The service: event listening, breach detection, inference, on-chain posting; `--dry-run` replays two synthetic acts locally |
| `.env.example` | Live-mode config template (RPC, contract addresses). Copy to `.env`; never commit a filled `.env` |

## Setup

```bash
cd ai-service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Reproduce the model

```bash
.venv/bin/python gen_data.py     # 1200 series, 400/class, seed 42 → data/
.venv/bin/python train.py        # → model.joblib + evaluation.md
```

Held-out results (test n=300, stratified): **accuracy 0.9967**,
VETO recall **0.9950**, EXECUTE recall **1.0000**; per-scenario
correct-action rates: wick 1.0000, trend 1.0000, chop 0.9905 (the single
test error is a deep chop misread as a trend). Full table, confusion matrix
and permutation importances in `evaluation.md`. Caveat, stated there too:
this is a synthetic-data model — it proves the loop and gives reproducible
demo numbers, it is not trained on real market data. Features are computed
on the first **30 post-breach ticks**, the same observation window the live
guard uses, well inside the Reactive contract's 120 s decision window.

## Dry-run (no chain, no transactions)

```bash
.venv/bin/python guard.py --dry-run
```

Replays two seeded synthetic acts through the exact live decision path
(breach detection → 30-tick window → features → model → verdict):

**Act 1 — flash wick → VETO.** Base 87.82, stop 83.43; price knifes to
80.67 (3.3% below the stop) at tick 61, recovers 91% of the drop and ends
the window at 87.26. Model: P(trend) = 0.000 → **VETO, score 1000/1000** —
position kept. Feature+inference latency 16.4 ms (first call, includes
warm-up).

**Act 2 — real trend reversal → EXECUTE.** Base 89.43, stop 84.96; breach
at tick 75, price slides to 76.77 (9.6% below the stop) and is still there
at window end, rebound 0%. Model: P(trend) = 1.000 → **EXECUTE, score
1000/1000** — stop fires. Feature+inference latency 5.8 ms.

Both acts print the template explanation and the `reasonHash` that would be
posted on-chain, and state explicitly that nothing was posted.

### How latency is measured

* **Compute latency** — `time.perf_counter()` around feature extraction +
  `predict_proba` inside `decide_on_window()`; reported per decision as
  `inference_ms` (single-digit ms on CPU after warm-up).
* **Loop latency (simulated)** — in dry-run the series is 1 tick/second, so
  breach→decision = the 30-tick observation window (30 s of market time) +
  compute latency. On testnet (phase 2) the same number is measured from
  chain timestamps: `PriceUpdate` breach block → `DecisionPosted` block →
  Lasna reaction → Base callback, and the window can be shortened by
  raising the feed rate — the model only needs 30 ticks, not 30 seconds.

## Live mode (phase 2, testnet)

```bash
cp .env.example .env   # fill in RPC + deployed MockPool / AISignal addresses
.venv/bin/python guard.py
```

What it does, mirroring `GuardedStopReactive`'s state machine:

1. Polls `StopOrderPlaced` → registers orders (stop price, 1e18-scaled).
2. Polls `PriceUpdate` → appends ticks; a tick `<= stopPrice` on a
   monitoring order marks it **pending** (same rule as the contract).
3. After 30 post-breach ticks (or, if the 120 s decision window is about
   to lapse, with whatever ≥5 ticks are available), runs the model.
4. Signs `AISignal.postDecision(orderId, verdict, score, reasonHash)` with
   the testnet wallet in `../evm-wallet.json` (address
   `0xa1b25c5A83Bc5FAe2Ddd3EB94412C3971a54F425`; the key is read from the
   file at runtime and never printed). The signer must be registered via
   `AISignal.setPoster(...)`, and `score` is the confidence in the posted
   verdict (0..1000). `reasonHash = keccak256(canonical features JSON +
   explanation + model version)` — anyone can recompute it off-chain and
   audit the decision.
5. VETO re-arms monitoring locally (as the Reactive contract does);
   EXECUTE is terminal for that breach.

Fail-safe philosophy matches the contracts: if the service is down, no
decision is posted and the Reactive contract's timeout policy applies —
which defaults to **not selling**.

## Status

- ✅ Synthetic data + model + evaluation (this directory).
- ✅ Dry-run: wick → VETO, trend → EXECUTE, both with latency numbers.
- ⏭ Live testnet integration (deploy contracts, fill `.env`, run the two
  acts on Base Sepolia + Lasna and collect full-loop tx hashes) — next phase.
