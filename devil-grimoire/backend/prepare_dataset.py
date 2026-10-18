"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Dataset Formatting Utility                                ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Converts raw Kaggle datasets (Intel Lab, MetroPT, or generic CSVs)         ║
║  into the synchronized wide multi-sensor format expected by SensorTrust-AI: ║
║      timestamp, SENSOR-01, SENSOR-02, SENSOR-03, ...                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Examples:
    1. Intel Berkeley Research Lab (data.txt):
       python prepare_dataset.py --type intel --input data.txt --output intel_formatted.csv

    2. MetroPT-3 or wide CSV:
       python prepare_dataset.py --type wide --input metropt.csv --output metropt_formatted.csv

    3. Generic long CSV (timestamp, sensor_id, value):
       python prepare_dataset.py --type long --input raw.csv --output clean.csv --time-col time --id-col sensor_id --val-col val
"""

import argparse
import sys
import pandas as pd
import numpy as np


def format_intel_lab(input_path: str, output_path: str, num_sensors: int = 5, max_rows: int = 1000):
    """
    Format Intel Berkeley Research Lab raw data.txt
    Columns: date time epoch moteid temperature humidity light voltage
    """
    print(f"[*] Reading Intel Berkeley Lab dataset from: {input_path}")
    
    # Space-separated file without header
    names = ["date", "time", "epoch", "moteid", "temperature", "humidity", "light", "voltage"]
    df = pd.read_csv(input_path, sep=r"\s+", header=None, names=names, on_bad_lines="skip")
    
    # Filter for first N valid motes (e.g. motes 1 to 5)
    selected_motes = list(range(1, num_sensors + 1))
    df = df[df["moteid"].isin(selected_motes)]
    
    # Filter out physical sensor outliers (e.g. invalid temp readings < 0 or > 100 C)
    df = df[(df["temperature"] >= 0) & (df["temperature"] <= 100)]
    
    # Pivot: rows = epoch, columns = moteid, values = temperature
    pivoted = df.pivot_table(index="epoch", columns="moteid", values="temperature", aggfunc="mean")
    
    # Forward-fill minor missing packets and backward-fill remaining edge NaNs
    pivoted = pivoted.ffill().bfill()
    
    # Rename columns to TEMP-01, TEMP-02, ...
    pivoted.columns = [f"TEMP-{int(c):02d}" for c in pivoted.columns]
    pivoted.reset_index(inplace=True)
    pivoted.rename(columns={"epoch": "timestamp"}, inplace=True)
    
    if max_rows and len(pivoted) > max_rows:
        pivoted = pivoted.iloc[:max_rows]
        
    pivoted.to_csv(output_path, index=False)
    print(f"[✓] Saved formatted dataset ({len(pivoted)} rows, {len(pivoted.columns)-1} sensors) to: {output_path}")


def format_wide_dataset(input_path: str, output_path: str, time_col: str = None, sensor_cols: list[str] = None, max_rows: int = 2000):
    """
    Format datasets that are already wide (like MetroPT-3 or NASA C-MAPSS)
    """
    print(f"[*] Reading wide dataset from: {input_path}")
    df = pd.read_csv(input_path, nrows=max_rows * 2 if max_rows else None)
    
    # Determine timestamp column
    if time_col and time_col in df.columns:
        ts = df[time_col]
    else:
        # Detect or generate timestamp
        candidates = ["timestamp", "time", "epoch", "tick", "index", "date", "datetime"]
        found = next((c for c in candidates if c in [col.lower() for col in df.columns]), None)
        if found:
            actual_col = [col for col in df.columns if col.lower() == found][0]
            ts = df[actual_col]
        else:
            ts = pd.Series(np.arange(len(df)), name="timestamp")
            
    # Determine numeric sensor columns
    if sensor_cols:
        sensors = df[[c for c in sensor_cols if c in df.columns]]
    else:
        # Pick top 5 numeric columns
        numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c != getattr(ts, 'name', None)]
        selected = numeric_cols[:5]
        sensors = df[selected].copy()
        
    # Standardize column names
    formatted_cols = {}
    for idx, col in enumerate(sensors.columns, 1):
        formatted_cols[col] = f"TEMP-{idx:02d}" if "temp" in col.lower() else f"SENSOR-{idx:02d}"
    sensors.rename(columns=formatted_cols, inplace=True)
    
    # Combine
    result = pd.concat([pd.Series(np.arange(len(sensors)), name="timestamp"), sensors.reset_index(drop=True)], axis=1)
    result = result.ffill().bfill()
    
    if max_rows and len(result) > max_rows:
        result = result.iloc[:max_rows]
        
    result.to_csv(output_path, index=False)
    print(f"[✓] Saved formatted dataset ({len(result)} rows, {len(result.columns)-1} sensors) to: {output_path}")


def format_long_dataset(input_path: str, output_path: str, time_col: str, id_col: str, val_col: str, max_rows: int = 1000):
    """
    Format generic long/tall datasets: (timestamp, sensor_id, measurement)
    """
    print(f"[*] Reading long dataset from: {input_path}")
    df = pd.read_csv(input_path)
    
    pivoted = df.pivot_table(index=time_col, columns=id_col, values=val_col, aggfunc="mean")
    pivoted = pivoted.ffill().bfill()
    pivoted.columns = [f"SENSOR-{str(c)}" for c in pivoted.columns]
    pivoted.reset_index(inplace=True)
    pivoted.rename(columns={time_col: "timestamp"}, inplace=True)
    
    if max_rows and len(pivoted) > max_rows:
        pivoted = pivoted.iloc[:max_rows]
        
    pivoted.to_csv(output_path, index=False)
    print(f"[✓] Saved formatted dataset ({len(pivoted)} rows, {len(pivoted.columns)-1} sensors) to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Format raw sensor datasets for SensorTrust-AI")
    parser.add_argument("--type", choices=["intel", "wide", "long"], default="wide", help="Dataset type")
    parser.add_argument("--input", required=True, help="Path to input raw file (.csv or .txt)")
    parser.add_argument("--output", default="formatted_sensors.csv", help="Output CSV path")
    parser.add_argument("--time-col", help="Name of timestamp column (for wide/long)")
    parser.add_argument("--id-col", help="Name of sensor ID column (for long)")
    parser.add_argument("--val-col", help="Name of sensor value column (for long)")
    parser.add_argument("--sensor-cols", nargs="+", help="Specific sensor columns to select (for wide)")
    parser.add_argument("--max-rows", type=int, default=1000, help="Max rows to output")
    
    args = parser.parse_args()
    
    if args.type == "intel":
        format_intel_lab(args.input, args.output, max_rows=args.max_rows)
    elif args.type == "wide":
        format_wide_dataset(args.input, args.output, time_col=args.time_col, sensor_cols=args.sensor_cols, max_rows=args.max_rows)
    elif args.type == "long":
        if not (args.time_col and args.id_col and args.val_col):
            print("Error: --time-col, --id-col, and --val-col are required for long format.")
            sys.exit(1)
        format_long_dataset(args.input, args.output, args.time_col, args.id_col, args.val_col, max_rows=args.max_rows)


if __name__ == "__main__":
    main()
