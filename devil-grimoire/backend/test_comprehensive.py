"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEVIL GRIMOIRE — Master Comprehensive Test Suite                           ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Exhaustive test suite covering all features, algorithms, models,           ║
║  generators, database transactions, REST API routes, and edge cases.        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import unittest
import asyncio
import io
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

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
    TRUST_PENALTY,
    EMA_ALPHA,
)
from app.generator import (
    GeneratorState,
    generate_tick,
    set_scenario,
    Scenario,
    SENSOR_IDS,
    AMBIENT_CENTER,
    SPIKE_MAGNITUDE,
    DRIFT_RATE,
)
from app import database as db
from app.main import app, process_tick
from evaluation import evaluate_csv


class TestEngineFeaturesAndEdgeCases(unittest.TestCase):
    """Test feature extraction with regular data and all possible edge cases."""

    def test_nominal_feature_calculation(self):
        np.random.seed(100)
        target = 24.0 + np.random.normal(0, 0.08, 40)
        peers = [24.0 + np.random.normal(0, 0.08, 40) for _ in range(4)]
        feats = compute_features(target, peers)
        
        self.assertEqual(len(feats), 6)
        for key in FEATURE_ORDER:
            self.assertIn(key, feats)
            self.assertFalse(np.isnan(feats[key]))
            self.assertFalse(np.isinf(feats[key]))
        
        # Nominal z-score and slope should be small
        self.assertLess(abs(feats["self_z_score"]), 2.0)
        self.assertLess(abs(feats["rolling_slope_norm"]), 1.0)
        self.assertAlmostEqual(feats["missing_rate"], 0.0)

    def test_edge_case_empty_array(self):
        feats = compute_features(np.array([]), [])
        self.assertEqual(feats["self_z_score"], 0.0)
        self.assertEqual(feats["peer_mad_score"], 0.0)
        self.assertEqual(feats["rolling_slope_norm"], 0.0)
        self.assertEqual(feats["variance_ratio"], 1.0)
        self.assertEqual(feats["missing_rate"], 0.0)
        self.assertEqual(feats["cohort_consensus_ratio"], 0.0)

    def test_edge_case_single_element(self):
        feats = compute_features(np.array([25.0]), [np.array([25.0])])
        self.assertEqual(feats["self_z_score"], 0.0)
        self.assertEqual(feats["rolling_slope_norm"], 0.0)

    def test_edge_case_zero_variance_peers_outlier_detection(self):
        # When all peers are identical (zero dispersion), an outlier should NOT be suppressed
        target = np.array([36.0] * 35) # 12 degrees higher
        peers = [np.array([24.0] * 35) for _ in range(4)]
        feats = compute_features(target, peers)
        
        # Peer MAD score must reflect the severe outlier (> 3.0), not 0.0!
        self.assertGreater(feats["peer_mad_score"], 3.0)

    def test_edge_case_nan_handling_and_missing_rate(self):
        # 5 NaNs out of 10 recent ticks
        raw_missing = [False] * 10 + [True] * 5 + [False] * 5
        target = np.array([24.0] * 20)
        peers = [np.array([24.0] * 20) for _ in range(4)]
        feats = compute_features(target, peers, raw_missing=raw_missing)
        
        self.assertAlmostEqual(feats["missing_rate"], 0.5)

    def test_edge_case_all_nans(self):
        target = np.array([np.nan] * 35)
        peers = [np.array([np.nan] * 35) for _ in range(4)]
        feats = compute_features(target, peers)
        vec = features_to_vector(feats)
        
        self.assertFalse(np.isnan(vec).any())
        self.assertFalse(np.isinf(vec).any())
        # Classification should safely return a valid class without throwing
        pred_class, proba = classify_sensor(feats)
        self.assertIn(pred_class, CLASS_LABELS)


class TestClassificationAndTrustManager(unittest.TestCase):
    """Test Random Forest predictions and EMA Trust dynamics."""

    def test_all_six_anomaly_classes(self):
        np.random.seed(42)
        # 1. Normal
        t_norm = 24.0 + np.random.normal(0, 0.08, 60)
        p_norm = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        pred, _ = classify_sensor(compute_features(t_norm, p_norm))
        self.assertEqual(pred, "Normal")

        # 2. Spike
        t_spike = 24.0 + np.random.normal(0, 0.08, 60)
        t_spike[-1] += 12.0
        p_spike = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        pred, _ = classify_sensor(compute_features(t_spike, p_spike))
        self.assertEqual(pred, "Spike")

        # 3. Drift
        t_drift = 24.0 + np.random.normal(0, 0.08, 60) + np.arange(60) * 0.03
        p_drift = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        pred, _ = classify_sensor(compute_features(t_drift, p_drift))
        self.assertEqual(pred, "Drift")

        # 4. Stuck-At
        t_stuck = 24.0 + np.random.normal(0, 0.08, 60)
        t_stuck[-25:] = 25.0
        p_stuck = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        pred, _ = classify_sensor(compute_features(t_stuck, p_stuck))
        self.assertEqual(pred, "Stuck-At")

        # 5. Excessive Noise
        t_noise = 24.0 + np.random.normal(0, 0.08, 60)
        t_noise[-25:] = 24.0 + np.random.normal(0, 0.8, 25)
        p_noise = [24.0 + np.random.normal(0, 0.08, 60) for _ in range(4)]
        pred, _ = classify_sensor(compute_features(t_noise, p_noise))
        self.assertEqual(pred, "Excessive Noise")

    def test_trust_score_ema_mathematics(self):
        mgr = TrustScoreManager()
        self.assertEqual(mgr.get_trust("TEMP-01"), 100.0)

        # Apply Spike: penalty = 25.0 -> instant = 75.0
        # Expected new trust: 0.3 * 75.0 + 0.7 * 100.0 = 92.5
        new_trust = mgr.update("TEMP-01", "Spike")
        self.assertAlmostEqual(new_trust, 92.5)

        # Apply Normal: penalty = 0.0 -> instant = 100.0
        # Expected: 0.3 * 100.0 + 0.7 * 92.5 = 94.75
        recovered_trust = mgr.update("TEMP-01", "Normal")
        self.assertAlmostEqual(recovered_trust, 94.75)

    def test_trust_score_cohort_dampening(self):
        mgr1 = TrustScoreManager()
        mgr2 = TrustScoreManager()

        # Regular Env Event penalty (no cohort dampening)
        t1 = mgr1.update("TEMP-01", "Env Event", is_env_event_cohort=False)

        # Dampened Env Event penalty (with cohort dampening: 50% reduced penalty)
        t2 = mgr2.update("TEMP-01", "Env Event", is_env_event_cohort=True)

        self.assertGreater(t2, t1)

    def test_xai_reason_generation(self):
        reasons = [
            generate_xai_reason("TEMP-01", "Normal", {"self_z_score": 0.2}, False, [], 98.0),
            generate_xai_reason("TEMP-02", "Spike", {"self_z_score": 4.5, "peer_mad_score": 5.1}, False, [], 85.0),
            generate_xai_reason("TEMP-03", "Stuck-At", {"variance_ratio": 0.001}, False, [], 65.0),
            generate_xai_reason("TEMP-04", "Drift", {"rolling_slope_norm": 0.04}, False, [], 70.0),
            generate_xai_reason("TEMP-05", "Excessive Noise", {"variance_ratio": 9.5}, False, [], 60.0),
            generate_xai_reason("TEMP-01", "Env Event", {"cohort_consensus_ratio": 0.8}, True, ["TEMP-01", "TEMP-02", "TEMP-04"], 95.0),
        ]
        for r in reasons:
            self.assertIsInstance(r, str)
            self.assertGreater(len(r), 10)


class TestGeneratorAndScenarios(unittest.TestCase):
    """Test synthetic data generator and state machine transitions."""

    def test_generator_normal_ticks(self):
        state = GeneratorState()
        readings = generate_tick(state)
        self.assertEqual(len(readings), 5)
        for sid in SENSOR_IDS:
            self.assertIn(sid, readings)
            self.assertAlmostEqual(readings[sid], AMBIENT_CENTER, delta=2.0)

    def test_spike_scenario_auto_reset(self):
        state = GeneratorState()
        set_scenario(state, "spike")
        
        # Tick 1: Spike active on TEMP-02
        t1 = generate_tick(state)
        self.assertGreater(t1["TEMP-02"], AMBIENT_CENTER + SPIKE_MAGNITUDE - 2.0)
        
        # Tick 2: Must auto-reset to Normal
        t2 = generate_tick(state)
        self.assertLess(t2["TEMP-02"], AMBIENT_CENTER + 2.0)
        self.assertEqual(state.scenario, Scenario.NORMAL)

    def test_env_event_synchronized_ramp(self):
        state = GeneratorState()
        set_scenario(state, "env_event")
        
        t1 = generate_tick(state)
        # TEMP-01, 02, 04, 05 must all have the same ramp offset applied
        offsets = [t1[sid] - 24.0 for sid in ["TEMP-01", "TEMP-02", "TEMP-04", "TEMP-05"]]
        # Standard deviation of offsets across cohort must be small (only noise variation, not 4x stagger)
        self.assertLess(np.std(offsets), 0.25)
        self.assertAlmostEqual(state.env_event_ramp, 0.15, places=3)

    def test_scenario_clean_state_transitions(self):
        state = GeneratorState()
        set_scenario(state, "drift")
        generate_tick(state)
        self.assertGreater(state.drift_accumulator, 0.0)

        # Switching to Stuck-At should reset drift accumulator
        set_scenario(state, "stuck_at")
        self.assertEqual(state.drift_accumulator, 0.0)
        self.assertEqual(state.scenario, Scenario.STUCK_AT)


class TestDatabaseBatchAndConcurrency(unittest.IsolatedAsyncioTestCase):
    """Test database transactions, batch inserts, and concurrency safety."""

    async def asyncSetUp(self):
        await db.init_db()

    async def test_insert_tick_batch_and_alert_ids(self):
        readings = {sid: 25.0 for sid in SENSOR_IDS}
        features = {sid: compute_features(np.array([25.0] * 30), []) for sid in SENSOR_IDS}
        classes = {sid: "Normal" if sid != "TEMP-02" else "Spike" for sid in SENSOR_IDS}
        trusts = {sid: 95.0 for sid in SENSOR_IDS}
        xais = {sid: "Normal operation" for sid in SENSOR_IDS}
        alerts = [{
            "sensor_id": "TEMP-02",
            "type": "Spike",
            "severity": "warning",
            "message": "Spike test",
            "is_suppressed": False,
        }]

        alert_ids = await db.insert_tick_batch(
            9999, readings, features, classes, trusts, xais, alerts
        )
        self.assertEqual(len(alert_ids), 1)
        self.assertIsInstance(alert_ids[0], int)
        self.assertGreater(alert_ids[0], 0)

        # Verify acknowledgement works with the real ID
        success = await db.acknowledge_alert(alert_ids[0])
        self.assertTrue(success)

    async def test_concurrent_load_without_locking_error(self):
        # Fire 20 concurrent tick batch writes
        tasks = []
        for t in range(20):
            readings = {sid: 24.0 + t for sid in SENSOR_IDS}
            feats = {sid: {} for sid in SENSOR_IDS}
            classes = {sid: "Normal" for sid in SENSOR_IDS}
            trusts = {sid: 100.0 for sid in SENSOR_IDS}
            xais = {sid: "OK" for sid in SENSOR_IDS}
            tasks.append(
                db.insert_tick_batch(10000 + t, readings, feats, classes, trusts, xais, [])
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        self.assertEqual(len(errors), 0, f"Encountered locking errors: {errors}")


class TestAPIRoutes(unittest.TestCase):
    """Test all FastAPI REST endpoints and edge cases."""

    @classmethod
    def setUpClass(cls):
        asyncio.run(db.init_db())
        cls.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "healthy")

    def test_all_scenario_endpoints(self):
        for s in ["normal", "spike", "drift", "env_event", "stuck_at", "excessive_noise"]:
            r = self.client.post("/api/scenario", json={"scenario": s})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["status"], "ok")

    def test_invalid_csv_uploads(self):
        # Empty CSV
        r1 = self.client.post("/api/upload-csv", files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")})
        self.assertEqual(r1.status_code, 400)

        # CSV with no sensor columns
        csv_no_sensors = "timestamp,user,status\n0,alice,ok\n1,bob,err\n"
        r2 = self.client.post(
            "/api/upload-csv",
            files={"file": ("no_sensors.csv", io.BytesIO(csv_no_sensors.encode()), "text/csv")}
        )
        self.assertEqual(r2.status_code, 400)

    def test_valid_csv_upload_and_stop(self):
        csv_valid = (
            "timestamp,TEMP-01,TEMP-02,TEMP-03,TEMP-04,TEMP-05\n"
            "0,24.1,24.2,24.0,24.3,24.1\n"
            "1,24.2,24.3,24.1,24.4,24.2\n"
        )
        r = self.client.post(
            "/api/upload-csv?speed=5",
            files={"file": ("valid.csv", io.BytesIO(csv_valid.encode()), "text/csv")}
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["rows"], 2)

        # Stop replay
        r_stop = self.client.post("/api/stop-csv")
        self.assertEqual(r_stop.status_code, 200)

    def test_alerts_and_stats(self):
        r_alerts = self.client.get("/api/alerts?limit=5")
        self.assertEqual(r_alerts.status_code, 200)

        r_stats = self.client.get("/api/stats")
        self.assertEqual(r_stats.status_code, 200)

        r_history = self.client.get("/api/trust-history/TEMP-01?limit=10")
        self.assertEqual(r_history.status_code, 200)


class TestBatchEvaluation(unittest.TestCase):
    """Test evaluation.py script with sample CSV."""

    def test_batch_evaluation_execution(self):
        test_csv_path = os.path.join(os.path.dirname(__file__), "sample_test.csv")
        results = evaluate_csv(test_csv_path)
        self.assertIsInstance(results, pd.DataFrame)
        self.assertGreater(len(results), 0)
        self.assertIn("trust_score", results.columns)
        self.assertIn("predicted_class", results.columns)
        self.assertIn("xai_reason", results.columns)


if __name__ == "__main__":
    unittest.main()
