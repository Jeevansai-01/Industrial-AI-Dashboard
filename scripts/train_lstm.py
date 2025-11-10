import os, sys, numpy as np
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from models.lstm import train_and_save

ROOT = os.path.dirname(os.path.dirname(__file__))
csv_path = os.path.join(ROOT, "data", "history.csv")
artifacts_dir = os.path.join(ROOT, "artifacts")

if not os.path.exists(csv_path):
    raise FileNotFoundError(f"Training CSV not found at: {csv_path}")

# Expect 3 columns: temperature, pressure, motor_speed
X = np.loadtxt(csv_path, delimiter=",", skiprows=1, usecols=(2,3,4))
if X.ndim == 1:
    X = X.reshape(-1, 3)

seq_len = 24
if len(X) < seq_len:
    raise ValueError(f"Need at least seq_len={seq_len} rows, got {len(X)}")

train_and_save(X, seq_len=seq_len, epochs=15, batch_size=64, artifacts_dir=artifacts_dir)
print(f"Saved artifacts to {artifacts_dir}")
