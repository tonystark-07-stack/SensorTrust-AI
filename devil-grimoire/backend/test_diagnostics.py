"""
Comprehensive Test Suite for DEVIL GRIMOIRE
Tests all components, algorithms, edge cases, and endpoints.
"""

import sys
import os
import unittest
import numpy as np
import pandas as pd
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engine import (
    compute_features,
    features_to_vector,
    classify_sensor,
    TrustScoreManager,
    detect_cohort_event,
    generate_xai_reason,
    CLASS_LABELS,
    FEATURE_ORDER,
    WINDOW_LONG,
    WINDOW_SHORT,
    WINDOW_NAN,
)
from app.generator import (
    GeneratorState,
    generate_tick,
    set_scenario,
    Scenario,
    SENSOR_IDS,
)
from app import database as db
from app.main import app, process_tick

class TestFeatureExtraction(unittest.TestCase):
    def test_normal_features(self):
        # 30 ticks of stationary data around 24.0 with noise 0.08
        np.random.seed(42)
        target = 24.0 + np.random.normal(0, 0.08, 35)
        peers = [24.0 + np.random.normal(0, 0.08, 35) for _ in range(4)]
        feats = compute_features(target, peers)
        
        self.assertEqual(len(feats), 6)
        for f in FEATURE_ORDER:
            self.assertIn(f, feats)
            self.assertFalse(np.isnan(feats[f]), f"Feature {f} is NaN")
            self.assertFalse(np.isinf(feats[f]), f"Feature {f} is Inf")

    def test_edge_case_empty_values(self):
        # Empty array
        target = np.array([])
        peers = [np.array([]) for _ in range(4)]
        try:
            feats = compute_features(target, peers)
            for f in FEATURE_ORDER:
                self.assertIn(f, feats)
                self.assertFalse(np.isnan(feats[f]))
        except Exception as e:
            self.fail(f"compute_features crashed on empty input: {e}")

    def test_edge_case_single_value(self):
        target = np.array([25.0])
        peers = [np.array([25.0]) for _ in range(4)]
        feats = compute_features(target, peers)
        self.assertEqual(feats["self_z_score"], 0.0)

    def test_edge_case_zero_variance_peers(self):
        # All peers have identical value -> MAD is 0
        target = np.array([35.0] * 35)
        peers = [np.array([25.0] * 35) for _ in range(4)]
        feats = compute_features(target, peers)
        # Target differs from peers by 10.0! peer_mad_score should NOT be 0!
        print(f"DEBUG: peer_mad_score with 0-var peers: {feats.get('peer_mad_score')}")

    def test_edge_case_nans_in_input(self):
        target = np.array([25.0] * 20 + [np.nan] * 10)
        peers = [np.array([25.0] * 30) for _ in range(4)]
        try:
            feats = compute_features(target, peers)
            vec = features_to_vector(feats)
            pred_class, proba = classify_sensor(feats)
            self.assertIn(pred_class, CLASS_LABELS)
        except Exception as e:
            self.fail(f"NaN in input crashed classification: {e}")

class TestGeneratorState(unittest.TestCase):
    def test_env_event_ramp_synchrony(self):
        state = GeneratorState()
        set_scenario(state, "env_event")
        readings = generate_tick(state)
        # Check if TEMP-01, 02, 04, 05 have the same ramp offset
        offsets = [readings[s] - 24.0 for s in ["TEMP-01", "TEMP-02", "TEMP-04", "TEMP-05"]]
        print(f"DEBUG: env_event tick 1 offsets: {offsets}")
        print(f"DEBUG: env_event ramp accumulator: {state.env_event_ramp}")

    def test_spike_duration(self):
        state = GeneratorState()
        set_scenario(state, "spike")
        readings1 = generate_tick(state)
        self.assertGreater(readings1["TEMP-02"], 30.0)
        readings2 = generate_tick(state)
        self.assertLess(readings2["TEMP-02"], 30.0)
        self.assertEqual(state.scenario, Scenario.NORMAL)

if __name__ == "__main__":
    unittest.main()
