"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Async SQLite Database Layer                              ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Edge-optimized persistence using aiosqlite for async, non-blocking I/O.   ║
║  Stores sensor readings, trust scores, alerts, and classification events.  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import aiosqlite
import os
import json
import asyncio
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE PATH — SQLite file stored alongside the backend
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "devil_grimoire.db"
)

# Mutex lock to serialize database writes and prevent 'database is locked' errors
_db_lock = asyncio.Lock()

async def get_connection():
    """Create a connection with a 30s busy timeout and WAL mode."""
    conn = await aiosqlite.connect(DB_PATH, timeout=30.0)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=10000")
    return conn


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

async def init_db():
    """
    Initialize the SQLite database with the required schema.
    Uses WAL journal mode for concurrent read/write performance.
    """
    async with _db_lock:
        conn = await get_connection()
        try:
            # ── Sensor Readings Table ────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                    tick INTEGER NOT NULL,
                    sensor_id TEXT NOT NULL,
                    value REAL NOT NULL,
                    self_z_score REAL,
                    peer_mad_score REAL,
                    rolling_slope_norm REAL,
                    variance_ratio REAL,
                    missing_rate REAL,
                    cohort_consensus_ratio REAL,
                    predicted_class TEXT,
                    trust_score REAL,
                    xai_reason TEXT
                )
            """)
            
            # ── Alerts Table ─────────────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                    tick INTEGER NOT NULL,
                    sensor_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'warning',
                    message TEXT NOT NULL,
                    is_suppressed INTEGER NOT NULL DEFAULT 0,
                    is_acknowledged INTEGER NOT NULL DEFAULT 0,
                    acknowledged_at TEXT
                )
            """)
            
            # ── Trust History Table ──────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trust_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                    tick INTEGER NOT NULL,
                    sensor_id TEXT NOT NULL,
                    trust_score REAL NOT NULL,
                    predicted_class TEXT NOT NULL
                )
            """)
            
            # ── Indexes for query performance ────────────────────────────────────
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_readings_sensor_tick "
                "ON sensor_readings(sensor_id, tick)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_sensor "
                "ON alerts(sensor_id, is_acknowledged)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trust_sensor_tick "
                "ON trust_history(sensor_id, tick)"
            )
            
            await conn.commit()
        finally:
            await conn.close()
    
    print(f"  ✅ Database initialized at: {DB_PATH}")


# ═══════════════════════════════════════════════════════════════════════════════
# ATOMIC BATCH INSERT (High Performance, 0 Locking Errors)
# ═══════════════════════════════════════════════════════════════════════════════

async def insert_tick_batch(
    tick: int,
    readings: dict[str, float],
    sensor_features: dict[str, dict],
    classifications: dict[str, str],
    trust_scores: dict[str, float],
    xai_reasons: dict[str, str],
    alerts_to_insert: list[dict],
) -> list[int]:
    """
    Atomically insert all data for a single tick in one transaction.
    Returns the list of generated alert IDs.
    """
    alert_ids = []
    async with _db_lock:
        conn = await get_connection()
        try:
            # 1. Insert sensor readings
            reading_params = [
                (
                    tick,
                    sid,
                    float(readings[sid]),
                    float(sensor_features[sid].get("self_z_score", 0.0)),
                    float(sensor_features[sid].get("peer_mad_score", 0.0)),
                    float(sensor_features[sid].get("rolling_slope_norm", 0.0)),
                    float(sensor_features[sid].get("variance_ratio", 0.0)),
                    float(sensor_features[sid].get("missing_rate", 0.0)),
                    float(sensor_features[sid].get("cohort_consensus_ratio", 0.0)),
                    classifications[sid],
                    float(trust_scores[sid]),
                    xai_reasons[sid],
                )
                for sid in readings
            ]
            await conn.executemany(
                """
                INSERT INTO sensor_readings 
                (tick, sensor_id, value, self_z_score, peer_mad_score,
                 rolling_slope_norm, variance_ratio, missing_rate,
                 cohort_consensus_ratio, predicted_class, trust_score, xai_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                reading_params,
            )

            # 2. Insert trust history
            history_params = [
                (tick, sid, float(trust_scores[sid]), classifications[sid])
                for sid in readings
            ]
            await conn.executemany(
                "INSERT INTO trust_history (tick, sensor_id, trust_score, predicted_class) VALUES (?, ?, ?, ?)",
                history_params,
            )

            # 3. Insert alerts and capture IDs
            for alt in alerts_to_insert:
                cursor = await conn.execute(
                    """
                    INSERT INTO alerts (tick, sensor_id, alert_type, severity, message, is_suppressed)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tick,
                        alt["sensor_id"],
                        alt["type"],
                        alt["severity"],
                        alt["message"],
                        int(alt.get("is_suppressed", False)),
                    ),
                )
                alert_ids.append(cursor.lastrowid)

            await conn.commit()
        except Exception as e:
            await conn.rollback()
            print(f"  ⚠️ Error during batch insert for tick {tick}: {e}")
        finally:
            await conn.close()

    return alert_ids


# ═══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL CRUD OPERATIONS (Mutex-Guarded)
# ═══════════════════════════════════════════════════════════════════════════════

async def insert_reading(
    tick: int,
    sensor_id: str,
    value: float,
    features: dict,
    predicted_class: str,
    trust_score: float,
    xai_reason: str,
):
    """Insert a single sensor reading with computed features and classification."""
    async with _db_lock:
        conn = await get_connection()
        try:
            await conn.execute(
                """
                INSERT INTO sensor_readings 
                (tick, sensor_id, value, self_z_score, peer_mad_score,
                 rolling_slope_norm, variance_ratio, missing_rate,
                 cohort_consensus_ratio, predicted_class, trust_score, xai_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tick, sensor_id, float(value),
                    float(features.get("self_z_score", 0)),
                    float(features.get("peer_mad_score", 0)),
                    float(features.get("rolling_slope_norm", 0)),
                    float(features.get("variance_ratio", 0)),
                    float(features.get("missing_rate", 0)),
                    float(features.get("cohort_consensus_ratio", 0)),
                    predicted_class, float(trust_score), xai_reason,
                )
            )
            await conn.commit()
        finally:
            await conn.close()


async def insert_alert(
    tick: int,
    sensor_id: str,
    alert_type: str,
    severity: str,
    message: str,
    is_suppressed: bool = False,
) -> int:
    """Insert a new alert into the alerts table and return the inserted ID."""
    async with _db_lock:
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                """
                INSERT INTO alerts (tick, sensor_id, alert_type, severity, message, is_suppressed)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tick, sensor_id, alert_type, severity, message, int(is_suppressed))
            )
            await conn.commit()
            return cursor.lastrowid
        finally:
            await conn.close()


async def insert_trust_history(tick: int, sensor_id: str, trust_score: float, predicted_class: str):
    """Record a trust score snapshot for historical tracking."""
    async with _db_lock:
        conn = await get_connection()
        try:
            await conn.execute(
                "INSERT INTO trust_history (tick, sensor_id, trust_score, predicted_class) VALUES (?, ?, ?, ?)",
                (tick, sensor_id, float(trust_score), predicted_class)
            )
            await conn.commit()
        finally:
            await conn.close()


async def get_recent_alerts(limit: int = 50) -> list[dict]:
    """Fetch the most recent alerts, newest first."""
    conn = await get_connection()
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def acknowledge_alert(alert_id: int) -> bool:
    """Acknowledge an alert by ID. Returns True if the alert existed."""
    async with _db_lock:
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                """
                UPDATE alerts 
                SET is_acknowledged = 1, acknowledged_at = datetime('now')
                WHERE id = ? AND is_acknowledged = 0
                """,
                (alert_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()


async def get_trust_history(sensor_id: str, limit: int = 120) -> list[dict]:
    """Get trust score history for a sensor."""
    conn = await get_connection()
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT tick, trust_score, predicted_class 
            FROM trust_history 
            WHERE sensor_id = ?
            ORDER BY tick DESC 
            LIMIT ?
            """,
            (sensor_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_sensor_stats() -> list[dict]:
    """Get aggregate statistics for all sensors."""
    conn = await get_connection()
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT sensor_id,
                   COUNT(*) as total_readings,
                   AVG(trust_score) as avg_trust,
                   MIN(trust_score) as min_trust,
                   MAX(trust_score) as max_trust
            FROM sensor_readings
            GROUP BY sensor_id
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()

