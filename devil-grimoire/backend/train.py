"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Training Script                                          ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Synthesizes labeled training data for all 6 anomaly classes, computes     ║
║  the 6 dimensionless features, and trains a 100-tree Random Forest.        ║
║  Output: sensortrust_model.joblib                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python train.py

This script is self-contained — it generates its own synthetic training data
by simulating each fault scenario mathematically. No external datasets needed.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.engine import (
    compute_features,
    FEATURE_ORDER,
    CLASS_LABELS,
    WINDOW_LONG,
)

# ─────────────────────────────────────────────────────────────────────────────
# TRAINING PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────
N_SAMPLES_PER_CLASS = 2000    # Samples per class → 12,000 total
N_SENSORS           = 5       # Peer sensors in the synthetic cohort
SEQUENCE_LENGTH     = 60      # Ticks of history per sample
AMBIENT_CENTER      = 24.0    # °C baseline
NOISE_SIGMA         = 0.08    # °C baseline noise
RANDOM_SEED         = 42

np.random.seed(RANDOM_SEED)


# ═══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC DATA GENERATION — one function per anomaly class
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_normal(n: int) -> list[dict]:
    """
    Generate Normal class samples.
    All sensors follow: X(t) = 24.0 + 0.5·sin(2π·t/3600) + N(0, 0.08²)
    No anomalies injected.
    """
    samples = []
    for _ in range(n):
        tick_offset = np.random.randint(0, 3600)
        # Generate 5 peer sensor histories
        all_sensors = []
        for s in range(N_SENSORS):
            ticks = np.arange(SEQUENCE_LENGTH) + tick_offset
            ambient = AMBIENT_CENTER + 0.5 * np.sin(2 * np.pi * ticks / 3600)
            noise = np.random.normal(0, NOISE_SIGMA, SEQUENCE_LENGTH)
            all_sensors.append(ambient + noise)
        
        # Target = sensor 0, peers = sensors 1..4
        target = all_sensors[0]
        peers = all_sensors[1:]
        features = compute_features(target, peers)
        features["label"] = 0  # Normal
        samples.append(features)
    return samples


def _generate_spike(n: int) -> list[dict]:
    """
    Generate Spike class samples.
    Inject a +8 to +15°C transient jump on the last tick of the target sensor.
    Peers remain normal → high peer_mad_score, high self_z_score.
    """
    samples = []
    for _ in range(n):
        tick_offset = np.random.randint(0, 3600)
        all_sensors = []
        for s in range(N_SENSORS):
            ticks = np.arange(SEQUENCE_LENGTH) + tick_offset
            ambient = AMBIENT_CENTER + 0.5 * np.sin(2 * np.pi * ticks / 3600)
            noise = np.random.normal(0, NOISE_SIGMA, SEQUENCE_LENGTH)
            all_sensors.append(ambient + noise)
        
        target = all_sensors[0].copy()
        # Inject spike on last tick: +8 to +15°C
        spike_mag = np.random.uniform(8.0, 15.0)
        target[-1] += spike_mag
        
        peers = all_sensors[1:]
        features = compute_features(target, peers)
        features["label"] = 1  # Spike
        samples.append(features)
    return samples


def _generate_drift(n: int) -> list[dict]:
    """
    Generate Drift class samples.
    Apply cumulative +0.02 to +0.04°C/tick linear trend on the target sensor.
    Results in high rolling_slope_norm and elevated self_z_score over time.
    """
    samples = []
    for _ in range(n):
        tick_offset = np.random.randint(0, 3600)
        all_sensors = []
        for s in range(N_SENSORS):
            ticks = np.arange(SEQUENCE_LENGTH) + tick_offset
            ambient = AMBIENT_CENTER + 0.5 * np.sin(2 * np.pi * ticks / 3600)
            noise = np.random.normal(0, NOISE_SIGMA, SEQUENCE_LENGTH)
            all_sensors.append(ambient + noise)
        
        target = all_sensors[0].copy()
        # Apply linear drift: +0.02 to +0.04 per tick
        drift_rate = np.random.uniform(0.02, 0.04)
        drift = np.arange(SEQUENCE_LENGTH) * drift_rate
        target += drift
        
        peers = all_sensors[1:]
        features = compute_features(target, peers)
        features["label"] = 2  # Drift
        samples.append(features)
    return samples


def _generate_env_event(n: int) -> list[dict]:
    """
    Generate Env Event (Environmental Event) class samples.
    All sensors (including target) shift together by +3 to +6°C in the last
    15-30 ticks. High cohort_consensus_ratio, moderate self_z_score.
    """
    samples = []
    for _ in range(n):
        tick_offset = np.random.randint(0, 3600)
        shift_mag = np.random.uniform(3.0, 6.0)
        shift_start = np.random.randint(SEQUENCE_LENGTH // 2, SEQUENCE_LENGTH - 10)
        
        all_sensors = []
        for s in range(N_SENSORS):
            ticks = np.arange(SEQUENCE_LENGTH) + tick_offset
            ambient = AMBIENT_CENTER + 0.5 * np.sin(2 * np.pi * ticks / 3600)
            noise = np.random.normal(0, NOISE_SIGMA, SEQUENCE_LENGTH)
            sensor = ambient + noise
            # Apply cohort shift to all sensors
            ramp = np.zeros(SEQUENCE_LENGTH)
            ramp_len = SEQUENCE_LENGTH - shift_start
            ramp[shift_start:] = np.linspace(0, shift_mag, ramp_len)
            sensor += ramp
            all_sensors.append(sensor)
        
        target = all_sensors[0]
        peers = all_sensors[1:]
        features = compute_features(target, peers)
        features["label"] = 3  # Env Event
        samples.append(features)
    return samples


def _generate_stuck_at(n: int) -> list[dict]:
    """
    Generate Stuck-At class samples.
    Target sensor freezes at a constant value (zero noise) for last 10-30 ticks.
    Results in near-zero variance_ratio and elevated peer_mad_score.
    """
    samples = []
    for _ in range(n):
        tick_offset = np.random.randint(0, 3600)
        all_sensors = []
        for s in range(N_SENSORS):
            ticks = np.arange(SEQUENCE_LENGTH) + tick_offset
            ambient = AMBIENT_CENTER + 0.5 * np.sin(2 * np.pi * ticks / 3600)
            noise = np.random.normal(0, NOISE_SIGMA, SEQUENCE_LENGTH)
            all_sensors.append(ambient + noise)
        
        target = all_sensors[0].copy()
        # Freeze the last 10-30 ticks at a constant value
        stuck_start = np.random.randint(SEQUENCE_LENGTH - 30, SEQUENCE_LENGTH - 5)
        stuck_value = np.random.uniform(23.0, 27.0)
        target[stuck_start:] = stuck_value
        
        peers = all_sensors[1:]
        features = compute_features(target, peers)
        features["label"] = 4  # Stuck-At
        samples.append(features)
    return samples


def _generate_excessive_noise(n: int) -> list[dict]:
    """
    Generate Excessive Noise class samples.
    Target sensor noise σ amplified by 5-15× for the last 15-30 ticks.
    Results in high variance_ratio and erratic self_z_score.
    """
    samples = []
    for _ in range(n):
        tick_offset = np.random.randint(0, 3600)
        all_sensors = []
        for s in range(N_SENSORS):
            ticks = np.arange(SEQUENCE_LENGTH) + tick_offset
            ambient = AMBIENT_CENTER + 0.5 * np.sin(2 * np.pi * ticks / 3600)
            noise = np.random.normal(0, NOISE_SIGMA, SEQUENCE_LENGTH)
            all_sensors.append(ambient + noise)
        
        target = all_sensors[0].copy()
        # Amplify noise in the last segment
        noise_start = np.random.randint(SEQUENCE_LENGTH - 30, SEQUENCE_LENGTH - 10)
        noise_mult = np.random.uniform(5.0, 15.0)
        ticks_noisy = np.arange(noise_start, SEQUENCE_LENGTH) + tick_offset
        ambient_noisy = AMBIENT_CENTER + 0.5 * np.sin(2 * np.pi * ticks_noisy / 3600)
        target[noise_start:] = ambient_noisy + np.random.normal(
            0, NOISE_SIGMA * noise_mult, SEQUENCE_LENGTH - noise_start
        )
        
        peers = all_sensors[1:]
        features = compute_features(target, peers)
        features["label"] = 5  # Excessive Noise
        samples.append(features)
    return samples


# ═══════════════════════════════════════════════════════════════════════════════
# REAL INTEL BERKELEY LAB DATASET AUGMENTATION
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_from_intel(intel_csv_path: str, n_samples_per_class: int = 1500) -> list[dict]:
    """
    Extract training samples directly from the real Intel Berkeley Research Lab dataset,
    combining real hardware noise distributions and room acoustics with fault injections.
    """
    if not os.path.exists(intel_csv_path):
        print(f"  [!] Intel dataset not found at {intel_csv_path}. Skipping.")
        return []

    print(f"\n[2/5] Extracting training samples from real Intel dataset ({intel_csv_path})...")
    df_intel = pd.read_csv(intel_csv_path)
    sensor_cols = [c for c in df_intel.columns if c.lower() not in ("timestamp", "time", "tick", "index", "label")]
    data_matrix = df_intel[sensor_cols].values
    total_ticks = len(data_matrix)
    num_sensors = len(sensor_cols)
    
    samples = []
    
    for class_idx, class_name in enumerate(CLASS_LABELS):
        print(f"  → Generating {n_samples_per_class} real Intel {class_name} samples...")
        for _ in range(n_samples_per_class):
            start_idx = np.random.randint(0, max(1, total_ticks - SEQUENCE_LENGTH))
            segment = data_matrix[start_idx : start_idx + SEQUENCE_LENGTH].copy()
            
            target_col = np.random.randint(0, num_sensors)
            target = segment[:, target_col].copy()
            peer_cols = [c for c in range(num_sensors) if c != target_col]
            peers = [segment[:, c].copy() for c in peer_cols]
            
            if class_name == "Normal":
                pass
            elif class_name == "Spike":
                target[-1] += np.random.uniform(8.0, 15.0)
            elif class_name == "Drift":
                drift_rate = np.random.uniform(0.02, 0.04)
                target += np.arange(SEQUENCE_LENGTH) * drift_rate
            elif class_name == "Env Event":
                shift_mag = np.random.uniform(3.0, 6.0)
                shift_start = np.random.randint(SEQUENCE_LENGTH // 2, SEQUENCE_LENGTH - 10)
                ramp_len = SEQUENCE_LENGTH - shift_start
                ramp = np.linspace(0, shift_mag, ramp_len)
                target[shift_start:] += ramp
                for p in peers:
                    p[shift_start:] += ramp
            elif class_name == "Stuck-At":
                stuck_len = np.random.randint(15, 30)
                target[-stuck_len:] = target[-stuck_len]
            elif class_name == "Excessive Noise":
                noise_mult = np.random.uniform(5.0, 15.0)
                noise_len = np.random.randint(15, 30)
                target[-noise_len:] += np.random.normal(0, 0.08 * noise_mult, noise_len)
            
            features = compute_features(target, peers)
            features["label"] = class_idx
            samples.append(features)
            
        print(f"    ✓ {n_samples_per_class} Intel {class_name} samples generated.")
        
    return samples


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TRAINING PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  DEVIL GRIMOIRE — Dual-Source Model Training Pipeline")
    print("  (Synthetic Physics Baseline + Real Intel Berkeley Lab Telemetry)")
    print("=" * 70)
    
    # ── Step 1: Generate synthetic training data ────────────────────────────
    print("\n[1/5] Generating baseline synthetic training data...")
    generators = [
        ("Normal",          _generate_normal),
        ("Spike",           _generate_spike),
        ("Drift",           _generate_drift),
        ("Env Event",       _generate_env_event),
        ("Stuck-At",        _generate_stuck_at),
        ("Excessive Noise", _generate_excessive_noise),
    ]
    
    all_samples = []
    for class_name, gen_func in generators:
        print(f"  → Generating {N_SAMPLES_PER_CLASS} synthetic {class_name} samples...")
        samples = gen_func(N_SAMPLES_PER_CLASS)
        all_samples.extend(samples)
        print(f"    ✓ {len(samples)} synthetic samples generated.")
    
    # ── Step 2: Add Real Intel Berkeley Research Lab Telemetry ─────────────
    base_dir = os.path.dirname(os.path.abspath(__file__))
    intel_csv = os.path.join(base_dir, "intel_dataset.csv")
    if not os.path.exists(intel_csv):
        intel_csv = os.path.join(base_dir, "my_formatted_data.csv")
    
    if os.path.exists(intel_csv):
        intel_samples = _generate_from_intel(intel_csv, n_samples_per_class=1500)
        all_samples.extend(intel_samples)
    
    print(f"\n  🎯 Total Combined Training Dataset: {len(all_samples)} samples")

    # ── Step 3: Build feature matrix ────────────────────────────────────────
    print(f"\n[3/5] Building feature matrix ({len(all_samples)} samples × {len(FEATURE_ORDER)} features)...")
    df = pd.DataFrame(all_samples)
    
    X = df[FEATURE_ORDER].values
    y = df["label"].values
    
    # Handle any NaN/inf values from edge cases
    X = np.nan_to_num(X, nan=0.0, posinf=50.0, neginf=-50.0)
    
    print(f"  Feature matrix shape: {X.shape}")
    print(f"  Class distribution:")
    for i, label in enumerate(CLASS_LABELS):
        count = np.sum(y == i)
        print(f"    {label}: {count} ({count/len(y)*100:.1f}%)")
    
    # ── Step 4: Train Random Forest ─────────────────────────────────────────
    print("\n[4/5] Training 100-tree Random Forest...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )
    
    model = RandomForestClassifier(
        n_estimators=100,       # 100 trees as specified
        max_depth=20,           # Prevent overfitting
        min_samples_split=5,    # Minimum samples to split a node
        min_samples_leaf=2,     # Minimum samples in leaf
        random_state=RANDOM_SEED,
        n_jobs=-1,              # Use all CPU cores
        class_weight="balanced" # Handle any class imbalance
    )
    
    model.fit(X_train, y_train)
    
    # ── Step 5: Evaluate ────────────────────────────────────────────────────
    print("\n[5/5] Evaluating model performance...")
    
    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
    print(f"  5-Fold CV Accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    
    # Test set evaluation
    y_pred = model.predict(X_test)
    print(f"\n  Test Set Classification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=CLASS_LABELS,
        digits=4
    ))
    
    # Feature importance
    print("  Feature Importance Rankings:")
    importances = model.feature_importances_
    for feat, imp in sorted(
        zip(FEATURE_ORDER, importances), key=lambda x: -x[1]
    ):
        bar = "█" * int(imp * 50)
        print(f"    {feat:25s} {imp:.4f} {bar}")
    
    # ── Save model ──────────────────────────────────────────────────────────
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "sensortrust_model.joblib"
    )
    joblib.dump(model, output_path)
    print(f"\n  ✅ Model saved to: {output_path}")
    print(f"  Model size: {os.path.getsize(output_path) / 1024:.1f} KB")
    print("=" * 70)


if __name__ == "__main__":
    main()
