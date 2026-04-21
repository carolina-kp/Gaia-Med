"""
train.py — standalone script to train and save the GaiaMed model.

Usage (from project root):
    python backend/train.py

Saves models/rf_model.pkl and prints accuracy + ROC-AUC.
"""
import sys
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.model import train_and_save
from backend.config import MODEL_PATH


def main():
    print("Training GaiaMed RandomForest...")
    result = train_and_save()

    metrics = result["metrics"]
    print(f"\n  Test accuracy : {metrics['test_accuracy']:.4f}")
    print(f"  Test ROC-AUC  : {metrics['test_roc_auc']:.4f}")

    print("\nTop-10 feature importances:")
    for i, (feat, imp) in enumerate(result["feature_importance"].items()):
        if i >= 10:
            break
        print(f"  {feat:<30s} {imp:.4f}")

    print(f"\nModel saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
