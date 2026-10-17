"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Synthetic Data Generator & Scenario State Machine        ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Generates 5 virtual temperature sensors (TEMP-01..05) at 1 Hz with       ║
║  physically realistic ambient trends, Gaussian noise, and injectable      ║
║  fault/event scenarios via the Active Scenario Injector API.               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import time
from dataclasses import dataclass, field
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO ENUMERATION — supported injectable fault/event types
# ─────────────────────────────────────────────────────────────────────────────
class Scenario(str, Enum):
    NORMAL          = "normal"
    SPIKE           = "spike"
    DRIFT           = "drift"
    ENV_EVENT       = "env_event"
    STUCK_AT        = "stuck_at"
    EXCESSIVE_NOISE = "excessive_noise"


# ─────────────────────────────────────────────────────────────────────────────
# GENERATOR STATE — mutable state container for the live data generator
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class GeneratorState:
    """
    Holds the mutable state for the 5-sensor synthetic data generator.
    
    Attributes
    ──────────
    scenario : Scenario
        Currently active fault/event injection mode.
    tick : int
        Global tick counter (monotonically increasing at 1 Hz).
    drift_accumulator : float
        Cumulative drift offset for TEMP-04 in Drift scenario.
        Grows by +0.025°C per tick to simulate gradual sensor calibration loss.
    spike_remaining : int
        Number of ticks remaining for the Spike injection on TEMP-02.
        Spike lasts exactly 1 tick, then auto-resets to Normal.
    env_event_ramp : float
        Current ramp offset for Env Event. All 4 affected sensors share this.
    noise_multiplier : float
        Noise amplification factor for Excessive Noise on TEMP-05.
    stuck_value : float
        Fixed output value for Stuck-At fault on TEMP-03.
    """
    scenario: Scenario = Scenario.NORMAL
    tick: int = 0
    drift_accumulator: float = 0.0
    spike_remaining: int = 0
    env_event_ramp: float = 0.0
    noise_multiplier: float = 1.0
    stuck_value: float = 25.0


# ─────────────────────────────────────────────────────────────────────────────
# SENSOR NAMES — 5 virtual temperature sensors in the default cohort
# ─────────────────────────────────────────────────────────────────────────────
SENSOR_IDS = ["TEMP-01", "TEMP-02", "TEMP-03", "TEMP-04", "TEMP-05"]


# ═══════════════════════════════════════════════════════════════════════════════
# MATH FORMULA: X(t) = Ambient_Trend + Gaussian_Noise + Scenario_Offset
#
# Ambient Trend:  A(t) = 24.0 + 0.5 × sin(2π × t / 3600)
#   Simulates a slow diurnal temperature oscillation with period = 1 hour
#   (3600 ticks). Center = 24.0°C, amplitude = ±0.5°C.
#
# Gaussian Noise: ε(t) ~ N(0, σ²) where σ = 0.08°C
#   Represents typical ADC quantization + thermal noise in industrial sensors.
#
# Scenario Offset: S(t) varies by active scenario (see generate_tick below).
# ═══════════════════════════════════════════════════════════════════════════════

AMBIENT_CENTER    = 24.0    # °C — baseline temperature
AMBIENT_AMPLITUDE = 0.5     # °C — diurnal oscillation amplitude
AMBIENT_PERIOD    = 3600.0  # ticks — full oscillation cycle (1 hour at 1 Hz)
NOISE_SIGMA       = 0.08    # °C — baseline Gaussian noise standard deviation

# Scenario-specific constants
SPIKE_MAGNITUDE    = 12.0   # °C — instant jump for Spike scenario on TEMP-02
DRIFT_RATE         = 0.025  # °C/tick — cumulative drift rate on TEMP-04
ENV_RAMP_RATE      = 0.15   # °C/tick — env event ramp rate (reaches +4.5 in ~30 ticks)
ENV_RAMP_MAX       = 4.5    # °C — maximum env event offset
NOISE_MULTIPLIER   = 10.0   # ×σ — noise amplification for Excessive Noise


def _ambient(tick: int) -> float:
    """
    Compute ambient temperature trend at a given tick.
    
    Formula: A(t) = 24.0 + 0.5 × sin(2π × t / 3600)
    
    This creates a smooth sinusoidal baseline that mimics real HVAC/weather
    temperature cycles without requiring any physical unit calibration.
    """
    return AMBIENT_CENTER + AMBIENT_AMPLITUDE * np.sin(
        2.0 * np.pi * tick / AMBIENT_PERIOD
    )


def generate_tick(state: GeneratorState) -> dict[str, float]:
    """
    Generate one tick of synthetic sensor data for all 5 sensors.
    
    The output is a dict mapping sensor_id → current_reading.
    Each sensor follows X(t) = Ambient + Noise + Scenario_Offset.
    
    Scenario Effects
    ────────────────
    Normal:          Offset = 0 for all sensors.
    Spike:           TEMP-02 gets +12°C for exactly 1 tick, then auto-resets.
    Drift:           TEMP-04 accumulates +0.025°C/tick (monotonic creep).
    Env Event:       TEMP-01,02,04,05 ramp up by +4.5°C together (cohort).
    Stuck-At:        TEMP-03 locked at 25.0°C with zero noise.
    Excessive Noise: TEMP-05 noise σ multiplied by 10×.
    """
    state.tick += 1
    t = state.tick
    ambient = _ambient(t)
    readings = {}
    
    # ── Advance scenario-wide state before sensor loop ──
    if state.scenario == Scenario.ENV_EVENT:
        state.env_event_ramp = min(
            state.env_event_ramp + ENV_RAMP_RATE, ENV_RAMP_MAX
        )
    
    for sid in SENSOR_IDS:
        # ── Base signal: ambient trend + Gaussian noise ──
        noise = np.random.normal(0, NOISE_SIGMA)
        value = ambient + noise
        
        # ── Apply scenario-specific mutations ──
        if state.scenario == Scenario.SPIKE and sid == "TEMP-02":
            if state.spike_remaining > 0:
                value += SPIKE_MAGNITUDE
                state.spike_remaining -= 1
                if state.spike_remaining <= 0:
                    # Auto-reset to Normal after spike completes
                    state.scenario = Scenario.NORMAL
        
        elif state.scenario == Scenario.DRIFT and sid == "TEMP-04":
            state.drift_accumulator += DRIFT_RATE
            value += state.drift_accumulator
        
        elif state.scenario == Scenario.ENV_EVENT and sid != "TEMP-03":
            # Ramp 4 sensors (01, 02, 04, 05) together with identical offset
            value += state.env_event_ramp
        
        elif state.scenario == Scenario.STUCK_AT and sid == "TEMP-03":
            # Lock TEMP-03 at exactly 25.0°C with zero noise
            value = state.stuck_value
        
        elif state.scenario == Scenario.EXCESSIVE_NOISE and sid == "TEMP-05":
            # Replace normal noise with amplified noise (10× σ)
            extra_noise = np.random.normal(0, NOISE_SIGMA * NOISE_MULTIPLIER)
            value = ambient + extra_noise
        
        readings[sid] = round(value, 4)
    
    return readings


def set_scenario(state: GeneratorState, scenario: str) -> str:
    """
    Set the active scenario on the generator state machine.
    Resets scenario-specific accumulators as needed.
    
    Returns a human-readable confirmation string.
    """
    scenario = scenario.lower().strip()
    
    # Reset accumulators on any scenario switch to avoid state pollution
    state.drift_accumulator = 0.0
    state.env_event_ramp = 0.0
    state.noise_multiplier = 1.0
    state.spike_remaining = 0
    
    if scenario == "normal":
        state.scenario = Scenario.NORMAL
        return "🔄 Reset to NORMAL — all offsets cleared."
    
    elif scenario == "spike":
        state.scenario = Scenario.SPIKE
        state.spike_remaining = 1  # Exactly 1 tick
        return "⚡ SPIKE injected on TEMP-02 — +12°C for 1 tick."
    
    elif scenario == "drift":
        state.scenario = Scenario.DRIFT
        return "📈 DRIFT activated on TEMP-04 — +0.025°C/tick cumulative."
    
    elif scenario == "env_event":
        state.scenario = Scenario.ENV_EVENT
        return "🌡️ ENV EVENT activated — ramping 4 sensors by +4.5°C."
    
    elif scenario == "stuck_at":
        state.scenario = Scenario.STUCK_AT
        state.stuck_value = 25.0
        return "🔒 STUCK-AT activated on TEMP-03 — locked at 25.0°C."
    
    elif scenario == "excessive_noise":
        state.scenario = Scenario.EXCESSIVE_NOISE
        state.noise_multiplier = NOISE_MULTIPLIER
        return "📊 EXCESSIVE NOISE on TEMP-05 — σ × 10."
    
    else:
        return f"⚠️ Unknown scenario: {scenario}"
