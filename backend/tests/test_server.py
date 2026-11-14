"""Local control server: whitelist, validation, a real job run, CSV upload, panel and app pages."""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from fastapi.testclient import TestClient

    from analog_atlas import server
except ImportError:  # pragma: no cover - fastapi / httpx missing
    server = None


@unittest.skipIf(server is None, "fastapi/httpx not installed")
class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [mock.patch.object(server, "PANEL_CFG", tmp / "panel.json"),
                        mock.patch.object(server, "EXPORTS_DIR", tmp / "exports")]
        for p in self.patches:
            p.start()
        self.c = TestClient(server.app)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def wait(self, job_id, timeout=120):
        end = time.time() + timeout
        while time.time() < end:
            r = self.c.get(f"/jobs/{job_id}").json()
            if r["state"] != "running":
                return r
            time.sleep(0.3)
        self.fail("job did not finish")

    def test_unknown_action_is_rejected(self):
        self.assertEqual(self.c.post("/jobs", json={"action": "rm -rf /"}).status_code, 404)

    def test_earth_engine_actions_need_a_valid_project(self):
        self.assertEqual(self.c.post("/jobs", json={"action": "smoke"}).status_code, 422)
        bad = self.c.post("/jobs", json={"action": "smoke", "params": {"project": "x; del *"}})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.c.post("/panel/config", json={"project": "Bad Name"}).status_code, 422)
        ok = self.c.post("/panel/config", json={"project": "analog-atlas-spaeapps"})
        self.assertEqual(ok.json()["project"], "analog-atlas-spaeapps")
        self.assertEqual(self.c.get("/panel/status").json()["project"], "analog-atlas-spaeapps")

    def test_find_rejects_unknown_target(self):
        r = self.c.post("/jobs", json={"action": "find", "params": {"target": "atlantis"}})
        self.assertEqual(r.status_code, 422)

    def test_validate_job_runs_and_streams_its_log(self):
        job = self.c.post("/jobs", json={"action": "validate"}).json()
        done = self.wait(job["id"])
        self.assertEqual(done["state"], "done", done)
        log = "\n".join(self.c.get(f"/jobs/{job['id']}").json()["log"])
        self.assertIn("Summary", log)
        self.assertTrue(log.startswith("$ python -u -m analog_atlas.cli validate"))
        page = self.c.get(f"/jobs/{job['id']}?since=1").json()
        self.assertEqual(page["since"], 1)

    def test_upload_only_accepts_plain_csv_names(self):
        self.assertEqual(self.c.post("/exports/upload?name=evil.exe", content=b"x").status_code, 422)
        r = self.c.post("/exports/upload?name=..%2F..%2Fanalog_atlas_50km_000.csv", content=b"cell_id\n1_1\n")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["saved"], "analog_atlas_50km_000.csv")       # path stripped, kept in exports
        self.assertTrue((server.EXPORTS_DIR / "analog_atlas_50km_000.csv").exists())
        self.assertEqual(self.c.get("/panel/status").json()["export_csvs"], 1)

    def test_pages_and_api_share_one_origin(self):
        self.assertIn("Pipeline steps", self.c.get("/").text)
        self.assertIn("ANALOG ATLAS", self.c.get("/index.html").text)
        self.assertTrue(self.c.get("/health").json()["ok"])
        self.assertEqual(self.c.post("/find-analogs", json={"target_id": "jezero"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
