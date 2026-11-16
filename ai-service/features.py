#!/usr/bin/env python3
"""Feature extraction for the AI guard — shared by training and live inference.

The guard sees a 1 Hz price series and a stop line. Once the price breaches
the stop (``price <= stop``), the features summarise the *shape* of what
happens next, over the post-breach observation window:

========================= =====================================================
feature                   meaning
========================= =====================================================
drawdown_depth            deepest dip below the stop, relative to the stop
drop_from_pre             total drop from the pre-breach level to the trough
breach_duration_ratio     share of the post window spent below the stop
longest_below_s           longest consecutive run below the stop (seconds)
time_to_trough_s          seconds from breach to the trough
rebound_ratio             share of the drop recovered by the window's end
rebound_speed             fastest 5 s rise after the trough, relative to drop
recovery_time_s           seconds from trough back above the stop (window if never)
end_below_stop            how far below the stop the window ends (signed)
post_slope                normalised linear slope of the post-breach window
vol_pre / vol_post        return volatility before / after the breach
vol_shock                 vol_post / vol_pre (volatility regime change)
volume_proxy              sum |returns| after the breach (activity proxy)
volume_proxy_ratio        volume proxy after vs. before the breach
n_stop_crossings          how often the price crosses the stop in the window
========================= =====================================================

Everything is relative (unit-free), so the same code works for the synthetic
series in ``gen_data.py`` and for live ``PriceUpdate`` ticks in ``guard.py``.
"""

from __future__ import annotations

import numpy as np

FEATURE_NAMES = [
    "drawdown_depth",
    "drop_from_pre",
    "breach_duration_ratio",
    "longest_below_s",
    "time_to_trough_s",
    "rebound_ratio",
    "rebound_speed",
    "recovery_time_s",
    "end_below_stop",
    "post_slope",
    "vol_pre",
    "vol_post",
    "vol_shock",
    "volume_proxy",
    "volume_proxy_ratio",
    "n_stop_crossings",
]

PRE_WINDOW = 30        # ticks of pre-breach context used for vol baselines
REBOUND_SPAN = 5       # ticks over which rebound speed is measured


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def extract_features(prices: np.ndarray, breach_idx: int, stop_price: float,
                     window: int | None = None) -> dict[str, float]:
    """Extract the guard feature vector for one breached series.

    ``prices`` is the full tick series, ``breach_idx`` the first index with
    ``price <= stop_price``. ``window`` caps how many post-breach ticks are
    used (``None`` = everything available) — the live guard passes its
    observation-window size here so training and inference see the same
    feature semantics.
    """
    prices = np.asarray(prices, dtype=float)
    pre = prices[max(0, breach_idx - PRE_WINDOW):breach_idx]
    post = prices[breach_idx:] if window is None else prices[breach_idx:breach_idx + window]
    if len(post) == 0:
        raise ValueError("empty post-breach window")
    if len(pre) == 0:
        pre = prices[:breach_idx + 1]

    pre_level = float(np.mean(pre[-min(len(pre), 10):]))     # level just before breach
    trough_idx = int(np.argmin(post))
    trough = float(post[trough_idx])
    last = float(post[-1])
    drop = max(pre_level - trough, 1e-12)

    below = post <= stop_price
    # Recovery: first tick after the trough that is back above the stop.
    recovery_time = float(len(post) - trough_idx)
    for j in range(trough_idx + 1, len(post)):
        if post[j] > stop_price:
            recovery_time = float(j - trough_idx)
            break
    # Fastest rise over REBOUND_SPAN ticks after the trough.
    rebound_speed = 0.0
    tail = post[trough_idx:]
    if len(tail) > REBOUND_SPAN:
        rises = (tail[REBOUND_SPAN:] - tail[:-REBOUND_SPAN]) / drop
        rebound_speed = float(max(rises.max(), 0.0))

    pre_ret = np.diff(np.log(np.maximum(pre, 1e-12))) if len(pre) > 2 else np.array([0.0])
    post_ret = np.diff(np.log(np.maximum(post, 1e-12))) if len(post) > 2 else np.array([0.0])
    vol_pre = float(np.std(pre_ret)) if len(pre_ret) else 0.0
    vol_post = float(np.std(post_ret)) if len(post_ret) else 0.0
    vol_proxy_pre = float(np.sum(np.abs(pre_ret))) / max(len(pre_ret), 1)
    vol_proxy_post = float(np.sum(np.abs(post_ret)))

    # Slope of the post window, normalised per-second relative to price level.
    if len(post) > 2:
        t = np.arange(len(post), dtype=float)
        slope = float(np.polyfit(t, post, 1)[0]) / max(pre_level, 1e-12)
    else:
        slope = 0.0

    crossings = int(np.sum(below[1:] != below[:-1])) if len(below) > 1 else 0

    return {
        "drawdown_depth": float((stop_price - trough) / stop_price),
        "drop_from_pre": float(drop / pre_level),
        "breach_duration_ratio": float(np.mean(below)),
        "longest_below_s": float(_longest_run(below)),
        "time_to_trough_s": float(trough_idx),
        "rebound_ratio": float((last - trough) / drop),
        "rebound_speed": rebound_speed,
        "recovery_time_s": recovery_time,
        "end_below_stop": float((stop_price - last) / stop_price),
        "post_slope": slope,
        "vol_pre": vol_pre,
        "vol_post": vol_post,
        "vol_shock": float(vol_post / vol_pre) if vol_pre > 1e-12 else 0.0,
        "volume_proxy": vol_proxy_post,
        "volume_proxy_ratio": float(vol_proxy_post / vol_proxy_pre) if vol_proxy_pre > 1e-12 else 0.0,
        "n_stop_crossings": float(crossings),
    }


def feature_vector(features: dict[str, float]) -> np.ndarray:
    """Dict → ordered vector, in ``FEATURE_NAMES`` order."""
    return np.array([features[name] for name in FEATURE_NAMES], dtype=float)


def build_feature_matrix(prices: np.ndarray, breach_idx: np.ndarray,
                         stop_price: np.ndarray, window: int | None = None) -> np.ndarray:
    """Vectorised convenience wrapper used by train.py."""
    rows = []
    for i in range(len(prices)):
        feats = extract_features(prices[i], int(breach_idx[i]), float(stop_price[i]),
                                 window=window)
        rows.append(feature_vector(feats))
    return np.stack(rows)
