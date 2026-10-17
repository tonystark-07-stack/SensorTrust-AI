"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — FastAPI Application Entry Point                          ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Initializes the FastAPI app, mounts routes, sets up the async background  ║
║  loop for 1 Hz sensor data generation → feature extraction →               ║
║  classification → trust scoring → WebSocket broadcast.                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import numpy as np
import pandas as pd

from .generator import GeneratorState, generate_tick, SENSOR_IDS
from .engine import (
    compute_features,
    classify_sensor,
    TrustScoreManager,
    detect_cohort_event,
    generate_xai_reason,
    CLASS_LABELS,
    WINDOW_LONG,
)
from .routes import router, ws_manager
from . import database as db

# ─────────────────────────────────────────────────────────────────────────────
# SHARED MUTABLE STATE — accessed by both the background loop and API routes
# ─────────────────────────────────────────────────────────────────────────────

# Generator state machine (mutated by Scenario Injector API)
generator_state = GeneratorState()

# Trust score manager (EMA-based, one score per sensor)
trust_manager = TrustScoreManager()

# Rolling buffers for feature computation (sensor_id → list of float values)
# These maintain the 30+ tick history needed for window-based features.
sensor_buffers: dict[str, list[float]] = {sid: [] for sid in SENSOR_IDS}

# Rolling buffers for missing data tracking (sensor_id → list of bool)
sensor_missing_buffers: dict[str, list[bool]] = {sid: [] for sid in SENSOR_IDS}

# Application state for CSV replay mode
app_state = {
    "csv_mode": False,
    "csv_data": None,
    "csv_index": 0,
    "csv_speed": 1,
    "csv_sensors": [],
    "running": True,
}


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TICK PROCESSOR — the core 1 Hz pipeline
# ═══════════════════════════════════════════════════════════════════════════════

async def process_tick(readings: dict[str, float], tick: int):
    """
    Process one tick of sensor data through the full pipeline:
    
    1. Track missingness and forward-fill NaN values (ffill)
    2. Append to rolling buffers
    3. Compute 6 dimensionless features per sensor
    4. Detect cohort environmental events
    5. Classify each sensor via Random Forest
    6. Update EMA trust scores
    7. Generate XAI reasoning strings
    8. Persist to SQLite atomically
    9. Generate alerts with persistent database IDs
    10. Broadcast via WebSocket
    """
    global sensor_buffers, sensor_missing_buffers
    
    # Ensure all sensor buffers exist
    for sid in readings:
        if sid not in sensor_buffers:
            sensor_buffers[sid] = []
        if sid not in sensor_missing_buffers:
            sensor_missing_buffers[sid] = []
    
    # ── Step 1: Track NaNs and Forward-fill ───────────────────────────────────
    for sid, val in readings.items():
        is_missing = val is None or (isinstance(val, float) and np.isnan(val))
        sensor_missing_buffers[sid].append(is_missing)
        if len(sensor_missing_buffers[sid]) > WINDOW_LONG * 2:
            sensor_missing_buffers[sid] = sensor_missing_buffers[sid][-WINDOW_LONG * 2:]

        if is_missing:
            if sensor_buffers[sid]:
                readings[sid] = sensor_buffers[sid][-1]  # ffill
            else:
                readings[sid] = 0.0  # fallback
    
    # ── Step 2: Append to rolling buffers ────────────────────────────────────
    for sid, val in readings.items():
        sensor_buffers[sid].append(val)
        if len(sensor_buffers[sid]) > WINDOW_LONG * 2:
            sensor_buffers[sid] = sensor_buffers[sid][-WINDOW_LONG * 2:]
    
    # ── Step 3: Compute features for each sensor ────────────────────────────
    sensor_features = {}
    active_sids = list(readings.keys())
    
    for sid in active_sids:
        target = np.array(sensor_buffers[sid])
        peers = [
            np.array(sensor_buffers[other_sid])
            for other_sid in active_sids
            if other_sid != sid and len(sensor_buffers[other_sid]) > 0
        ]
        features = compute_features(
            target, peers, raw_missing=sensor_missing_buffers.get(sid, [])
        )
        sensor_features[sid] = features
    
    # ── Step 4: Detect cohort environmental event ────────────────────────────
    cohort_buffers = {
        sid: np.array(buf)
        for sid, buf in sensor_buffers.items()
        if sid in active_sids and len(buf) >= WINDOW_LONG
    }
    is_cohort_event, cohort_sensors = detect_cohort_event(cohort_buffers)
    
    # ── Step 5-7: Classify, score, and explain each sensor ───────────────────
    classifications = {}
    trust_scores = {}
    xai_reasons = {}
    class_probabilities = {}
    alerts_to_insert = []
    
    for sid in active_sids:
        features = sensor_features[sid]
        
        # ── Step 5: ML Classification ──
        try:
            predicted_class, class_proba = classify_sensor(features)
        except Exception:
            predicted_class = "Normal"
            class_proba = np.zeros(len(CLASS_LABELS))
            class_proba[0] = 1.0
        
        # ── Override: Cohort consensus override ──
        is_in_cohort = sid in cohort_sensors
        if is_cohort_event and is_in_cohort:
            predicted_class = "Env Event"
        
        # ── Step 6: Update Trust Score ──
        trust_score = trust_manager.update(
            sid, predicted_class, is_env_event_cohort=is_in_cohort
        )
        
        # ── Step 7: Generate XAI Reason ──
        xai_reason = generate_xai_reason(
            sid, predicted_class, features,
            is_cohort_event and is_in_cohort,
            cohort_sensors, trust_score
        )

        classifications[sid] = predicted_class
        trust_scores[sid] = trust_score
        xai_reasons[sid] = xai_reason
        class_probabilities[sid] = class_proba
        
        # ── Step 8: Build alert if anomalous ──
        if predicted_class != "Normal":
            severity = "critical" if trust_score < 40 else "warning"
            is_suppressed = is_cohort_event and is_in_cohort
            alerts_to_insert.append({
                "sensor_id": sid,
                "type": predicted_class,
                "severity": severity,
                "message": xai_reason,
                "is_suppressed": is_suppressed,
                "tick": tick,
            })

    # ── Step 9: Atomically persist tick data to database ────────────────────
    alert_ids = await db.insert_tick_batch(
        tick, readings, sensor_features, classifications, trust_scores, xai_reasons, alerts_to_insert
    )
    
    # Associate generated IDs with the alerts for the WebSocket payload
    broadcast_alerts = []
    for i, alt in enumerate(alerts_to_insert):
        alt_payload = dict(alt)
        if i < len(alert_ids):
            alt_payload["id"] = alert_ids[i]
        broadcast_alerts.append(alt_payload)

    # ── Step 10: Build and broadcast payload ────────────────────────────────
    broadcast_payload = {
        "type": "tick",
        "tick": tick,
        "sensors": {
            sid: {
                "value": round(readings[sid], 4),
                "features": {k: round(v, 4) for k, v in sensor_features[sid].items()},
                "predicted_class": classifications[sid],
                "trust_score": round(trust_scores[sid], 2),
                "xai_reason": xai_reasons[sid],
                "class_probabilities": {
                    CLASS_LABELS[i]: round(float(p), 4)
                    for i, p in enumerate(class_probabilities[sid])
                },
            }
            for sid in active_sids
        },
        "cohort_event": is_cohort_event,
        "cohort_sensors": cohort_sensors,
        "alerts": broadcast_alerts,
    }
    
    await ws_manager.broadcast(broadcast_payload)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND LOOP — dual-mode 1 Hz data ingestion
# ═══════════════════════════════════════════════════════════════════════════════

async def background_loop():
    """
    Main background asyncio loop running at 1 Hz.
    """
    tick = 0
    await asyncio.sleep(1)
    print("  🚀 Background loop started — 1 Hz sensor data pipeline active.")
    
    while app_state["running"]:
        try:
            tick += 1
            
            if app_state["csv_mode"] and app_state["csv_data"] is not None:
                # ── CSV Replay Mode ──────────────────────────────────────────
                df = app_state["csv_data"]
                idx = app_state["csv_index"]
                sensors = app_state["csv_sensors"]
                speed = app_state["csv_speed"]
                
                if idx >= len(df) or not sensors:
                    # CSV exhausted — loop back or stop
                    app_state["csv_index"] = 0
                    app_state["csv_mode"] = False
                    await ws_manager.broadcast({
                        "type": "csv_complete",
                        "message": "CSV replay complete. Returning to live mode."
                    })
                    continue
                
                # Read current row safely
                row = df.iloc[idx]
                readings = {}
                for col in sensors:
                    raw_val = row.get(col, np.nan)
                    try:
                        if pd.isna(raw_val):
                            val = np.nan
                        else:
                            val = float(raw_val)
                    except (ValueError, TypeError):
                        val = np.nan
                    readings[col] = val
                
                app_state["csv_index"] = idx + 1
                
                await process_tick(readings, tick)
                await asyncio.sleep(1.0 / max(1, speed))
            
            else:
                # ── Live Generator Mode ──────────────────────────────────────
                readings = generate_tick(generator_state)
                await process_tick(readings, tick)
                await asyncio.sleep(1.0)
        
        except Exception as e:
            print(f"  ⚠️ Background loop error: {e}")
            await asyncio.sleep(1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION — lifecycle management
# ═══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Startup:
      1. Initialize SQLite database
      2. Launch background 1 Hz processing loop
    
    Shutdown:
      1. Signal background loop to stop
      2. Close database connections
    """
    print("\n" + "=" * 70)
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║         DEVIL GRIMOIRE — Starting Up            ║")
    print("  ║    AI Sensor Trust & Drift Detection System      ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print("=" * 70)
    
    # Initialize database
    await db.init_db()
    
    # Start background loop
    loop_task = asyncio.create_task(background_loop())
    
    print("  📡 WebSocket endpoint: ws://localhost:8000/ws/live")
    print("  🔧 API docs: http://localhost:8000/docs")
    print("=" * 70 + "\n")
    
    yield
    
    # Shutdown
    print("\n  🛑 Shutting down DEVIL GRIMOIRE...")
    app_state["running"] = False
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass


# ── Create FastAPI application ──────────────────────────────────────────────
app = FastAPI(
    title="DEVIL GRIMOIRE",
    description="AI-Based Sensor Trust, Drift, and False-Alarm Detection System",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS middleware for React frontend ──────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routes ────────────────────────────────────────────────────────────
app.include_router(router)
