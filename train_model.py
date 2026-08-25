"""

Trains the echo classifier (target vs. clutter) on the synthetic dataset,
evaluates it honestly, and saves the best model to disk so classify_echo.py
can load it later without retraining.
"""

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

from synthetic_echo_generator import generate_dataset

MODEL_PATH = "echo_classifier.joblib"
SCALER_PATH = "echo_scaler.joblib"


def load_training_data(csv_path: str = None) -> pd.DataFrame:
    """
    Load training data. If a real dataset CSV is provided (e.g. the UCI
    Sonar Mines-vs-Rocks set, or real tank recordings later), use that.
    Otherwise, fall back to our own synthetic generator.
    """
    if csv_path:
        return pd.read_csv(csv_path)
    return generate_dataset(n_samples=1000, seed=42)


def evaluate(name: str, model, X_test, y_test) -> dict:
    preds = model.predict(X_test)
    metrics = {
        "model": name,
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds),
        "recall": recall_score(y_test, preds),
        "f1": f1_score(y_test, preds),
    }
    print(f"\n{name}")
    for k, v in metrics.items():
        if k != "model":
            print(f"  {k:10s}: {v:.3f}")
    print("  confusion matrix [[TN FP] [FN TP]]:")
    print(" ", confusion_matrix(y_test, preds))
    return metrics


def main():
    df = load_training_data()
    X = df.drop(columns=["label"])
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X.to_numpy(), y.to_numpy(), test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    candidates = {
        "Logistic Regression": LogisticRegression(max_iter=1000),
        "Random Forest": RandomForestClassifier(n_estimators=200, random_state=42),
    }

    results = []
    fitted = {}
    for name, model in candidates.items():
        model.fit(X_train_scaled, y_train)
        fitted[name] = model
        results.append(evaluate(name, model, X_test_scaled, y_test))

    # Pick the best model by F1 (balances false alarms vs missed targets --
    # both matter here, so accuracy alone isn't the right thing to optimize).
    best = max(results, key=lambda r: r["f1"])
    best_name = best["model"]
    best_model = fitted[best_name]

    print(f"\nBest model: {best_name} (F1 = {best['f1']:.3f})")

    joblib.dump(best_model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"Saved model to {MODEL_PATH}, scaler to {SCALER_PATH}")


if __name__ == "__main__":
    main()