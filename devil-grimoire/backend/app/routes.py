"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — REST API Routes & WebSocket Endpoint                     ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Provides REST endpoints for scenario injection, alert management,         ║
║  CSV upload, and sensor statistics. Also hosts the /ws/live WebSocket.     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Query
from fastapi.responses import JSONResponse
import json
import asyncio
import pandas as pd
import numpy as np
import io

from .generator import set_scenario
from . import database as db

# ─────────────────────────────────────────────────────────────────────────────
# ROUTER & CONNECTION MANAGER
# ─────────────────────────────────────────────────────────────────────────────
router = APIRouter()


class ConnectionManager:
    """
    Manages active WebSocket connections for the /ws/live broadcast.
    Supports multiple simultaneous dashboard clients.
    """
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"  📡 WebSocket client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"  📡 WebSocket client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, data: dict):
        """Broadcast JSON payload to all connected WebSocket clients."""
        disconnected = []
        message = json.dumps(data)
        for conn in self.active_connections:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.append(conn)
        
        # Clean up dead connections
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager — shared with main.py
ws_manager = ConnectionManager()


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket Endpoint — /ws/live
# ═══════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sensor data streaming.
    
    The server pushes data at 1 Hz; clients are passive listeners.
    Connection lifecycle: connect → receive broadcasts → disconnect.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — wait for client messages (pings/pongs)
            # Actual data is pushed via the broadcast loop in main.py
            data = await websocket.receive_text()
            # Client can send control messages if needed
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ═══════════════════════════════════════════════════════════════════════════════
# REST API — Scenario Injector
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/scenario")
async def inject_scenario(payload: dict):
    """
    POST /api/scenario — Inject a fault/event scenario into the live generator.
    
    Request Body:
        { "scenario": "spike" | "drift" | "env_event" | "stuck_at" | "excessive_noise" | "normal" }
    
    This mutates the shared GeneratorState in the background loop,
    causing immediate effect on the next generated tick.
    """
    from .main import generator_state  # Import shared state
    
    scenario = payload.get("scenario", "normal")
    message = set_scenario(generator_state, scenario)
    
    return JSONResponse({
        "status": "ok",
        "scenario": scenario,
        "message": message
    })


# ═══════════════════════════════════════════════════════════════════════════════
# REST API — CSV Upload for Replay Mode
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...), speed: int = Query(default=1)):
    """
    POST /api/upload-csv — Upload a CSV file for replay evaluation mode.
    
    The CSV is parsed and stored in the shared app state. The background
    loop switches from Live Generator Mode to CSV Replay Mode.
    
    Expected CSV format:
        timestamp, TEMP-01, TEMP-02, TEMP-03, TEMP-04, TEMP-05, ...
    
    Query Parameters:
        speed: Playback speed multiplier (1x, 5x, 10x)
    """
    from .main import app_state
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        if df.empty:
            return JSONResponse(
                {"status": "error", "message": "Uploaded CSV file contains no data rows."},
                status_code=400
            )

        # Exclude common non-sensor metadata column names
        ignored_names = {
            "timestamp", "time", "tick", "index", "id", "label",
            "class", "target", "date", "status", "notes", "user", "comment"
        }
        
        # 1. First priority: numeric columns matching sensor naming conventions
        sensor_cols = [
            col for col in df.columns
            if col.lower() not in ignored_names
            and pd.api.types.is_numeric_dtype(df[col])
            and (
                col.upper().startswith(("TEMP", "SENSOR"))
                or (col.upper().startswith("S") and (len(col) > 1 and (col[1].isdigit() or col[1] in ("-", "_"))))
            )
        ]
        
        # 2. Fallback: any numeric columns not in ignored metadata names
        if not sensor_cols:
            sensor_cols = [
                col for col in df.select_dtypes(include=[np.number]).columns
                if col.lower() not in ignored_names
            ]
        
        if not sensor_cols:
            return JSONResponse(
                {"status": "error", "message": "No valid numeric sensor columns detected in CSV."},
                status_code=400
            )

        # Store the CSV data in app state for the background loop
        app_state["csv_data"] = df
        app_state["csv_index"] = 0
        app_state["csv_mode"] = True
        app_state["csv_speed"] = max(1, min(10, speed))
        app_state["csv_sensors"] = sensor_cols
        
        return JSONResponse({
            "status": "ok",
            "message": f"CSV uploaded: {len(df)} rows, {len(sensor_cols)} sensors detected.",
            "sensors": sensor_cols,
            "rows": len(df),
            "speed": app_state["csv_speed"],
        })
    
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=400
        )


@router.post("/api/stop-csv")
async def stop_csv():
    """Stop CSV replay mode and return to live generator."""
    from .main import app_state
    app_state["csv_mode"] = False
    app_state["csv_data"] = None
    app_state["csv_index"] = 0
    return JSONResponse({"status": "ok", "message": "CSV replay stopped. Returning to live mode."})


# ═══════════════════════════════════════════════════════════════════════════════
# REST API — Alert Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/alerts")
async def get_alerts(limit: int = Query(default=50)):
    """GET /api/alerts — Fetch recent alerts with acknowledgement status."""
    alerts = await db.get_recent_alerts(limit)
    return JSONResponse({"alerts": alerts})


@router.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """POST /api/alerts/{id}/acknowledge — Mark an alert as acknowledged."""
    success = await db.acknowledge_alert(alert_id)
    if success:
        return JSONResponse({"status": "ok", "message": f"Alert {alert_id} acknowledged."})
    return JSONResponse(
        {"status": "error", "message": f"Alert {alert_id} not found or already acknowledged."},
        status_code=404
    )


# ═══════════════════════════════════════════════════════════════════════════════
# REST API — Sensor Statistics
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/stats")
async def get_stats():
    """GET /api/stats — Get aggregate sensor statistics."""
    stats = await db.get_sensor_stats()
    return JSONResponse({"stats": stats})


@router.get("/api/trust-history/{sensor_id}")
async def get_trust_history(sensor_id: str, limit: int = Query(default=120)):
    """GET /api/trust-history/{sensor_id} — Get trust score history."""
    history = await db.get_trust_history(sensor_id, limit)
    return JSONResponse({"history": history})


@router.get("/api/health")
async def health_check():
    """GET /api/health — Basic health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "DEVIL GRIMOIRE",
        "version": "1.0.0"
    })
