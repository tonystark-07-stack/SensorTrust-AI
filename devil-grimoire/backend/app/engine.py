"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Sensor-Agnostic Feature Engine & ML Classification       ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Computes 6 dimensionless features over a rolling window, classifies       ║
║  sensor states via a 100-tree Random Forest, and maintains an EMA-based    ║
║  dynamic Trust Score per sensor with cohort-aware environmental event      ║
║  detection and Explainable AI (XAI) reasoning strings.                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
from scipy import stats
from collections import defaultdict
import joblib
import os

# ─────────────────────────────────────────────────────────────────────────────
# CLASS LABELS — 6 anomaly/state categories predicted by the Random Forest
# ─────────────────────────────────────────────────────────────────────────────
CLASS_LABELS = [
    "Normal",           # 0 — Nominal operation, no drift or fault
    "Spike",            # 1 — Sudden transient excursion (> 3σ single-tick)
    "Drift",            # 2 — Slow monotonic creep (CUSUM slope exceeds threshold)
    "Env Event",        # 3 — Genuine environmental hazard corroborated by peers
    "Stuck-At",         # 4 — Zero-variance frozen sensor (hardware latch fault)
    "Excessive Noise",  # 5 — Noise amplitude ≫ baseline (sensor degradation)
]

# ─────────────────────────────────────────────────────────────────────────────
# TRUST PENALTY MAP — per-class EMA penalty applied to the 0-100 trust score
# Higher penalty = faster trust erosion for that fault type.
# ─────────────────────────────────────────────────────────────────────────────
TRUST_PENALTY = {
    "Normal":          0.0,    # No penalty — trust recovers slowly
    "Spike":          25.0,    # Moderate — could be transient noise
    "Drift":          20.0,    # Moderate — gradual, harder to catch
    "Env Event":       5.0,    # Low — genuine hazard, not sensor fault
    "Stuck-At":       35.0,    # Severe — hardware failure indicator
    "Excessive Noise": 30.0,   # Severe — sensor degradation
}

# EMA smoothing coefficient: Trust_new = α * instantaneous + (1−α) * Trust_old
EMA_ALPHA = 0.3

# Rolling window sizes for feature extraction
WINDOW_LONG  = 30   # Primary analysis window (30 ticks at 1 Hz = 30 seconds)
WINDOW_SHORT = 5    # Short-term variance sub-window
WINDOW_NAN   = 10   # NaN/missing data lookback

# Cohort consensus parameters
COHORT_Z_THRESHOLD = 1.5   # |z| > 1.5 triggers peer flagging
COHORT_MIN_SENSORS = 3     # Minimum sensors shifting together for Env Event
COHORT_SIGMA_SHIFT = 1.5   # Minimum σ shift for cohort detection


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE EXTRACTION — 6 dimensionless, unit-agnostic features
# ═══════════════════════════════════════════════════════════════════════════════

def compute_features(
    values: np.ndarray,
    peer_values: list[np.ndarray],
    raw_missing: list[bool] = None,
) -> dict:
    """
    Compute 6 dimensionless features for a single sensor's rolling window.
    
    Parameters
    ----------
    values : np.ndarray
        Rolling window of this sensor's recent readings (up to WINDOW_LONG ticks).
        Forward-filled (ffill) prior to this call to eliminate internal NaNs.
    peer_values : list[np.ndarray]
        List of rolling windows for all peer sensors in the same cohort.
    raw_missing : list[bool], optional
        Boolean list indicating whether each reading in the window was originally missing/NaN.
    
    Returns
    -------
    dict : Feature name → float value. All features are dimensionless ratios.
    """
    features = {
        "self_z_score": 0.0,
        "peer_mad_score": 0.0,
        "rolling_slope_norm": 0.0,
        "variance_ratio": 1.0,
        "missing_rate": 0.0,
        "cohort_consensus_ratio": 0.0,
    }

    if len(values) == 0:
        if raw_missing and len(raw_missing) > 0:
            window_missing = raw_missing[-WINDOW_NAN:]
            features["missing_rate"] = float(sum(window_missing) / max(1, len(window_missing)))
        return features

    # ── Feature 1: Self Z-Score ──────────────────────────────────────────────
    if len(values) >= 2:
        w = values[-WINDOW_LONG:]
        valid_w = w[~np.isnan(w)]
        if len(valid_w) >= 2:
            roll_mean = np.mean(valid_w)
            roll_std  = np.std(valid_w, ddof=1)
            if roll_std < 1e-10:
                features["self_z_score"] = 0.0
            else:
                features["self_z_score"] = float((values[-1] - roll_mean) / roll_std)
        else:
            features["self_z_score"] = 0.0
    else:
        features["self_z_score"] = 0.0

    # ── Feature 2: Peer MAD Score ────────────────────────────────────────────
    if peer_values and len(peer_values) >= 2:
        peer_current = np.array([
            p[-1] for p in peer_values
            if len(p) > 0 and not np.isnan(p[-1])
        ])
        if len(peer_current) >= 2 and not np.isnan(values[-1]):
            peer_median = np.median(peer_current)
            raw_mad = np.median(np.abs(peer_current - peer_median))
            # MAD continuity correction for normal distribution
            mad = raw_mad * 1.4826
            diff = abs(values[-1] - peer_median)
            if mad < 1e-4:
                # If peers have zero/sub-noise dispersion, compare against baseline noise floor (0.08°C)
                features["peer_mad_score"] = float(diff / 0.08) if diff > 1e-4 else 0.0
            else:
                features["peer_mad_score"] = float(diff / mad)
        else:
            features["peer_mad_score"] = 0.0
    else:
        features["peer_mad_score"] = 0.0

    # ── Feature 3: Rolling Slope (Normalized CUSUM Beta) ─────────────────────
    if len(values) >= WINDOW_LONG:
        window = values[-WINDOW_LONG:]
        valid_mask = ~np.isnan(window)
        if np.sum(valid_mask) >= 2:
            x_axis = np.arange(len(window))[valid_mask]
            y_axis = window[valid_mask]
            try:
                slope, _, _, _, _ = stats.linregress(x_axis, y_axis)
                roll_std_long = np.std(y_axis, ddof=1) if len(y_axis) > 1 else 0.0
                if roll_std_long < 1e-10:
                    features["rolling_slope_norm"] = 0.0
                else:
                    features["rolling_slope_norm"] = float(slope / roll_std_long)
            except Exception:
                features["rolling_slope_norm"] = 0.0
        else:
            features["rolling_slope_norm"] = 0.0
    else:
        features["rolling_slope_norm"] = 0.0

    # ── Feature 4: Variance Ratio (σ_short / σ_long) ────────────────────────
    if len(values) >= WINDOW_LONG:
        w_short = values[-WINDOW_SHORT:]
        w_long  = values[-WINDOW_LONG:]
        valid_short = w_short[~np.isnan(w_short)]
        valid_long  = w_long[~np.isnan(w_long)]
        std_short = np.std(valid_short, ddof=1) if len(valid_short) > 1 else 0.0
        std_long  = np.std(valid_long, ddof=1) if len(valid_long) > 1 else 0.0
        if std_long < 1e-10:
            features["variance_ratio"] = 0.0
        else:
            features["variance_ratio"] = float(std_short / std_long)
    else:
        features["variance_ratio"] = 1.0

    # ── Feature 5: Missing Rate ──────────────────────────────────────────────
    if raw_missing is not None and len(raw_missing) > 0:
        window_missing = raw_missing[-WINDOW_NAN:]
        features["missing_rate"] = float(sum(window_missing) / max(1, len(window_missing)))
    elif len(values) >= WINDOW_NAN:
        nan_count = np.sum(np.isnan(values[-WINDOW_NAN:]))
        features["missing_rate"] = float(nan_count / WINDOW_NAN)
    else:
        features["missing_rate"] = 0.0

    # ── Feature 6: Cohort Consensus Ratio ────────────────────────────────────
    if peer_values and len(peer_values) >= 2:
        elevated_count = 0
        total_peers = 0
        for pv in peer_values:
            if len(pv) >= WINDOW_LONG:
                w_p = pv[-WINDOW_LONG:]
                valid_p = w_p[~np.isnan(w_p)]
                if len(valid_p) >= 2:
                    p_mean = np.mean(valid_p)
                    p_std  = np.std(valid_p, ddof=1)
                    if p_std > 1e-10 and not np.isnan(pv[-1]):
                        p_z = abs(pv[-1] - p_mean) / p_std
                        if p_z > COHORT_Z_THRESHOLD:
                            elevated_count += 1
                total_peers += 1
        features["cohort_consensus_ratio"] = float(
            elevated_count / total_peers if total_peers > 0 else 0.0
        )
    else:
        features["cohort_consensus_ratio"] = 0.0

    # Sanitize all features to non-NaN, non-inf floats
    for k in features:
        val = features[k]
        if np.isnan(val) or np.isinf(val):
            features[k] = 0.0

    return features


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE VECTOR BUILDER — converts dict → ordered numpy array for RF input
# ═══════════════════════════════════════════════════════════════════════════════

FEATURE_ORDER = [
    "self_z_score",
    "peer_mad_score",
    "rolling_slope_norm",
    "variance_ratio",
    "missing_rate",
    "cohort_consensus_ratio",
]

def features_to_vector(features: dict) -> np.ndarray:
    """Convert feature dict to ordered numpy array matching RF training order."""
    return np.array([float(features.get(f, 0.0)) for f in FEATURE_ORDER]).reshape(1, -1)


# ═══════════════════════════════════════════════════════════════════════════════
# ML MODEL LOADER — loads the pre-trained Random Forest from disk
# ═══════════════════════════════════════════════════════════════════════════════

_model = None

def load_model(path: str = None) -> object:
    """
    Lazy-load the trained Random Forest model.
    Default path: ../sensortrust_model.joblib (relative to this file).
    """
    global _model
    if _model is not None:
        return _model
    
    if path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "sensortrust_model.joblib")
    
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Model not found at {path}. Run `python train.py` first."
        )
    
    _model = joblib.load(path)
    return _model


def classify_sensor(features: dict) -> tuple[str, np.ndarray]:
    """
    Classify a sensor's state using the Random Forest model.
    
    Returns
    -------
    (predicted_class_label, class_probabilities)
    """
    model = load_model()
    vec = features_to_vector(features)
    
    # Replace any NaN or inf with 0, then clip to valid RF training boundary
    vec = np.nan_to_num(vec, nan=0.0, posinf=50.0, neginf=-50.0)
    vec = np.clip(vec, -50, 50)
    
    pred_idx = model.predict(vec)[0]
    pred_proba = model.predict_proba(vec)[0]
    
    return CLASS_LABELS[pred_idx], pred_proba


# ═══════════════════════════════════════════════════════════════════════════════
# TRUST SCORE MANAGER — EMA-based dynamic trust tracking per sensor
# ═══════════════════════════════════════════════════════════════════════════════

class TrustScoreManager:
    """
    Maintains a per-sensor trust score in [0, 100] using Exponential Moving Average.
    
    Trust Update Formula
    ────────────────────
    For each tick:
      1. Compute instantaneous trust:
         - If class == "Normal": instant_trust = 100 (full trust)
         - Else: instant_trust = max(0, 100 - penalty[class])
      2. Apply EMA:
         Trust[t] = α * instant_trust + (1 - α) * Trust[t-1]
         where α = 0.3
    
    Cohort Dampening
    ────────────────
    If an Env Event is detected (≥3 sensors shifting together > 1.5σ):
      - Trust penalty is halved (multiplied by 0.5)
      - XAI string indicates corroborated environmental hazard
    
    This ensures genuine environmental emergencies don't unfairly erode
    sensor trustworthiness — the sensors are reporting accurately.
    """
    
    def __init__(self):
        # sensor_id → current trust score (starts at 100%)
        self.trust_scores: dict[str, float] = defaultdict(lambda: 100.0)
        # sensor_id → last predicted class
        self.last_class: dict[str, str] = defaultdict(lambda: "Normal")
    
    def update(
        self,
        sensor_id: str,
        predicted_class: str,
        is_env_event_cohort: bool = False,
    ) -> float:
        """
        Update trust score for a sensor based on its predicted class.
        
        Parameters
        ----------
        sensor_id : str
            Unique sensor identifier (e.g., "TEMP-01")
        predicted_class : str
            One of CLASS_LABELS
        is_env_event_cohort : bool
            True if this sensor is part of a cohort environmental event.
            Halves the anomaly penalty to reflect verified hazard status.
        
        Returns
        -------
        float : Updated trust score in [0, 100]
        """
        penalty = TRUST_PENALTY.get(predicted_class, 10.0)
        
        # ── Cohort dampening: genuine hazards get 50% penalty reduction ──
        if is_env_event_cohort and predicted_class != "Normal":
            penalty *= 0.5
        
        # ── Compute instantaneous trust for this tick ──
        if predicted_class == "Normal":
            instant_trust = 100.0  # Full trust on normal operation
        else:
            instant_trust = max(0.0, 100.0 - penalty)
        
        # ── EMA smoothing: Trust[t] = α·instant + (1-α)·Trust[t-1] ──
        current = self.trust_scores[sensor_id]
        new_trust = EMA_ALPHA * instant_trust + (1 - EMA_ALPHA) * current
        
        # Clamp to valid range
        self.trust_scores[sensor_id] = max(0.0, min(100.0, new_trust))
        self.last_class[sensor_id] = predicted_class
        
        return self.trust_scores[sensor_id]
    
    def get_trust(self, sensor_id: str) -> float:
        """Get current trust score for a sensor."""
        return self.trust_scores[sensor_id]
    
    def get_all(self) -> dict[str, float]:
        """Get all trust scores as a plain dict."""
        return dict(self.trust_scores)


# ═══════════════════════════════════════════════════════════════════════════════
# COHORT DETECTION — identifies correlated environmental events
# ═══════════════════════════════════════════════════════════════════════════════

def detect_cohort_event(
    sensor_buffers: dict[str, np.ndarray],
) -> tuple[bool, list[str]]:
    """
    Detect if ≥ COHORT_MIN_SENSORS are shifting together by > 1.5σ.
    
    Algorithm
    ─────────
    1. For each sensor, compute z-score of current reading vs its 30-tick window.
    2. Count how many sensors have |z| > COHORT_SIGMA_SHIFT.
    3. If count ≥ COHORT_MIN_SENSORS → cohort environmental event detected.
    
    Returns
    -------
    (is_cohort_event, list_of_affected_sensor_ids)
    """
    elevated_sensors = []
    
    for sid, buf in sensor_buffers.items():
        if len(buf) < WINDOW_LONG:
            continue
        window = buf[-WINDOW_LONG:]
        mean = np.nanmean(window)
        std  = np.nanstd(window, ddof=1)
        if std > 1e-10:
            z = abs(buf[-1] - mean) / std
            if z > COHORT_SIGMA_SHIFT:
                elevated_sensors.append(sid)
    
    is_event = len(elevated_sensors) >= COHORT_MIN_SENSORS
    return is_event, elevated_sensors


# ═══════════════════════════════════════════════════════════════════════════════
# XAI REASONING ENGINE — generates human-readable explanation strings
# ═══════════════════════════════════════════════════════════════════════════════

def generate_xai_reason(
    sensor_id: str,
    predicted_class: str,
    features: dict,
    is_cohort: bool,
    cohort_sensors: list[str],
    trust_score: float,
) -> str:
    """
    Generate a plain-text Explainable AI (XAI) reasoning string.
    
    Provides actionable, human-readable explanations for each classification,
    referencing the specific feature values that drove the decision.
    """
    z = features.get("self_z_score", 0)
    mad = features.get("peer_mad_score", 0)
    slope = features.get("rolling_slope_norm", 0)
    vr = features.get("variance_ratio", 0)
    mr = features.get("missing_rate", 0)
    cc = features.get("cohort_consensus_ratio", 0)
    
    if predicted_class == "Normal":
        return (
            f"✅ {sensor_id} operating normally. "
            f"Z-score={z:.2f} within ±1.5σ bounds. "
            f"Trust={trust_score:.1f}%."
        )
    
    elif predicted_class == "Spike":
        return (
            f"⚡ SPIKE detected on {sensor_id}. "
            f"Self Z-score={z:.2f} (>{COHORT_Z_THRESHOLD}σ deviation). "
            f"Peer MAD score={mad:.2f} confirms outlier status. "
            f"Likely transient hardware glitch or EMI. Trust={trust_score:.1f}%."
        )
    
    elif predicted_class == "Drift":
        return (
            f"📈 DRIFT detected on {sensor_id}. "
            f"Normalized slope={slope:.4f} indicates monotonic creep. "
            f"Variance ratio={vr:.2f} shows gradual baseline shift. "
            f"Recommend recalibration. Trust={trust_score:.1f}%."
        )
    
    elif predicted_class == "Env Event":
        if is_cohort:
            peer_list = ", ".join([s for s in cohort_sensors if s != sensor_id][:3])
            return (
                f"🌡️ VERIFIED HAZARD on {sensor_id}. "
                f"Corroborated by neighbors: [{peer_list}]. "
                f"Cohort consensus={cc:.0%}. "
                f"Environmental event confirmed — penalty dampened 50%. "
                f"Trust={trust_score:.1f}%."
            )
        else:
            return (
                f"🌡️ Environmental event suspected on {sensor_id}. "
                f"Z-score={z:.2f}, cohort consensus={cc:.0%}. "
                f"Trust={trust_score:.1f}%."
            )
    
    elif predicted_class == "Stuck-At":
        return (
            f"🔒 STUCK-AT FAULT on {sensor_id}. "
            f"Variance ratio={vr:.4f} (near-zero short-term variance). "
            f"Sensor output frozen — possible ADC latch or wiring fault. "
            f"Immediate replacement recommended. Trust={trust_score:.1f}%."
        )
    
    elif predicted_class == "Excessive Noise":
        return (
            f"📊 EXCESSIVE NOISE on {sensor_id}. "
            f"Variance ratio={vr:.2f} (short-term σ ≫ baseline). "
            f"Self Z-score={z:.2f} shows high-frequency oscillation. "
            f"Check shielding and power supply. Trust={trust_score:.1f}%."
        )
    
    return f"⚠️ Unknown state for {sensor_id}. Trust={trust_score:.1f}%."
