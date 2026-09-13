"""Smoke tests: every endpoint that does not need a model.

Run with:  uv run python -m unittest discover -s tests

No pytest, no fixtures, no network, no API key. What this is for is the class of bug that
survives a syntax check and an import -- a name that only resolves on one code path, a
response shape the frontend depends on, a validation rule that quietly stopped rejecting.
Each test runs against a throwaway workspace, so it never touches real data.
"""
import os
import tempfile
import unittest
from pathlib import Path

WORKSPACE = tempfile.mkdtemp(prefix="toolkit-test-")
os.environ["WORKSPACE_DIR"] = WORKSPACE          # must be set before server.storage is imported

from fastapi.testclient import TestClient        # noqa: E402

from server.main import app                      # noqa: E402

client = TestClient(app)


class ConfigTests(unittest.TestCase):
    def test_fresh_workspace_has_working_defaults(self):
        # Deliberately no assertion about few-shot being empty: another test in this file sets
        # one, and unittest runs alphabetically. A test that only passes in a given order is
        # worse than no test.
        self.assertEqual(client.get("/api/settings").json()["source_tracking_default"], True)
        self.assertGreater(len(client.get("/api/schema").json()["fields"]), 0)
        self.assertGreater(len(client.get("/api/prompts").json()["extract"]), 100)
        self.assertGreater(len(client.get("/api/prompts").json()["judge"]), 100)
        self.assertIsInstance(client.get("/api/few-shot").json(), list)

    def test_schema_rejects_bad_field_names_and_types(self):
        bad_name = client.put("/api/schema", json={"fields": [{"name": "has space", "type": "string"}]})
        self.assertEqual(bad_name.status_code, 422)
        bad_type = client.put("/api/schema", json={"fields": [{"name": "ok", "type": "colour"}]})
        self.assertEqual(bad_type.status_code, 422)
        dupes = client.put("/api/schema", json={"fields": [{"name": "a"}, {"name": "a"}]})
        self.assertEqual(dupes.status_code, 400)
        self.assertIn("duplicate", dupes.json()["detail"])

    def test_schema_round_trips(self):
        fields = [{"name": "compound", "type": "string", "description": "what it is"},
                  {"name": "yield_percent", "type": "number", "description": "%"}]
        self.assertEqual(client.put("/api/schema", json={"fields": fields}).status_code, 200)
        self.assertEqual(client.get("/api/schema").json()["fields"], fields)

    def test_few_shot_rejects_malformed_examples(self):
        # the failure that used to save fine and only explode during a later extraction
        self.assertEqual(client.put("/api/few-shot", json=[{"text": "hi"}]).status_code, 422)
        self.assertEqual(client.put("/api/few-shot", json=[{"records": []}]).status_code, 422)
        good = [{"text": "a paper", "records": [{"compound": "x"}], "source": "p.pdf"}]
        self.assertEqual(client.put("/api/few-shot", json=good).status_code, 200)
        self.assertEqual(client.get("/api/few-shot").json()[0]["source"], "p.pdf")

    def test_api_key_name_must_be_an_env_var(self):
        self.assertEqual(client.put("/api/api-key", json={"name": "lower", "value": "x"}).status_code, 422)
        self.assertEqual(client.get("/api/api-key/not-a-var").status_code, 400)

    def test_env_keys_never_leaks_a_secret(self):
        os.environ["OPENAI_API_KEY"] = "sk-secretsecretsecret1234"
        body = client.get("/api/env-keys").json()
        self.assertTrue(body["OPENAI_API_KEY"]["set"])
        self.assertNotIn("secretsecret", body["OPENAI_API_KEY"]["preview"])
        self.assertTrue(body["OPENAI_API_KEY"]["preview"].endswith("1234"))


class CredentialTests(unittest.TestCase):
    """The very first thing a new install does is fail for want of a key. What it says then is
    the whole of the onboarding experience."""

    def test_a_missing_key_is_named_plainly(self):
        import os
        from server import llm
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            message = llm.missing_credentials("gpt-4o-mini")
            self.assertIsNotNone(message)
            self.assertIn("OPENAI_API_KEY", message)
            self.assertNotIn("workload_identity", message)   # the provider's wording, not ours
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved

    def test_an_empty_key_counts_as_missing(self):
        # `OPENAI_API_KEY=` in a copied .env.example is not a key, though litellm's own check
        # counts the empty string as present
        import os
        from server import llm
        saved = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = ""
        try:
            self.assertIsNotNone(llm.missing_credentials("gpt-4o-mini"))
        finally:
            if saved is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = saved

    def test_a_present_key_is_not_reported_missing(self):
        import os
        from server import llm
        saved = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-something"
        try:
            self.assertIsNone(llm.missing_credentials("gpt-4o-mini"))
        finally:
            if saved is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = saved


class PaperTests(unittest.TestCase):
    def test_missing_paper_is_404_not_500(self):
        self.assertEqual(client.get("/api/papers/nope").status_code, 404)
        self.assertEqual(client.get("/api/papers/nope/extraction").status_code, 404)
        self.assertEqual(client.get("/api/papers/nope/judgment").status_code, 404)

    def test_stages_report_missing_papers_per_item_rather_than_failing(self):
        for endpoint in ("/api/extract", "/api/judge"):
            body = client.post(endpoint, json={"paper_ids": ["nope"]}).json()
            self.assertIn("error", body[0], endpoint)

    def test_unparseable_pdf_fails_that_file_only_and_leaves_nothing_behind(self):
        from server.storage import PDFS
        result = client.post("/api/papers?source_tracking=true",
                             files={"files": ("bad.pdf", b"not a pdf", "application/pdf")}).json()
        self.assertIn("error", result[0])
        self.assertEqual(list(Path(PDFS).glob("*.pdf")), [], "a failed parse left an orphan PDF")


class ReviewTests(unittest.TestCase):
    """The save path for a reviewer's corrections -- the one kind of data here that cannot be
    regenerated by re-running anything."""

    def setUp(self):
        from server.storage import EXTRACTED, write_json
        self.paper = "paper-under-review"
        write_json(Path(EXTRACTED) / f"{self.paper}.json",
                   {"id": self.paper, "records": [{"compound": "as extracted"}]})

    def test_edit_preserves_the_models_original_output(self):
        version = client.get(f"/api/papers/{self.paper}/extraction").json()["version"]
        saved = client.put(f"/api/papers/{self.paper}/extraction",
                           json={"records": [{"compound": "corrected"}],
                                 "notes": {"0": {"flag": "bad", "note": "wrong"}},
                                 "version": version}).json()
        self.assertEqual(saved["records"][0]["compound"], "corrected")
        self.assertEqual(saved["model_records"][0]["compound"], "as extracted")
        self.assertEqual(saved["notes"]["0"]["flag"], "bad")

    def test_a_stale_save_is_refused_rather_than_silently_winning(self):
        stale = client.get(f"/api/papers/{self.paper}/extraction").json()["version"]
        client.put(f"/api/papers/{self.paper}/extraction",
                   json={"records": [{"compound": "first"}], "version": stale})
        second = client.put(f"/api/papers/{self.paper}/extraction",
                            json={"records": [{"compound": "second"}], "version": stale})
        self.assertEqual(second.status_code, 409)
        self.assertEqual(client.get(f"/api/papers/{self.paper}/extraction").json()["records"][0]["compound"],
                         "first", "the refused save overwrote the winner anyway")


class DeleteTests(unittest.TestCase):
    def setUp(self):
        from server.storage import EXTRACTED, JUDGED, PARSED, write_json
        self.pid = "deletable"
        write_json(Path(PARSED) / f"{self.pid}.json", {"id": self.pid, "filename": "d.pdf", "chunks": []})
        write_json(Path(EXTRACTED) / f"{self.pid}.json", {"id": self.pid, "records": [{"a": 1}]})
        write_json(Path(JUDGED) / f"{self.pid}.json", {"id": self.pid, "verdicts": []})

    def test_deleting_an_extraction_takes_its_judgment_with_it(self):
        # a verdict about records that no longer exist is worse than no verdict
        body = client.delete(f"/api/papers/{self.pid}/extraction").json()
        self.assertTrue(body["also_deleted_judgment"])
        self.assertEqual(client.get(f"/api/papers/{self.pid}/extraction").status_code, 404)
        self.assertEqual(client.get(f"/api/papers/{self.pid}/judgment").status_code, 404)
        self.assertEqual(client.get(f"/api/papers/{self.pid}").status_code, 200, "the paper itself went too")

    def test_deleting_a_judgment_leaves_the_extraction(self):
        self.assertEqual(client.delete(f"/api/papers/{self.pid}/judgment").status_code, 200)
        self.assertEqual(client.get(f"/api/papers/{self.pid}/judgment").status_code, 404)
        self.assertEqual(client.get(f"/api/papers/{self.pid}/extraction").status_code, 200)

    def test_deleting_a_paper_removes_every_stage(self):
        removed = client.delete(f"/api/papers/{self.pid}").json()["removed"]
        self.assertIn("parsed", removed)
        for path in ("", "/extraction", "/judgment"):
            self.assertEqual(client.get(f"/api/papers/{self.pid}{path}").status_code, 404, path)

    def test_deleting_what_is_not_there_is_404(self):
        self.assertEqual(client.delete("/api/papers/ghost").status_code, 404)
        self.assertEqual(client.delete("/api/papers/ghost/extraction").status_code, 404)


class SpendTests(unittest.TestCase):
    def test_per_paper_cost_is_listed_and_totalled(self):
        from server.storage import EXTRACTED, JUDGED, PARSED, write_json
        pid = "priced"
        write_json(Path(PARSED) / f"{pid}.json", {"id": pid, "filename": "p.pdf", "chunks": []})
        write_json(Path(EXTRACTED) / f"{pid}.json", {"id": pid, "records": [],
                   "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cost_usd": 0.0123}})
        write_json(Path(JUDGED) / f"{pid}.json", {"id": pid, "verdicts": [],
                   "usage": {"prompt_tokens": 500, "completion_tokens": 50, "cost_usd": 0.0077}})

        listed = next(p for p in client.get("/api/papers").json() if p["id"] == pid)
        self.assertAlmostEqual(listed["spend"]["cost_usd"], 0.02)
        self.assertEqual(listed["spend"]["tokens"], 1750)
        self.assertEqual(listed["spend"]["calls"], 2)

        paper = next(p for p in client.get("/api/report").json()["papers"] if p["id"] == pid)
        self.assertAlmostEqual(paper["cost_usd"], 0.02)
        self.assertEqual(paper["tokens"], 1750)
        client.delete(f"/api/papers/{pid}")


class ConcurrencyTests(unittest.TestCase):
    def test_a_second_run_is_refused_while_one_is_going(self):
        """Two tabs starting extractions on the same paper used to race for the same file."""
        from server.main import STAGE_LOCK
        STAGE_LOCK.acquire()
        try:
            for endpoint in ("/api/extract", "/api/judge"):
                busy = client.post(endpoint, json={"paper_ids": ["anything"]})
                self.assertEqual(busy.status_code, 409, endpoint)
                self.assertIn("already in progress", busy.json()["detail"])
        finally:
            STAGE_LOCK.release()
        # and the lock is genuinely released afterwards, not leaked by the error path
        self.assertNotEqual(client.post("/api/extract", json={"paper_ids": ["nope"]}).status_code, 409)


class ReportTests(unittest.TestCase):
    def test_report_and_exports_work_on_whatever_is_there(self):
        body = client.get("/api/report").json()
        for key in ("papers", "fields", "totals"):
            self.assertIn(key, body)
        for key in ("records", "verdicts", "spend", "papers_without_records"):
            self.assertIn(key, body["totals"])

    def test_a_paper_that_yields_nothing_still_counts_as_extracted(self):
        # it cost a call; counting it as unextracted hides both the work and the spend
        from server.storage import EXTRACTED, PARSED, write_json
        pid = "empty-but-processed"
        write_json(Path(PARSED) / f"{pid}.json", {"id": pid, "filename": "e.pdf", "chunks": []})
        write_json(Path(EXTRACTED) / f"{pid}.json", {"id": pid, "records": []})
        totals = client.get("/api/report").json()["totals"]
        self.assertGreaterEqual(totals["papers_without_records"], 1)
        paper = next(p for p in client.get("/api/report").json()["papers"] if p["id"] == pid)
        self.assertTrue(paper["extracted"])
        self.assertEqual(client.get("/api/papers").json()[0].get("n_records", "missing") is None, False)
        client.delete(f"/api/papers/{pid}")
        # flat_records() shares no state with build(); a NameError here only shows up on export
        self.assertEqual(client.get("/api/export.csv").status_code, 200)
        self.assertIn("paper_id", client.get("/api/export.csv").text.splitlines()[0])
        self.assertIsInstance(client.get("/api/export.json").json(), list)


class AppTests(unittest.TestCase):
    def test_the_page_and_its_assets_are_served(self):
        for path in ("/", "/app.js", "/style.css"):
            self.assertEqual(client.get(path).status_code, 200, path)


if __name__ == "__main__":
    unittest.main()
