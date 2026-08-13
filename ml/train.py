"""Train a baseline logistic regression win-probability model.

Loads data/processed/features.parquet (+ feature_schema.json), fits a
scaled logistic regression on the train split, evaluates on val/test
against a naive constant-probability baseline, and persists the fitted
pipeline to ml/models/winprob_v1.pkl.

Usage (from ml/, with .venv active):
    python train.py
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
MODELS_DIR = ML_DIR / "models"


def load_split(df: pd.DataFrame, features: list[str], target: str, split_name: str) -> tuple[pd.DataFrame, pd.Series]:
    subset = df[df["split"] == split_name]
    return subset[features], subset[target]


def evaluate(y_true: pd.Series, y_prob: np.ndarray, label: str) -> dict:
    metrics = {
        "auc": roc_auc_score(y_true, y_prob),
        "brier": brier_score_loss(y_true, y_prob),
        "log_loss": log_loss(y_true, y_prob, labels=[0, 1]),
        "accuracy": float(((y_prob >= 0.5).astype(int) == y_true).mean()),
        "n": int(len(y_true)),
    }
    print(
        f"  [{label:5s}] n={metrics['n']:5d}  AUC={metrics['auc']:.4f}  "
        f"Brier={metrics['brier']:.4f}  LogLoss={metrics['log_loss']:.4f}  "
        f"Acc={metrics['accuracy']:.4f}"
    )
    return metrics


def main() -> None:
    with open(DATA_PROCESSED / "feature_schema.json") as f:
        schema = json.load(f)
    features = schema["features"]
    target = schema["target"]

    df = pd.read_parquet(DATA_PROCESSED / "features.parquet")

    X_train, y_train = load_split(df, features, target, "train")
    X_val, y_val = load_split(df, features, target, "val")
    X_test, y_test = load_split(df, features, target, "test")

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )
    model.fit(X_train, y_train)

    print("Naive baseline (predict train home-win-rate for every game):")
    train_rate = y_train.mean()
    evaluate(y_val, np.full(len(y_val), train_rate), "val")
    evaluate(y_test, np.full(len(y_test), train_rate), "test")

    print("\nLogistic regression:")
    results = {}
    for split_name, X, y in [("train", X_train, y_train), ("val", X_val, y_val), ("test", X_test, y_test)]:
        y_prob = model.predict_proba(X)[:, 1]
        results[split_name] = evaluate(y, y_prob, split_name)

    coefs = pd.Series(model.named_steps["clf"].coef_[0], index=features).sort_values(key=abs, ascending=False)
    print("\nCoefficients (standardized, sorted by magnitude):")
    print(coefs.to_string())

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "winprob_v1.pkl"
    joblib.dump({"model": model, "features": features, "target": target}, model_path)
    print(f"\nsaved model -> {model_path.relative_to(REPO_ROOT)}")

    with open(MODELS_DIR / "winprob_v1_metrics.json", "w") as f:
        json.dump(
            {"baseline_train_rate": train_rate, "results": results, "coefficients": coefs.to_dict()},
            f,
            indent=2,
        )


if __name__ == "__main__":
    main()
