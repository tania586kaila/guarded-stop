#!/usr/bin/env python3
"""AI guard service — the off-chain link in the Guarded Stop loop.

Alignment with the contracts (see ../repo/src):

  * ``MockPool`` (Base Sepolia) emits ``PriceUpdate(uint256 price)`` on every
    feed and ``StopOrderPlaced(orderId, owner, amount, stopPrice,
    failSafeExecute)`` when an order is registered. Prices are 1e18-scaled.
  * ``GuardedStopReactive`` (Lasna) mirrors the same events: an order whose
    stop is breached (``price <= stopPrice``) becomes PENDING and the AI has
    ``decisionWindow`` seconds (default 120) to answer.
  * This service answers by calling ``AISignal.postDecision(orderId,
    verdict, score, reasonHash)`` where ``verdict`` is the AISignal enum
    (EXECUTE=0, VETO=1, HOLD=2), ``score`` is the model confidence in the
    posted verdict (0..1000) and ``reasonHash`` is the keccak hash of the
    feature vector + explanation + model version, so anyone can reproduce
    the decision off-chain.

Flow per order: learn order from ``StopOrderPlaced`` → stream ``PriceUpdate``
ticks → detect breach exactly like the Reactive contract → observe the
post-breach window (``observe_window`` ticks from the trained model bundle)
→ extract features (``features.py``) → gradient-boosting inference →
template explanation (``explain.py``, no paid API) → sign & post on-chain
with the testnet wallet from ``../evm-wallet.json`` (the key is read from
that file at runtime and never printed or logged).

Modes:
  * ``python guard.py --dry-run`` — no chain, no transactions. Replays two
    synthetic acts locally (wick → VETO, trend → EXECUTE) and prints the
    verdicts and latencies. This is the demo/CI path.
  * ``python guard.py`` — live mode. Requires a filled-in ``.env`` (see
    ``.env.example``): RPC URL + deployed MockPool / AISignal addresses.
    Polls events and posts decisions. (Phase-2 testnet integration.)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field

import numpy as np

from explain import VERDICT_EXECUTE, VERDICT_HOLD, VERDICT_VETO, generate_explanation
from features import extract_features, feature_vector

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = os.path.join(HERE, "model.joblib")
DEFAULT_WALLET = os.path.join(HERE, "..", "evm-wallet.json")
PRICE_SCALE = 10**18  # MockPool prices are 1e18-scaled USD

# AISignal.Verdict ordinals — must match ../repo/src/AISignal.sol.
VERDICT_TO_ENUM = {VERDICT_EXECUTE: 0, VERDICT_VETO: 1, VERDICT_HOLD: 2}

# Minimal ABIs (only what the guard uses) — full sources in ../repo/src.
MOCKPOOL_ABI = [
    {"anonymous": False, "inputs": [{"indexed": False, "name": "price", "type": "uint256"}],
     "name": "PriceUpdate", "type": "event"},
    {"anonymous": False, "inputs": [
        {"indexed": True, "name": "orderId", "type": "uint256"},
        {"indexed": True, "name": "owner", "type": "address"},
        {"indexed": False, "name": "amount", "type": "uint256"},
        {"indexed": False, "name": "stopPrice", "type": "uint256"},
        {"indexed": False, "name": "failSafeExecute", "type": "bool"}],
     "name": "StopOrderPlaced", "type": "event"},
]
AISIGNAL_ABI = [
    {"inputs": [
        {"name": "orderId_", "type": "uint256"},
        {"name": "verdict_", "type": "uint8"},
        {"name": "score_", "type": "uint256"},
        {"name": "reasonHash_", "type": "bytes32"}],
     "name": "postDecision", "outputs": [], "stateMutability": "nonpayable",
     "type": "function"},
    {"anonymous": False, "inputs": [
        {"indexed": True, "name": "orderId", "type": "uint256"},
        {"indexed": False, "name": "verdict", "type": "uint8"},
        {"indexed": False, "name": "score", "type": "uint256"},
        {"indexed": False, "name": "reasonHash", "type": "bytes32"}],
     "name": "DecisionPosted", "type": "event"},
]


# ---------------------------------------------------------------------------
# Config (.env file + environment override; no secrets in the repo)
# ---------------------------------------------------------------------------
def load_config(env_path: str | None = None) -> dict:
    cfg = {
        "BASE_SEPOLIA_RPC_URL": "",
        "MOCK_POOL_ADDRESS": "",
        "AI_SIGNAL_ADDRESS": "",
        "WALLET_FILE": DEFAULT_WALLET,
        "MODEL_PATH": DEFAULT_MODEL,
        "DECISION_WINDOW_SECONDS": "120",
        "POLL_INTERVAL_SECONDS": "2",
    }
    path = env_path or os.path.join(HERE, ".env")
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                cfg[key.strip()] = value.strip().strip('"').strip("'")
    for key in list(cfg):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


# ---------------------------------------------------------------------------
# Model + decision core (shared by dry-run and live mode)
# ---------------------------------------------------------------------------
class GuardModel:
    """Loads the joblib bundle written by train.py and classifies windows."""

    def __init__(self, model_path: str = DEFAULT_MODEL):
        import joblib
        bundle = joblib.load(model_path)
        self.model = bundle["model"]
        self.feature_names = bundle["feature_names"]
        self.observe_window = int(bundle["observe_window"])
        self.model_version = bundle["model_version"]

    def predict_proba_execute(self, features: dict[str, float]) -> float:
        vec = feature_vector(features).reshape(1, -1)
        return float(self.model.predict_proba(vec)[0, 1])


@dataclass
class Decision:
    verdict: str                 # "EXECUTE" | "VETO" | "HOLD"
    score: int                   # confidence in the verdict, 0..1000
    p_execute: float             # raw model probability of a real trend
    features: dict[str, float]
    explanation: str
    reason_hash: str             # 0x-prefixed keccak of features+explanation+version
    inference_ms: float          # feature extraction + inference wall time


def compute_reason_hash(features: dict[str, float], explanation: str,
                        model_version: str) -> str:
    """keccak256 of the canonical feature JSON + explanation + model version."""
    from web3 import Web3
    canonical = json.dumps(
        {"features": {k: round(float(v), 8) for k, v in sorted(features.items())},
         "explanation": explanation, "model_version": model_version},
        ensure_ascii=False, sort_keys=True)
    return Web3.keccak(text=canonical).hex()


def decide_on_window(model: GuardModel, prices: np.ndarray, breach_idx: int,
                     stop_price: float, threshold: float = 0.5) -> Decision:
    """Run features → model → verdict for one breached order.

    ``prices`` is the tick history up to now; only the first
    ``model.observe_window`` post-breach ticks are used, matching training.
    EXECUTE iff P(trend) >= threshold, else VETO. ``score`` is the confidence
    in the *posted* verdict, as AISignal expects.
    """
    t0 = time.perf_counter()
    feats = extract_features(prices, breach_idx, stop_price,
                             window=model.observe_window)
    p_exec = model.predict_proba_execute(feats)
    inference_ms = (time.perf_counter() - t0) * 1000.0

    if p_exec >= threshold:
        verdict, score = VERDICT_EXECUTE, int(round(p_exec * 1000))
    else:
        verdict, score = VERDICT_VETO, int(round((1.0 - p_exec) * 1000))
    explanation = generate_explanation(feats, verdict, score)
    reason_hash = compute_reason_hash(feats, explanation, model.model_version)
    return Decision(verdict=verdict, score=score, p_execute=p_exec, features=feats,
                    explanation=explanation, reason_hash="0x" + reason_hash
                    if not reason_hash.startswith("0x") else reason_hash,
                    inference_ms=inference_ms)


# ---------------------------------------------------------------------------
# Dry-run: two synthetic acts, no chain access, no transactions
# ---------------------------------------------------------------------------
def run_dry_run(model: GuardModel) -> None:
    from gen_data import generate_series

    acts = [
        ("第一幕 · 闪崩插针 (wick)", "wick", 20261116, VERDICT_VETO),
        ("第二幕 · 真实趋势反转 (trend)", "trend", 20261117, VERDICT_EXECUTE),
    ]
    print("=" * 72)
    print("AI GUARD DRY-RUN — local synthetic replay, no chain, no transactions")
    print(f"model: {model.model_version} | observe window: {model.observe_window} ticks")
    print("=" * 72)
    for title, scenario, seed, expected in acts:
        series = generate_series(scenario, np.random.default_rng(seed))
        prices, stop = series["prices"], series["stop_price"]
        breach_idx = series["breach_idx"]

        # Simulate the live loop: stream ticks, detect the breach the same
        # way GuardedStopReactive does (first price <= stop while monitoring).
        t_start = time.perf_counter()
        detected = next(i for i, p in enumerate(prices) if p <= stop)
        assert detected == breach_idx, (detected, breach_idx)
        decision = decide_on_window(model, prices, breach_idx, stop)
        wall_ms = (time.perf_counter() - t_start) * 1000.0

        trough = prices[breach_idx:breach_idx + model.observe_window].min()
        end = prices[breach_idx + model.observe_window - 1]
        ok = "✓ matches expectation" if decision.verdict == expected else \
            f"✗ UNEXPECTED (wanted {expected})"
        print(f"\n{title}")
        print(f"  base price {series['base_price']:.2f} | stop {stop:.2f} | "
              f"breach at tick {breach_idx} (price {prices[breach_idx]:.2f})")
        print(f"  window: trough {trough:.2f} "
              f"({(stop - trough) / stop * 100:.1f}% below stop), "
              f"window end {end:.2f}")
        print(f"  P(trend) = {decision.p_execute:.3f} → verdict: "
              f"{decision.verdict} (score {decision.score}/1000)  {ok}")
        print(f"  explanation: {decision.explanation}")
        print(f"  reasonHash: {decision.reason_hash}")
        print(f"  latency: feature+inference {decision.inference_ms:.2f} ms | "
              f"simulated breach→decision {model.observe_window:.0f}s of ticks "
              f"+ {decision.inference_ms:.1f} ms compute | replay wall {wall_ms:.1f} ms")
    print("\nDry-run complete: both acts decided locally; nothing was posted on-chain.")


# ---------------------------------------------------------------------------
# Live service (phase-2 testnet): poll events, post decisions
# ---------------------------------------------------------------------------
@dataclass
class TrackedOrder:
    order_id: int
    stop_price: float            # human units (converted from 1e18 scale)
    state: str = "monitoring"    # monitoring | pending | answered
    breach_idx: int = -1
    breach_time: float = 0.0


@dataclass
class GuardService:
    cfg: dict
    model: GuardModel
    orders: dict[int, TrackedOrder] = field(default_factory=dict)
    price_history: list[float] = field(default_factory=list)

    def __post_init__(self):
        from web3 import Web3
        rpc = self.cfg["BASE_SEPOLIA_RPC_URL"]
        if not rpc or not self.cfg["MOCK_POOL_ADDRESS"] or not self.cfg["AI_SIGNAL_ADDRESS"]:
            raise SystemExit(
                "live mode needs BASE_SEPOLIA_RPC_URL, MOCK_POOL_ADDRESS and "
                "AI_SIGNAL_ADDRESS in .env (see .env.example) — or use --dry-run")
        # Explicit timeout: without one, a throttled/hung RPC connection can
        # block the poll loop forever (seen in the first live acts, 2026-11-16).
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))
        if not self.w3.is_connected():
            raise SystemExit(f"cannot connect to RPC: {rpc}")
        self.pool = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.cfg["MOCK_POOL_ADDRESS"]),
            abi=MOCKPOOL_ABI)
        self.signal = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.cfg["AI_SIGNAL_ADDRESS"]),
            abi=AISIGNAL_ABI)
        self.account = self._load_wallet(self.cfg["WALLET_FILE"])
        self.decision_window = float(self.cfg["DECISION_WINDOW_SECONDS"])
        self.poll_interval = float(self.cfg["POLL_INTERVAL_SECONDS"])
        self.last_block = self.w3.eth.block_number

    @staticmethod
    def _load_wallet(path: str):
        """Load the testnet signer from the wallet JSON. Key never printed."""
        from eth_account import Account
        with open(path) as fh:
            blob = json.load(fh)
        key = blob.get("privateKey") or blob.get("private_key")
        if not key:
            raise SystemExit(f"wallet file {path} has no privateKey field")
        return Account.from_key(key)

    # -- event intake -------------------------------------------------------
    def _poll_events(self) -> None:
        latest = self.w3.eth.block_number
        if latest <= self.last_block:
            return
        # Base Sepolia's public RPC caps eth_getLogs at a 200-block range
        # (larger ranges return HTTP 413). Drain any backlog in <=150-block
        # steps so a slow poll cycle can never wedge the guard permanently.
        from_block = self.last_block + 1
        to_block = min(latest, self.last_block + 150)
        for log in self.pool.events.StopOrderPlaced.get_logs(
                from_block=from_block, to_block=to_block):
            oid = int(log["args"]["orderId"])
            self.orders[oid] = TrackedOrder(
                order_id=oid,
                stop_price=int(log["args"]["stopPrice"]) / PRICE_SCALE)
            print(f"[guard] order {oid} registered, stop "
                  f"{self.orders[oid].stop_price:.4f}")
        for log in self.pool.events.PriceUpdate.get_logs(
                from_block=from_block, to_block=to_block):
            price = int(log["args"]["price"]) / PRICE_SCALE
            self.price_history.append(price)
            self._on_price_tick(price)
        self.last_block = to_block

    def _on_price_tick(self, price: float) -> None:
        tick_idx = len(self.price_history) - 1
        for order in self.orders.values():
            if order.state == "monitoring" and price <= order.stop_price:
                order.state = "pending"
                order.breach_idx = tick_idx
                order.breach_time = time.time()
                print(f"[guard] order {order.order_id} BREACH at {price:.4f} "
                      f"(stop {order.stop_price:.4f}) — observing "
                      f"{self.model.observe_window} ticks")

    # -- decision + posting --------------------------------------------------
    def _maybe_decide(self) -> None:
        prices = np.asarray(self.price_history, dtype=float)
        for order in self.orders.values():
            if order.state != "pending":
                continue
            ticks_seen = len(prices) - order.breach_idx
            window_full = ticks_seen >= self.model.observe_window
            window_closing = (time.time() - order.breach_time
                              > self.decision_window - 10) and ticks_seen >= 5
            if not (window_full or window_closing):
                continue
            decision = decide_on_window(self.model, prices, order.breach_idx,
                                        order.stop_price)
            self._post_decision(order.order_id, decision)
            # Mirror the Reactive contract: VETO re-arms monitoring, EXECUTE
            # is terminal for this breach.
            order.state = "monitoring" if decision.verdict == VERDICT_VETO else "answered"
            if decision.verdict == VERDICT_VETO:
                order.breach_idx = -1

    def _post_decision(self, order_id: int, decision: Decision) -> str:
        verdict_enum = VERDICT_TO_ENUM[decision.verdict]
        reason = bytes.fromhex(decision.reason_hash.removeprefix("0x"))
        tx = self.signal.functions.postDecision(
            order_id, verdict_enum, decision.score, reason).build_transaction({
                "from": self.account.address,
                # "pending": the demo feeder blasts pre-nonced txs from the
                # same wallet; a confirmed-only nonce collides with them
                # ("nonce too low" retries, act wick order 3). The pending
                # count queues the decision right behind the feed burst.
                "nonce": self.w3.eth.get_transaction_count(
                    self.account.address, "pending"),
                "chainId": self.w3.eth.chain_id,
            })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"[guard] order {order_id}: {decision.verdict} "
              f"score={decision.score} posted, tx {tx_hash.hex()}")
        print(f"[guard]   {decision.explanation}")
        return tx_hash.hex()

    def run_forever(self) -> None:
        print(f"[guard] live mode: signer {self.account.address} "
              f"(testnet wallet), polling every {self.poll_interval}s",
              flush=True)
        while True:
            try:
                self._poll_events()
                self._maybe_decide()
            except Exception:
                # A transient RPC error must not kill the guard (it did exactly
                # that silently in the first live act, 2026-11-16: no decision
                # was posted and buffered stdout hid the cause). Log and continue.
                import traceback
                traceback.print_exc()
            time.sleep(self.poll_interval)


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="replay the two synthetic acts locally; no chain, no tx")
    ap.add_argument("--env", default=None, help="path to .env (default: ./.env)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    model = GuardModel(args.model)
    if args.dry_run:
        run_dry_run(model)
        return
    cfg = load_config(args.env)
    if args.model != DEFAULT_MODEL:
        cfg["MODEL_PATH"] = args.model
    GuardService(cfg=cfg, model=model).run_forever()


if __name__ == "__main__":
    main()
