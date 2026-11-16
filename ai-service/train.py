#!/usr/bin/env python3
"""Train the AI guard's wick-vs-trend classifier.

Pipeline: synthetic dataset (``gen_data.py``) → features (``features.py``,
computed on the same post-breach observation window the live guard uses) →
scikit-learn gradient-boosting binary classifier:

    target 1 = EXECUTE  (scenario ``trend`` — real reversal, sell)
    target 0 = VETO     (scenarios ``wick`` + ``chop`` — do not sell)

Outputs:
  * ``model.joblib``   — bundle {model, feature_names, observe_window,
                         model_version, trained_on} loaded by guard.py.
  * ``evaluation.md``  — held-out metrics: accuracy, per-class precision /
                         recall, per-scenario correct-action rates, confusion
                         matrix and feature importances.

Usage:
    python gen_data.py            # if data/dataset.npz does not exist yet
    python train.py [--data data] [--model-out model.joblib]
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (accuracy_score, confusion_matrix,
                             precision_recall_fscore_support)
from sklearn.model_selection import train_test_split

from features import FEATURE_NAMES, build_feature_matrix
from gen_data import load_dataset

# The live guard decides after this many post-breach ticks (seconds at 1 Hz),
# well inside the Reactive contract's 120 s decision window. Training uses
# the same window so features mean the same thing in both places.
OBSERVE_WINDOW = 30

MODEL_VERSION = "guard-gbdt-v1 (synthetic, seed 42)"


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=os.path.join(here, "data"))
    ap.add_argument("--model-out", default=os.path.join(here, "model.joblib"))
    ap.add_argument("--eval-out", default=os.path.join(here, "evaluation.md"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    blob = load_dataset(args.data)
    prices, scenario, target = blob["prices"], blob["scenario"], blob["target"]
    breach_idx, stop_price = blob["breach_idx"], blob["stop_price"]

    usable = breach_idx >= 0
    if not usable.all():
        print(f"dropping {int((~usable).sum())} series without a stop breach")
    X = build_feature_matrix(prices[usable], breach_idx[usable],
                             stop_price[usable], window=OBSERVE_WINDOW)
    y = target[usable].astype(int)
    scen = scenario[usable]

    X_train, X_test, y_train, y_test, scen_train, scen_test = train_test_split(
        X, y, scen, test_size=0.25, random_state=args.seed, stratify=y)

    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=None,
        min_samples_leaf=20, random_state=args.seed)
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, pred)
    prec, rec, f1, support = precision_recall_fscore_support(
        y_test, pred, labels=[0, 1], zero_division=0)
    cm = confusion_matrix(y_test, pred, labels=[0, 1])  # rows=true, cols=pred

    # Per-scenario correct-action rate: EXECUTE only for trend, VETO otherwise.
    scen_rates = {}
    for name in ("wick", "trend", "chop"):
        mask = scen_test == name
        if mask.sum():
            want = 1 if name == "trend" else 0
            scen_rates[name] = (float(np.mean(pred[mask] == want)), int(mask.sum()))

    importances = _permutation_importance(model, X_test, y_test, args.seed)

    bundle = dict(model=model, feature_names=FEATURE_NAMES,
                  observe_window=OBSERVE_WINDOW, model_version=MODEL_VERSION,
                  trained_on=f"{len(X_train)} synthetic series "
                             f"(seed {args.seed}, window {OBSERVE_WINDOW})")
    joblib.dump(bundle, args.model_out)

    report = _render_report(acc, prec, rec, f1, support, cm, scen_rates,
                            importances, len(X_train), len(X_test),
                            float(np.mean((proba >= 0.5).astype(int) == y_test)))
    with open(args.eval_out, "w") as fh:
        fh.write(report)

    print(f"train n={len(X_train)}  test n={len(X_test)}")
    print(f"test accuracy: {acc:.4f}")
    print(f"recall  VETO (y=0): {rec[0]:.4f}   EXECUTE (y=1): {rec[1]:.4f}")
    for name, (rate, n) in scen_rates.items():
        print(f"  scenario {name:5s}: correct-action rate {rate:.4f} (n={n})")
    print(f"confusion matrix [[TN, FP], [FN, TP]]: {cm.tolist()}")
    print(f"wrote {args.model_out}")
    print(f"wrote {args.eval_out}")


def _permutation_importance(model, X, y, seed: int, n_repeats: int = 10) -> np.ndarray:
    """Permutation importance on the held-out set (model-agnostic, robust)."""
    from sklearn.inspection import permutation_importance
    result = permutation_importance(model, X, y, n_repeats=n_repeats,
                                    random_state=seed, scoring="accuracy")
    return result.importances_mean


def _render_report(acc, prec, rec, f1, support, cm, scen_rates, importances,
                   n_train: int, n_test: int, proba_acc: float) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# AI Guard — model evaluation",
        "",
        f"- Model: `{MODEL_VERSION}` — scikit-learn `HistGradientBoostingClassifier`",
        f"- Data: synthetic series from `gen_data.py` (wick / trend / chop), "
        f"features from the first {OBSERVE_WINDOW} post-breach ticks "
        f"(the same window the live guard uses)",
        f"- Split: train {n_train} / held-out test {n_test} (stratified, seed 42)",
        f"- Target: 1 = EXECUTE (trend reversal), 0 = VETO (wick + chop)",
        f"- Generated: {now}",
        "",
        "## Headline metrics (held-out test set)",
        "",
        f"- **Accuracy: {acc:.4f}**",
        f"- Probability-threshold (0.5) accuracy check: {proba_acc:.4f}",
        "",
        "| class | precision | recall | F1 | support |",
        "|---|---|---|---|---|",
        f"| VETO (0) | {prec[0]:.4f} | **{rec[0]:.4f}** | {f1[0]:.4f} | {support[0]} |",
        f"| EXECUTE (1) | {prec[1]:.4f} | **{rec[1]:.4f}** | {f1[1]:.4f} | {support[1]} |",
        "",
        "Recall is the number that matters per class: VETO recall = share of "
        "non-reversals where the position was kept; EXECUTE recall = share of "
        "real reversals where the stop actually fired.",
        "",
        "## Correct-action rate by scenario",
        "",
        "| scenario | correct action | rate | n |",
        "|---|---|---|---|",
    ]
    for name in ("wick", "trend", "chop"):
        if name in scen_rates:
            rate, n = scen_rates[name]
            action = "EXECUTE" if name == "trend" else "VETO"
            lines.append(f"| {name} | {action} | {rate:.4f} | {n} |")
    lines += [
        "",
        "## Confusion matrix",
        "",
        "Rows = true class, columns = predicted class.",
        "",
        "|  | pred VETO | pred EXECUTE |",
        "|---|---|---|",
        f"| true VETO | {cm[0][0]} | {cm[0][1]} |",
        f"| true EXECUTE | {cm[1][0]} | {cm[1][1]} |",
        "",
        "## Feature importance (permutation, held-out set)",
        "",
        "| feature | importance (accuracy drop) |",
        "|---|---|",
    ]
    order = np.argsort(importances)[::-1]
    for i in order:
        lines.append(f"| {FEATURE_NAMES[i]} | {importances[i]:.4f} |")
    lines += [
        "",
        "## Notes",
        "",
        "- Synthetic-data model: it demonstrates the guard loop and gives the "
        "demo reproducible numbers; it is not trained on real market data.",
        "- The costly error is a false EXECUTE on a wick (selling the bottom); "
        "the threshold in `guard.py` can be raised above 0.5 to trade EXECUTE "
        "recall for fewer false executions.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
