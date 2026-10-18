"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Hackathon Dataset Generator                               ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Synthesizes a realistic multi-sensor environmental stream meeting all      ║
║  specifications of the "AI-Based Sensor Trust & Drift" problem statement:   ║
║                                                                              ║
║  1. Diurnal physical ambient trend + thermal noise baseline                  ║
║  2. 5 virtual sensor channels tracking the same environment                  ║
║  3. Injected labeled fault scenarios:                                        ║
║     - Sudden transient spikes (EMI / glitch)                                 ║
║     - Monotonic offset drift & slow degradation                              ║
║     - Stuck-at / frozen values (ADC latch failure)                           ║
║     - Excessive high-frequency noise (hardware degradation)                  ║
║     - Intermittent dropouts / missing data (NaNs)                            ║
║     - Gain error (calibration scaling drift)                                 ║
║  4. Genuine multi-sensor environmental events (Heatwave / HVAC surge)        ║
║     affecting cohorts simultaneously to test false-alarm suppression.         ║
║                                                                              ║
║  Outputs:                                                                    ║
║     - hackathon_challenge_data.csv (input stream for evaluation/dashboard)   ║
║     - hackathon_ground_truth.csv (evaluation labels & recommended actions)   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import os

def generate_hackathon_dataset(total_ticks=1500, random_seed=42):
    np.random.seed(random_seed)
    sensors = ["TEMP-01", "TEMP-02", "TEMP-03", "TEMP-04", "TEMP-05"]
    
    # ── 1. Realistic Diurnal Ambient Trend ──────────────────────────────────────
    # A(t) = 24.0°C + 1.2 * sin(2π * t / 720) (simulates daytime warming/cooling cycle)
    ticks = np.arange(total_ticks)
    ambient_trend = 24.0 + 1.2 * np.sin(2 * np.pi * ticks / 720.0)
    
    # ── 2. Initialize Sensor Signals with Baseline Gaussian Noise ───────────────
    # Each sensor has slight physical manufacturing variance (+/- 0.05°C) and noise sigma = 0.08°C
    sensor_data = {}
    offsets = {"TEMP-01": 0.02, "TEMP-02": -0.01, "TEMP-03": 0.04, "TEMP-04": -0.03, "TEMP-05": 0.01}
    
    for s in sensors:
        noise = np.random.normal(0, 0.08, total_ticks)
        sensor_data[s] = ambient_trend + offsets[s] + noise

    # Ground truth records
    ground_truth = []
    
    # Helper to log ground truth
    def log_gt(t, s, fault, is_fault, is_event, action):
        ground_truth.append({
            "tick": t,
            "sensor_id": s,
            "fault_type": fault,
            "is_fault": is_fault,
            "is_genuine_event": is_event,
            "recommended_action": action
        })

    # Default ground truth for nominal operation
    for t in range(total_ticks):
        for s in sensors:
            log_gt(t, s, "Normal", False, False, "None (Nominal)")

    # ── 3. Scenario Injections (Exactly matching Hackathon Specifications) ──────
    
    # Scenario A: Sudden Spikes on TEMP-02 (Ticks 150 - 200)
    # Transient single-tick outliers of +8°C to +12°C at specific ticks
    spike_ticks = [160, 175, 188, 195]
    for st in spike_ticks:
        sensor_data["TEMP-02"][st] += np.random.uniform(9.0, 13.0)
        # Update ground truth
        for entry in ground_truth:
            if entry["tick"] == st and entry["sensor_id"] == "TEMP-02":
                entry["fault_type"] = "Spike"
                entry["is_fault"] = True
                entry["recommended_action"] = "Inspect shielding / Transient noise filter"

    # Scenario B: Gradual Monotonic Drift on TEMP-04 (Ticks 250 - 450)
    # Slow calibration loss accumulating +0.035°C per tick
    drift_rate = 0.035
    for t in range(250, 451):
        accumulated_drift = (t - 250) * drift_rate
        sensor_data["TEMP-04"][t] += accumulated_drift
        for entry in ground_truth:
            if entry["tick"] == t and entry["sensor_id"] == "TEMP-04":
                entry["fault_type"] = "Drift"
                entry["is_fault"] = True
                entry["recommended_action"] = "Recalibration required"

    # Scenario C: Genuine Environmental Event (Ticks 500 - 650)
    # Heatwave / HVAC failure causing multi-sensor ramp of +4.5°C across 4 sensors
    # Must NOT be flagged as sensor fault!
    for t in range(500, 651):
        ramp_progress = min(1.0, (t - 500) / 40.0)
        env_offset = 4.5 * ramp_progress
        for s in ["TEMP-01", "TEMP-02", "TEMP-04", "TEMP-05"]:
            sensor_data[s][t] += env_offset
            for entry in ground_truth:
                if entry["tick"] == t and entry["sensor_id"] == s:
                    entry["fault_type"] = "Env Event"
                    entry["is_fault"] = False
                    entry["is_genuine_event"] = True
                    entry["recommended_action"] = "GENUINE HAZARD: Inspect HVAC / Environment"

    # Scenario D: Stuck-At / Frozen Sensor on TEMP-03 (Ticks 700 - 850)
    # ADC latch failure: Sensor freezes at exactly 25.10°C with 0 noise
    frozen_val = 25.10
    for t in range(700, 851):
        sensor_data["TEMP-03"][t] = frozen_val
        for entry in ground_truth:
            if entry["tick"] == t and entry["sensor_id"] == "TEMP-03":
                entry["fault_type"] = "Stuck-At"
                entry["is_fault"] = True
                entry["recommended_action"] = "Sensor replacement required (ADC latch fault)"

    # Scenario E: Excessive High-Frequency Noise on TEMP-05 (Ticks 900 - 1050)
    # Sensor component degradation: noise sigma multiplied by 12x
    for t in range(900, 1051):
        extra_noise = np.random.normal(0, 0.08 * 12.0)
        sensor_data["TEMP-05"][t] += extra_noise
        for entry in ground_truth:
            if entry["tick"] == t and entry["sensor_id"] == "TEMP-05":
                entry["fault_type"] = "Excessive Noise"
                entry["is_fault"] = True
                entry["recommended_action"] = "Inspect grounding & physical connection"

    # Scenario F: Intermittent Dropouts / Missing Data on TEMP-01 (Ticks 1100 - 1200)
    # Packet loss / telemetry failure producing NaNs
    dropout_ticks = [1105, 1106, 1112, 1120, 1121, 1122, 1135, 1148, 1150, 1162, 1175, 1176]
    for dt in dropout_ticks:
        sensor_data["TEMP-01"][dt] = np.nan
        for entry in ground_truth:
            if entry["tick"] == dt and entry["sensor_id"] == "TEMP-01":
                entry["fault_type"] = "Dropout"
                entry["is_fault"] = True
                entry["recommended_action"] = "Telemetry network check / Forward-fill active"

    # Scenario G: Gain / Scaling Error on TEMP-02 (Ticks 1250 - 1400)
    # Multiplier calibration error (amplitude multiplied by 1.6x)
    for t in range(1250, 1401):
        delta = sensor_data["TEMP-02"][t] - 24.0
        sensor_data["TEMP-02"][t] = 24.0 + (delta * 1.6)
        for entry in ground_truth:
            if entry["tick"] == t and entry["sensor_id"] == "TEMP-02":
                entry["fault_type"] = "Gain Error / Drift"
                entry["is_fault"] = True
                entry["recommended_action"] = "Gain recalibration required"

    # ── 4. Save Challenge Dataset ───────────────────────────────────────────────
    df_data = pd.DataFrame({"timestamp": ticks})
    for s in sensors:
        df_data[s] = np.round(sensor_data[s], 4)
        
    df_gt = pd.DataFrame(ground_truth)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "hackathon_challenge_data.csv")
    gt_path = os.path.join(base_dir, "hackathon_ground_truth.csv")
    
    df_data.to_csv(data_path, index=False)
    df_gt.to_csv(gt_path, index=False)
    
    print("=" * 70)
    print("  HACKATHON DATASET GENERATION COMPLETE")
    print("=" * 70)
    print(f"  Rows: {len(df_data)} ticks (approx. 25 minutes of continuous 1 Hz telemetry)")
    print(f"  Sensors: {sensors}")
    print(f"  Data File:         {data_path}")
    print(f"  Ground Truth File: {gt_path}")
    print("=" * 70)
    return data_path, gt_path

if __name__ == "__main__":
    generate_hackathon_dataset()
