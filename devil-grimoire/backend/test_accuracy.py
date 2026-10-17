"""
Test Classification Accuracy on Synthesized Faults
"""

import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.engine import (
    compute_features,
    classify_sensor,
    detect_cohort_event,
    CLASS_LABELS,
)

class TestModelAccuracy(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)

    def test_classify_normal(self):
        target = 24.0 + np.random.normal(0, 0.08, 60)
        peers = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        feats = compute_features(target, peers)
        pred, proba = classify_sensor(feats)
        print("Normal test:", pred, "proba:", proba)
        self.assertEqual(pred, "Normal")

    def test_classify_spike(self):
        target = 24.0 + np.random.normal(0, 0.08, 60)
        peers = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        target[-1] += 12.0  # +12 deg spike on last tick
        feats = compute_features(target, peers)
        pred, proba = classify_sensor(feats)
        print("Spike test:", pred, "proba:", proba)
        self.assertEqual(pred, "Spike")

    def test_classify_drift(self):
        target = 24.0 + np.random.normal(0, 0.08, 60) + np.arange(60) * 0.035
        peers = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        feats = compute_features(target, peers)
        pred, proba = classify_sensor(feats)
        print("Drift test:", pred, "proba:", proba)
        self.assertEqual(pred, "Drift")

    def test_classify_stuck_at(self):
        target = 24.0 + np.random.normal(0, 0.08, 60)
        peers = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        target[-20:] = 25.0  # frozen for 20 ticks
        feats = compute_features(target, peers)
        pred, proba = classify_sensor(feats)
        print("Stuck-At test:", pred, "proba:", proba)
        self.assertEqual(pred, "Stuck-At")

    def test_classify_excessive_noise(self):
        target = 24.0 + np.random.normal(0, 0.08, 60)
        peers = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        target[-20:] = 24.0 + np.random.normal(0, 0.8, 20)  # 10x noise
        feats = compute_features(target, peers)
        pred, proba = classify_sensor(feats)
        print("Excessive Noise test:", pred, "proba:", proba)
        self.assertEqual(pred, "Excessive Noise")

    def test_classify_env_event(self):
        # 4 sensors shift together by +4.5 deg
        ramp = np.linspace(0, 4.5, 20)
        target = 24.0 + np.random.normal(0, 0.08, 60)
        target[-20:] += ramp
        peers = []
        for _ in range(3):
            p = 24.0 + np.random.normal(0, 0.08, 60)
            p[-20:] += ramp
            peers.append(p)
        # 1 peer does not shift
        peers.append(24.0 + np.random.normal(0, 0.08, 60))
        
        feats = compute_features(target, peers)
        pred, proba = classify_sensor(feats)
        print("Env Event test:", pred, "proba:", proba)
        # Check cohort consensus ratio
        self.assertGreater(feats["cohort_consensus_ratio"], 0.5)

if __name__ == "__main__":
    unittest.main()
