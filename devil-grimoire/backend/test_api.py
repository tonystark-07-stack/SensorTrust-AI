"""
API and Integration Tests for DEVIL GRIMOIRE
"""

import sys
import os
import io
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from app import database as db
import asyncio

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(db.init_db())
        cls.client = TestClient(app)

    def test_health_check(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "DEVIL GRIMOIRE")

    def test_scenario_injection_valid(self):
        scenarios = ["normal", "spike", "drift", "env_event", "stuck_at", "excessive_noise"]
        for s in scenarios:
            res = self.client.post("/api/scenario", json={"scenario": s})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["scenario"], s)

    def test_scenario_injection_unknown(self):
        res = self.client.post("/api/scenario", json={"scenario": "alien_invasion"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("Unknown scenario", data["message"])

    def test_scenario_injection_empty(self):
        res = self.client.post("/api/scenario", json={})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["scenario"], "normal")

    def test_get_alerts(self):
        res = self.client.get("/api/alerts?limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("alerts", data)
        self.assertIsInstance(data["alerts"], list)

    def test_acknowledge_alert_not_found(self):
        res = self.client.post("/api/alerts/9999999/acknowledge")
        self.assertEqual(res.status_code, 404)
        data = res.json()
        self.assertEqual(data["status"], "error")

    def test_get_stats(self):
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("stats", data)
        self.assertIsInstance(data["stats"], list)

    def test_get_trust_history(self):
        res = self.client.get("/api/trust-history/TEMP-01?limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("history", data)
        self.assertIsInstance(data["history"], list)

    def test_upload_csv_valid(self):
        csv_content = (
            "timestamp,TEMP-01,TEMP-02,TEMP-03,TEMP-04,TEMP-05\n"
            "0,24.1,24.2,24.0,24.3,24.1\n"
            "1,24.2,24.3,24.1,24.4,24.2\n"
        )
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = self.client.post("/api/upload-csv?speed=5", files=files)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["rows"], 2)
        self.assertEqual(data["speed"], 5)
        self.assertEqual(len(data["sensors"]), 5)

    def test_upload_csv_no_sensors(self):
        csv_content = "timestamp,label,notes\n0,foo,bar\n1,baz,qux\n"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = self.client.post("/api/upload-csv", files=files)
        # Should handle cleanly
        print("DEBUG CSV no sensors response:", res.status_code, res.json())

    def test_upload_csv_empty(self):
        files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
        res = self.client.post("/api/upload-csv", files=files)
        print("DEBUG CSV empty response:", res.status_code, res.json())

    def test_stop_csv(self):
        res = self.client.post("/api/stop-csv")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")

if __name__ == "__main__":
    unittest.main()
