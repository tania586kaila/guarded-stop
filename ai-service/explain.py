#!/usr/bin/env python3
"""Human-readable decision explanations — template-based, zero API dependency.

PLAN.md §3 lists an *optional* enhancement: use a free LLM tier to phrase
each decision in one human sentence, hashing the text on-chain alongside the
features. This module implements the always-available path:

  * :func:`generate_explanation` — deterministic template explanation built
    from the feature vector. This is what runs in production / the demo.
  * :class:`LLMExplainer` — the interface an optional LLM-backed explainer
    would implement. It is a stub: no paid (or any) API is called, and the
    guard falls back to the template whenever an explainer is absent or
    disabled. Wire a real implementation behind this interface later without
    touching guard logic.

The explanation string is part of the ``reasonHash`` preimage in guard.py,
so every on-chain decision can be reproduced and audited off-chain.
"""

from __future__ import annotations

VERDICT_EXECUTE = "EXECUTE"
VERDICT_VETO = "VETO"
VERDICT_HOLD = "HOLD"


def generate_explanation(features: dict[str, float], verdict: str, score: int) -> str:
    """One-sentence template explanation of a guard decision.

    ``score`` is the model confidence in the chosen verdict, 0..1000
    (the same value posted to AISignal).
    """
    depth = features["drawdown_depth"] * 100
    below = features["longest_below_s"]
    rebound = features["rebound_ratio"] * 100
    recovery = features["recovery_time_s"]
    end_below = features["end_below_stop"] * 100
    conf = score / 10.0  # 0..100 %

    if verdict == VERDICT_VETO:
        return (
            f"触线后最深跌至止损线下 {depth:.1f}%，但 {recovery:.0f}s 内价格回到止损线上方、"
            f"窗口结束时已收复跌幅的 {rebound:.0f}%，形态符合闪崩插针（最长连续位于线下 "
            f"{below:.0f}s），判定 VETO 保仓（置信度 {conf:.0f}%）。"
            f" Wick pattern: dipped {depth:.1f}% below the stop, recovered "
            f"{rebound:.0f}% of the drop within {recovery:.0f}s — VETO, keep the position."
        )
    if verdict == VERDICT_EXECUTE:
        return (
            f"触线后持续下行，窗口结束时仍位于止损线下 {end_below:.1f}%，最长连续位于线下 "
            f"{below:.0f}s、反弹仅收复跌幅的 {max(rebound, 0.0):.0f}%，形态符合真实趋势反转，"
            f"判定 EXECUTE 执行止损（置信度 {conf:.0f}%）。"
            f" Trend reversal: still {end_below:.1f}% below the stop at window end, "
            f"rebound only {max(rebound, 0.0):.0f}% — EXECUTE the stop."
        )
    return (
        f"触线后形态不明确（最深 {depth:.1f}%、收复 {rebound:.0f}%），判定 HOLD 继续待决"
        f"（置信度 {conf:.0f}%）。 Ambiguous shape — HOLD inside the decision window."
    )


class LLMExplainer:
    """Interface stub for an optional LLM-backed explainer (NOT implemented).

    A future implementation could call a free-tier model to rephrase the
    template text. It must never be on the critical path: the guard calls
    :meth:`explain` only if an instance is explicitly injected, and any
    failure must fall back to :func:`generate_explanation`.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "LLMExplainer is an interface stub — the guard uses template "
            "explanations (generate_explanation) and needs no API key."
        )

    def explain(self, features: dict[str, float], verdict: str, score: int) -> str:
        raise NotImplementedError
