"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Batch Evaluation Script                                  ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  CLI tool to evaluate hidden test CSVs against the trained model.          ║
║  Reads CSV files, computes features, classifies each row, and outputs      ║
║  detailed results with trust scores and XAI explanations.                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python evaluation.py --input test_data.csv --output results.csv
"""

import argparse
import pandas as pd
import numpy as np
import sys
import os

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.engine import (
    compute_features,
    classify_sensor,
    TrustScoreManager,
    detect_cohort_event,
    generate_xai_reason,
    FEATURE_ORDER,
    CLASS_LABELS,
    WINDOW_LONG,
)


def evaluate_csv(input_path: str, output_path: str = None):
    """
    Evaluate a CSV file through the DEVIL GRIMOIRE pipeline.
    
    Expected CSV format:
        Column 0: timestamp or tick index
        Columns 1..N: sensor readings (numeric)
    """
    print("=" * 70)
    print("  DEVIL GRIMOIRE — Batch Evaluation")
    print("=" * 70)
    
    # ── Load CSV ─────────────────────────────────────────────────────────────
    df = pd.read_csv(input_path)
    print(f"\n  Input: {input_path}")
    print(f"  Rows: {len(df)}, Columns: {list(df.columns)}")
    
    # Detect sensor columns
    sensor_cols = [
        col for col in df.columns
        if col.lower() not in ("timestamp", "time", "tick", "index", "label", "class")
        and pd.api.types.is_numeric_dtype(df[col])
    ]
    print(f"  Detected sensors: {sensor_cols}")
    
    # ── Initialize state ─────────────────────────────────────────────────────
    trust_mgr = TrustScoreManager()
    buffers = {col: [] for col in sensor_cols}
    missing_buffers = {col: [] for col in sensor_cols}
    results = []
    
    # ── Process each row ─────────────────────────────────────────────────────
    for tick, (_, row) in enumerate(df.iterrows()):
        readings = {}
        for col in sensor_cols:
            val = row[col]
            is_nan = pd.isna(val)
            missing_buffers[col].append(is_nan)
            if len(missing_buffers[col]) > WINDOW_LONG * 2:
                missing_buffers[col] = missing_buffers[col][-WINDOW_LONG * 2:]

            if is_nan:
                # Forward-fill
                val = buffers[col][-1] if buffers[col] else 0.0
            try:
                fval = float(val)
            except (ValueError, TypeError):
                fval = 0.0
            readings[col] = fval
            buffers[col].append(fval)
            if len(buffers[col]) > WINDOW_LONG * 2:
                buffers[col] = buffers[col][-WINDOW_LONG * 2:]
        
        # Compute features for each sensor
        for sid in sensor_cols:
            target = np.array(buffers[sid])
            peers = [
                np.array(buffers[other])
                for other in sensor_cols
                if other != sid and len(buffers[other]) > 0
            ]
            features = compute_features(target, peers, raw_missing=missing_buffers[sid])
            
            # Cohort detection
            cohort_bufs = {
                s: np.array(b) for s, b in buffers.items()
                if len(b) >= WINDOW_LONG
            }
            is_cohort, cohort_sids = detect_cohort_event(cohort_bufs)
            
            # Classify
            try:
                pred_class, proba = classify_sensor(features)
            except Exception:
                pred_class = "Normal"
                proba = np.zeros(len(CLASS_LABELS))
            
            if is_cohort and sid in cohort_sids:
                pred_class = "Env Event"
            
            trust = trust_mgr.update(sid, pred_class, is_cohort and sid in cohort_sids)
            xai = generate_xai_reason(sid, pred_class, features, is_cohort, cohort_sids, trust)
            
            results.append({
                "tick": tick,
                "sensor_id": sid,
                "value": readings[sid],
                **{f: round(features[f], 6) for f in FEATURE_ORDER},
                "predicted_class": pred_class,
                "trust_score": round(trust, 2),
                "xai_reason": xai,
            })
        
        if tick % 100 == 0:
            print(f"  Processing tick {tick}/{len(df)}...")
    
    # ── Output results ───────────────────────────────────────────────────────
    results_df = pd.DataFrame(results)
    
    if output_path:
        results_df.to_csv(output_path, index=False)
        print(f"\n  ✅ Results saved to: {output_path}")
    
    # Summary statistics
    print(f"\n  Classification Summary:")
    class_counts = results_df["predicted_class"].value_counts()
    for cls, count in class_counts.items():
        pct = count / len(results_df) * 100
        print(f"    {cls:20s}: {count:6d} ({pct:.1f}%)")
    
    print(f"\n  Trust Score Summary:")
    for sid in sensor_cols:
        sensor_data = results_df[results_df["sensor_id"] == sid]
        if len(sensor_data) > 0:
            avg_trust = sensor_data["trust_score"].mean()
            min_trust = sensor_data["trust_score"].min()
            print(f"    {sid}: avg={avg_trust:.1f}%, min={min_trust:.1f}%")
    
    print("=" * 70)
    return results_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DEVIL GRIMOIRE Batch Evaluator")
    parser.add_argument("--input", "-i", required=True, help="Input CSV file path")
    parser.add_argument("--output", "-o", default=None, help="Output CSV file path")
    args = parser.parse_args()
    
    evaluate_csv(args.input, args.output)
