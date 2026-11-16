#!/usr/bin/env python3
"""Synthetic price-series generator for the AI guard.

Generates labelled 1 Hz price series in three shapes, matching PLAN.md §3
(concept A — the AI-guarded stop order):

  * ``wick``  — flash-crash wick: price knifes through the stop, stays below
    it for a few seconds, then rebounds and recovers most of the drop.
    Correct guard action: **VETO** (do not sell).
  * ``trend`` — real trend reversal: price breaks the stop and keeps going
    down (weak bounces only), ending the window far below the stop.
    Correct guard action: **EXECUTE** (sell).
  * ``chop``  — sideways noise around the stop: marginal, repeated dips
    below the stop line but no sustained move in either direction.
    Correct guard action: **VETO** (not a reversal; don't sell on noise).

Every series is generated around a base price ``p0`` with the stop line at
``STOP_RATIO * p0`` and carries its label, generation parameters and the
breach index (first tick where ``price <= stop``) so feature extraction and
evaluation are fully reproducible offline.

Reproducibility: all randomness flows from ``numpy.random.default_rng(seed)``
with a per-series child seed derived from the master seed, so re-running
with the same arguments produces byte-identical output.

Outputs (into ``data/`` by default):
  * ``dataset.npz``      — prices matrix (n_series, series_len), labels,
                           breach indices, stop/base prices, child seeds.
  * ``dataset_meta.csv`` — one row per series: scenario, binary target and
                           the generation parameters (audit / reproducibility).

Usage:
    python gen_data.py [--n-per-class 400] [--seed 42] [--out data]
"""

from __future__ import annotations

import argparse
import csv
import os

import numpy as np

# ---------------------------------------------------------------------------
# Series layout (shared with features.py / guard.py — keep in sync)
# ---------------------------------------------------------------------------
DT_SECONDS = 1.0          # one price tick per second
N_PRE = 60                # ticks before the staged move starts
N_POST = 60               # ticks of staged move / aftermath
SERIES_LEN = N_PRE + N_POST
STOP_RATIO = 0.95         # stop line = 95% of the base price

SCENARIOS = ("wick", "trend", "chop")
# Binary target for the guard model: 1 = EXECUTE (real trend), 0 = VETO.
BINARY_TARGET = {"wick": 0, "trend": 1, "chop": 0}


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def _ou_segment(rng: np.random.Generator, n: int, center: float, theta: float,
                sigma: float, start: float) -> np.ndarray:
    """Ornstein-Uhlenbeck (mean-reverting) segment — realistic sideways noise."""
    out = np.empty(n)
    x = start
    for i in range(n):
        x += theta * (center - x) + rng.normal(0.0, sigma * center)
        out[i] = x
    return out


def _anchored_path(rng: np.random.Generator, times: np.ndarray,
                   anchors_t: list[float], anchors_p: list[float],
                   noise_sigma: float) -> np.ndarray:
    """Piecewise-linear path through (t, price) anchors + gaussian noise."""
    base = np.interp(times, anchors_t, anchors_p)
    noise = rng.normal(0.0, noise_sigma, size=len(times))
    # Keep the very first point exactly on its anchor (continuity with pre-segment).
    noise[0] = 0.0
    return base + noise


def _gen_pre(rng: np.random.Generator, p0: float, stop: float) -> np.ndarray:
    """Calm pre-breach segment hovering near p0, ending safely above the stop."""
    for _ in range(50):
        seg = _ou_segment(rng, N_PRE, center=p0, theta=0.06, sigma=0.0016, start=p0)
        if seg[-1] > stop * 1.015 and seg.min() > stop * 1.005:
            return seg
    # Deterministic fallback: gentle sine-free drift line above the stop.
    return np.linspace(p0 * 0.998, p0 * 1.004, N_PRE)


def _gen_wick(rng: np.random.Generator, p0: float, stop: float,
              pre_end: float) -> tuple[np.ndarray, dict]:
    """Flash wick: fast deep dip below the stop, brief hold, fast rebound."""
    depth = rng.uniform(0.015, 0.10)             # trough depth below the stop (rel.)
    drop_dur = int(rng.integers(1, 5))           # 1–4 s to fall
    hold_dur = int(rng.integers(1, 13))          # 1–12 s pinned below the stop
    rebound_dur = int(rng.integers(3, 31))       # 3–30 s to bounce back (slow wicks
                                                 # may not finish inside the window)
    recovery = rng.uniform(0.55, 1.05)           # share of the drop recovered
    trough = stop * (1.0 - depth)
    recovered = trough + recovery * (pre_end - trough)
    t_trough = drop_dur
    t_hold_end = t_trough + hold_dur
    t_rebound_end = t_hold_end + rebound_dur
    times = np.arange(N_POST, dtype=float)
    post = _anchored_path(
        rng, times,
        [0, t_trough, t_hold_end, t_rebound_end, N_POST - 1],
        [pre_end, trough, trough * rng.uniform(0.995, 1.005), recovered,
         pre_end * rng.uniform(0.985, 1.01)],
        noise_sigma=p0 * 0.0012,
    )
    params = dict(depth_below_stop=depth, drop_dur=drop_dur, hold_dur=hold_dur,
                  rebound_dur=rebound_dur, recovery=recovery)
    return post, params


def _gen_trend(rng: np.random.Generator, p0: float, stop: float,
               pre_end: float) -> tuple[np.ndarray, dict]:
    """Real reversal: break, keep sliding, one weak bounce, end far below."""
    extra_drop = rng.uniform(0.04, 0.20)         # further fall below the stop (rel.)
    decline_dur = int(rng.integers(15, 56))      # 15–55 s of decline
    bounce_share = rng.uniform(0.0, 0.45)        # bounce recovers <=45% of the leg
                                                 # (strong bounces mimic wicks)
    end_low = stop * (1.0 - extra_drop)
    t_bounce = int(decline_dur * rng.uniform(0.45, 0.7))
    price_at_bounce_start = pre_end + (end_low - pre_end) * (t_bounce / decline_dur)
    bounce_top = price_at_bounce_start + bounce_share * (pre_end - price_at_bounce_start)
    times = np.arange(N_POST, dtype=float)
    post = _anchored_path(
        rng, times,
        [0, t_bounce, t_bounce + int(rng.integers(2, 6)), decline_dur, N_POST - 1],
        [pre_end, price_at_bounce_start, bounce_top, end_low,
         end_low * rng.uniform(0.99, 1.015)],
        noise_sigma=p0 * 0.0015,
    )
    params = dict(extra_drop=extra_drop, decline_dur=decline_dur,
                  bounce_share=bounce_share)
    return post, params


def _gen_chop(rng: np.random.Generator, p0: float, stop: float) -> tuple[np.ndarray, dict]:
    """Sideways noise straddling the stop: dips below it, never runs away.

    Generated as one OU segment (no pre/post split) centred a little above
    the stop. Rejection-sampled so the series *does* breach (otherwise there
    is nothing for the guard to decide on) but never deeply (a deep dip is a
    wick, not chop): min price must stay above ``stop * 0.94``.
    """
    for _ in range(200):
        center = p0 * rng.uniform(0.958, 0.99)
        seg = _ou_segment(rng, SERIES_LEN, center=center, theta=0.08,
                          sigma=0.0065, start=p0)
        below = seg <= stop
        if below.any() and seg.min() > stop * 0.94 and seg[-10:].mean() > stop * 0.94:
            return seg, dict(center_ratio=float(center / p0))
    # Fallback: hand-built shallow straddle.
    t = np.arange(SERIES_LEN, dtype=float)
    seg = stop * (1.01 + 0.018 * np.sin(t / 6.0) + rng.normal(0, 0.002, SERIES_LEN))
    return seg, dict(center_ratio=float(stop * 1.01 / p0))


# ---------------------------------------------------------------------------
# Series assembly
# ---------------------------------------------------------------------------
def generate_series(scenario: str, rng: np.random.Generator) -> dict:
    """Generate one labelled series. Returns prices + metadata dict."""
    p0 = float(rng.uniform(80.0, 120.0))
    stop = p0 * STOP_RATIO

    if scenario == "chop":
        prices, params = _gen_chop(rng, p0, stop)
    else:
        pre = _gen_pre(rng, p0, stop)
        if scenario == "wick":
            post, params = _gen_wick(rng, p0, stop, float(pre[-1]))
        elif scenario == "trend":
            post, params = _gen_trend(rng, p0, stop, float(pre[-1]))
        else:  # pragma: no cover - guarded by SCENARIOS
            raise ValueError(f"unknown scenario: {scenario}")
        prices = np.concatenate([pre, post])

    prices = np.maximum(prices, 1e-9)
    below = np.nonzero(prices <= stop)[0]
    breach_idx = int(below[0]) if len(below) else -1
    return dict(prices=prices, scenario=scenario, target=BINARY_TARGET[scenario],
                base_price=p0, stop_price=stop, breach_idx=breach_idx, params=params)


def generate_dataset(n_per_class: int = 400, seed: int = 42) -> dict:
    """Generate a balanced dataset of all three scenarios."""
    master = np.random.default_rng(seed)
    rows = []
    for scenario in SCENARIOS:
        for _ in range(n_per_class):
            child_seed = int(master.integers(0, 2**63 - 1))
            rng = np.random.default_rng(child_seed)
            row = generate_series(scenario, rng)
            row["child_seed"] = child_seed
            rows.append(row)
    return dict(rows=rows, seed=seed, n_per_class=n_per_class)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_dataset(dataset: dict, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    rows = dataset["rows"]
    npz_path = os.path.join(out_dir, "dataset.npz")
    np.savez_compressed(
        npz_path,
        prices=np.stack([r["prices"] for r in rows]),
        scenario=np.array([r["scenario"] for r in rows]),
        target=np.array([r["target"] for r in rows], dtype=np.int64),
        base_price=np.array([r["base_price"] for r in rows]),
        stop_price=np.array([r["stop_price"] for r in rows]),
        breach_idx=np.array([r["breach_idx"] for r in rows], dtype=np.int64),
        child_seed=np.array([r["child_seed"] for r in rows], dtype=np.int64),
        master_seed=np.int64(dataset["seed"]),
    )
    meta_path = os.path.join(out_dir, "dataset_meta.csv")
    param_keys = sorted({k for r in rows for k in r["params"]})
    with open(meta_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["idx", "scenario", "target_execute", "base_price",
                         "stop_price", "breach_idx", "child_seed"] + param_keys)
        for i, r in enumerate(rows):
            writer.writerow([i, r["scenario"], r["target"],
                             f"{r['base_price']:.4f}", f"{r['stop_price']:.4f}",
                             r["breach_idx"], r["child_seed"]]
                            + [r["params"].get(k, "") for k in param_keys])
    return npz_path, meta_path


def load_dataset(data_dir: str = "data") -> dict:
    """Load a dataset previously written by :func:`save_dataset`."""
    blob = np.load(os.path.join(data_dir, "dataset.npz"))
    return {k: blob[k] for k in blob.files}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-per-class", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data"))
    args = ap.parse_args()

    dataset = generate_dataset(n_per_class=args.n_per_class, seed=args.seed)
    npz_path, meta_path = save_dataset(dataset, args.out)
    rows = dataset["rows"]
    n_breach = sum(1 for r in rows if r["breach_idx"] >= 0)
    print(f"generated {len(rows)} series "
          f"({args.n_per_class}/class, seed={args.seed}), "
          f"{n_breach} with a stop breach")
    for scenario in SCENARIOS:
        sub = [r for r in rows if r["scenario"] == scenario]
        depths = [(r["stop_price"] - r["prices"].min()) / r["stop_price"] for r in sub]
        print(f"  {scenario:5s} n={len(sub):4d}  mean max depth below stop: "
              f"{np.mean(depths) * 100:.2f}%")
    print(f"wrote {npz_path}")
    print(f"wrote {meta_path}")


if __name__ == "__main__":
    main()
