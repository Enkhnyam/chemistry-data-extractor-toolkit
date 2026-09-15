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
from contextlib import contextmanager
from pathlib import Path

WORKSPACE = tempfile.mkdtemp(prefix="toolkit-test-")
os.environ["WORKSPACE_DIR"] = WORKSPACE          # must be set before server.storage is imported
os.environ["TOOLKIT_SEED_DEMO"] = "0"            # these test the empty workspace, not the demo

from fastapi.testclient import TestClient        # noqa: E402

from server import config                        # noqa: E402
from server.main import app                      # noqa: E402
from server.storage import EXTRACTED as EXTRACTED_DIR, JUDGED as JUDGED_DIR  # noqa: E402

client = TestClient(app)


@contextmanager
def configured():
    """A workspace with everything a run needs, torn back down afterwards. Stages refuse until a
    model with a key, a schema and a prompt are all present, so most tests need this."""
    from server import config, models
    saved = client.put("/api/models", json=[{"name": "test", "model": "gpt-4o-mini"}]).json()
    pid = saved["ids"][0]
    os.environ[models.key_var(pid)] = "sk-test-not-a-real-key"
    config.save_settings({"extract_model": pid, "judge_model": pid})
    config.save_schema([{"name": "compound", "type": "string", "description": "what it is"}])
    config.save_extract_prompt("Extract every reaction this paper reports.")
    config.save_judge_prompt("Check each record against the paper.")
    try:
        yield pid
    finally:
        os.environ.pop(models.key_var(pid), None)
        client.put("/api/models", json=[])
        config.save_settings({"extract_model": "", "judge_model": ""})
        config.save_schema([])
        config.EXTRACT_PROMPT_FILE.unlink(missing_ok=True)
        config.JUDGE_PROMPT_FILE.unlink(missing_ok=True)


class ConfigTests(unittest.TestCase):
    def test_a_fresh_workspace_is_genuinely_empty(self):
        """Nothing is filled in for you. Someone who downloads this finds no schema, no model
        and no prompts -- only examples of each, shown as placeholder text."""
        settings = client.get("/api/settings").json()
        self.assertEqual(settings["source_tracking_default"], True, "a real default, not a leftover")
        cfg = client.get("/api/models").json()
        self.assertEqual(cfg["profiles"], [], "a model was prefilled")
        self.assertEqual(cfg["extract"], "")
        self.assertEqual(cfg["judge"], "")

        schema = client.get("/api/schema").json()
        self.assertEqual(schema["fields"], [], "a schema was prefilled")
        self.assertFalse(schema["set"])
        self.assertGreater(len(schema["placeholder"]), 0, "no example schema to show")

        self.assertIsInstance(client.get("/api/few-shot").json(), list)

    def test_nothing_leaks_from_the_example_into_the_values(self):
        # the placeholders are PET chemistry; the values must not be
        prompts = client.get("/api/prompts").json()
        blob = (prompts["extract"] + prompts["judge"]).lower()
        for word in ("pet", "glycolysis", "bhet", "ionic liquid"):
            self.assertNotIn(word, blob, f"{word!r} leaked from the example into a real value")

    def test_prompts_start_empty_but_offer_an_example(self):
        # A prompt must be written, not silently inherited from somebody else's chemistry --
        # but the example is there to read and adapt.
        body = client.get("/api/prompts").json()
        for kind in ("extract", "judge"):
            self.assertGreater(len(body["placeholders"][kind]), 500, kind)
        if not body["extract_set"]:
            self.assertEqual(body["extract"], "")

    def test_stages_refuse_to_run_without_a_prompt(self):
        from server import config
        with configured():
            config.EXTRACT_PROMPT_FILE.unlink(missing_ok=True)
            config.JUDGE_PROMPT_FILE.unlink(missing_ok=True)
            for endpoint, word in (("/api/extract", "extraction prompt"), ("/api/judge", "judge rubric")):
                r = client.post(endpoint, json={"paper_ids": ["anything"]})
                self.assertEqual(r.status_code, 400, endpoint)
                self.assertIn(word, r.json()["detail"])

    def test_a_fully_configured_workspace_unblocks_the_stages(self):
        """Every blocker must clear before a run is possible: model, key, schema, prompt."""
        from server import config
        with configured():
            ready = client.get("/api/readiness").json()
            self.assertEqual(ready["extract"]["blockers"], [])
            self.assertEqual(ready["judge"]["blockers"], [])
            # and it names what it will call, so the checklist can stop saying "not chosen"
            self.assertTrue(ready["extract"]["model"]["name"])
            r = client.post("/api/extract", json={"paper_ids": ["nope"]})
            self.assertEqual(r.status_code, 200)          # now fails per-paper, not as a gate
            self.assertIn("error", r.json()[0])

    def test_readiness_names_each_missing_piece(self):
        from server import config
        config.save_settings({"extract_model": "", "judge_model": ""})
        config.save_schema([])
        config.EXTRACT_PROMPT_FILE.unlink(missing_ok=True)
        blockers = " ".join(client.get("/api/readiness").json()["extract"]["blockers"])
        self.assertIn("model", blockers)
        self.assertIn("fields", blockers)
        self.assertIn("extraction prompt", blockers)

    def test_a_model_without_a_key_is_named_as_the_blocker(self):
        from server import config
        pid = client.put("/api/models", json=[{"name": "Keyless", "model": "gpt-4o-mini"}]).json()["ids"][0]
        config.save_settings({"extract_model": pid})
        blockers = " ".join(client.get("/api/readiness").json()["extract"]["blockers"])
        self.assertIn("Keyless", blockers)
        self.assertIn("API key", blockers)
        client.put("/api/models", json=[])

    def test_a_model_string_with_no_provider_is_caught_before_the_call(self):
        """The failure this replaces: "Qwen3.8-27B" saved, tested and configured without
        complaint, then every extraction died on litellm's "LLM Provider NOT provided" -- after
        the papers were parsed and paid for."""
        from server import config, models
        pid = client.put("/api/models", json=[{"name": "Local", "model": "Qwen3.8-27B"}]).json()["ids"][0]
        os.environ[models.key_var(pid)] = "any"
        config.save_settings({"extract_model": pid})
        blockers = " ".join(client.get("/api/readiness").json()["extract"]["blockers"])
        self.assertIn("openai/Qwen3.8-27B", blockers)
        # and the model list says so where the model is being configured
        profile = client.get("/api/models").json()["profiles"][0]
        self.assertTrue(profile["provider_problem"])
        # a prefixed string is accepted and the warning goes away
        client.put("/api/models", json=[{"id": pid, "name": "Local", "model": "openai/Qwen3.8-27B"}])
        self.assertEqual(client.get("/api/models").json()["profiles"][0]["provider_problem"], "")
        os.environ.pop(models.key_var(pid), None)
        client.put("/api/models", json=[])
        config.save_settings({"extract_model": ""})

    def test_the_only_model_is_used_without_a_second_decision(self):
        """Adding your first model used to leave both stages pointing at nothing, so the Extract
        page asked for a model you had just entered."""
        from server import config
        config.save_settings({"extract_model": "", "judge_model": ""})
        pid = client.put("/api/models", json=[{"name": "Only", "model": "gpt-4o-mini"}]).json()["ids"][0]
        settings = client.get("/api/settings").json()
        self.assertEqual(settings["extract_model"], pid)
        self.assertEqual(settings["judge_model"], pid)
        # but a stage someone pointed somewhere on purpose is never moved
        second = client.put("/api/models", json=[
            {"id": pid, "name": "Only", "model": "gpt-4o-mini"},
            {"name": "Other", "model": "gpt-4o"}]).json()["ids"][1]
        self.assertEqual(client.get("/api/settings").json()["extract_model"], pid)
        self.assertNotEqual(second, pid)
        client.put("/api/models", json=[])
        config.save_settings({"extract_model": "", "judge_model": ""})

    def test_a_stage_never_keeps_pointing_at_a_deleted_model(self):
        """Replace your only model and the stage used to keep naming the one you removed, which
        reads on the Extract page as "the model you chose no longer exists" and no way forward."""
        from server import config
        config.save_settings({"extract_model": "", "judge_model": ""})
        old = client.put("/api/models", json=[{"name": "Old", "model": "gpt-4o-mini"}]).json()["ids"][0]
        self.assertEqual(client.get("/api/settings").json()["extract_model"], old)
        new = client.put("/api/models", json=[{"name": "New", "model": "gpt-4o"}]).json()["ids"][0]
        self.assertNotEqual(new, old)
        self.assertEqual(client.get("/api/settings").json()["extract_model"], new)
        self.assertEqual(client.get("/api/readiness").json()["extract"]["model"]["name"], "New")
        client.put("/api/models", json=[])
        config.save_settings({"extract_model": "", "judge_model": ""})

    def test_the_version_token_survives_a_browsers_json_parser(self):
        """The bug this pins: version was st_mtime_ns, about 1.8e18. JavaScript's JSON.parse
        turns any number past 2^53 into the nearest float, so the browser sent back a rounded
        token and EVERY review save was refused as a conflict with an edit that never happened.
        Python's big ints round-tripped it perfectly, so the API tests saw nothing -- which is
        why this test parses the response the way a browser would."""
        import json
        from server.storage import EXTRACTED, PARSED, write_json
        write_json(PARSED / "vp.json", {"id": "vp", "filename": "vp.pdf", "source_tracking": True,
                                        "chunks": [{"id": "c1", "text": "t", "html": "<p>t</p>"}]})
        write_json(EXTRACTED / "vp.json", {"id": "vp", "records": [{"a": 1}], "usage": {}})

        raw = client.get("/api/papers/vp/extraction").text
        # parse_int=float is what a browser does to every integer in a JSON document
        as_browser_sees_it = json.loads(raw, parse_int=float)["version"]
        self.assertIsInstance(as_browser_sees_it, str, "a number here loses precision in the browser")

        r = client.put("/api/papers/vp/extraction",
                       json={"records": [{"a": 2}], "notes": {}, "version": as_browser_sees_it})
        self.assertEqual(r.status_code, 200, r.text)
        # and a genuinely stale token is still refused
        stale = client.put("/api/papers/vp/extraction",
                           json={"records": [{"a": 3}], "notes": {}, "version": as_browser_sees_it})
        self.assertEqual(stale.status_code, 409)
        (EXTRACTED / "vp.json").unlink()
        (PARSED / "vp.json").unlink()

    def test_the_demo_can_be_loaded_back_beside_your_own_papers(self):
        """The regression this pins: scoping clear() to the demo's own files meant one paper of
        your own left the workspace permanently non-empty, and the seeder it called refused any
        workspace that was not empty -- so "Load the demo" silently did nothing, for exactly the
        person who had cleared it and wanted it back."""
        from server import demo
        from server.storage import PDFS, PARSED, CONFIG
        if not demo.available():
            self.skipTest("no demo/ in this checkout")
        for d in (PDFS, PARSED, EXTRACTED_DIR, JUDGED_DIR, CONFIG):
            for f in list(d.iterdir()):
                if not f.name.startswith("."):
                    f.unlink()
        demo.MARKER.unlink(missing_ok=True)

        (PDFS / "mine.pdf").write_bytes(b"%PDF-1.4 mine")
        self.assertFalse(demo.is_empty())

        r = client.post("/api/demo/load?replace=true").json()
        self.assertTrue(r["is_demo"], "the demo did not load into a non-empty workspace")
        self.assertEqual(len(list(PDFS.glob("*.pdf"))), 3, "two demo papers plus yours")
        self.assertTrue((PDFS / "mine.pdf").exists(), "your paper must survive a demo load")
        self.assertTrue(config.get_schema(), "the demo's schema comes with it")

        # and it round-trips: clear again and only yours is left
        client.post("/api/demo/clear")
        self.assertEqual([p.name for p in PDFS.glob("*.pdf")], ["mine.pdf"])
        (PDFS / "mine.pdf").unlink()
        config.save_schema([])

    def test_clearing_the_demo_keeps_your_own_papers_and_edits(self):
        """It used to empty the workspace outright, which took papers you had added with it."""
        import shutil, tempfile
        from server import demo
        from server.storage import PDFS, PARSED, EXTRACTED, CONFIG
        if not demo.available():
            self.skipTest("no demo/ in this checkout")
        for d in (PDFS, PARSED, EXTRACTED, CONFIG):
            for f in list(d.iterdir()):
                if not f.name.startswith("."):
                    f.unlink()
        demo.MARKER.unlink(missing_ok=True)
        self.assertTrue(demo.seed())

        (PDFS / "mine.pdf").write_bytes(b"%PDF-1.4 mine")
        config.save_schema([{"name": "my_field", "type": "string", "description": "mine"}])
        config.save_settings({"extract_model": "chosen-by-me"})

        removed = client.post("/api/demo/clear").json()["removed"]
        self.assertEqual(removed["papers"], 2)
        self.assertTrue((PDFS / "mine.pdf").exists(), "your own paper must survive")
        self.assertEqual([f["name"] for f in config.get_schema()], ["my_field"],
                         "a schema you edited is yours and stays")
        self.assertIn("schema.json", removed["kept_config"])
        self.assertEqual(config.get_settings()["extract_model"], "chosen-by-me",
                         "clearing the demo must not unpick your model")
        self.assertFalse(demo.state()["is_demo"])
        (PDFS / "mine.pdf").unlink()
        config.save_schema([])
        config.save_settings({"extract_model": "", "judge_model": ""})

    def test_the_export_carries_the_judges_reasoning_not_only_its_verdict(self):
        """A verdict with no argument behind it cannot be checked by anyone later."""
        from server.storage import EXTRACTED, JUDGED, PARSED, write_json
        from server import report
        write_json(PARSED / "jr.json", {"id": "jr", "filename": "jr.pdf", "chunks": []})
        write_json(EXTRACTED / "jr.json", {"id": "jr", "records": [{"compound": "ZnCl2"}]})
        write_json(JUDGED / "jr.json", {"id": "jr", "verdicts": [
            {"record_index": 0, "verdict": "incorrect", "bad_fields": ["compound"],
             "critique": "Table 2 says FeCl3, not ZnCl2.", "drop_record": False,
             "fixes": [{"field": "compound", "value": "FeCl3", "evidence": "Table 2, entry 4"}]}]})
        columns, rows = report.flat_records()
        for column in ("judge_critique", "judge_proposed", "judge_evidence", "judge_would_drop"):
            self.assertIn(column, columns)
        row = next(r for r in rows if r["paper_id"] == "jr")
        self.assertEqual(row["judge_critique"], "Table 2 says FeCl3, not ZnCl2.")
        self.assertIn("compound", row["judge_proposed"])
        self.assertIn("Table 2, entry 4", row["judge_evidence"])
        for name in ("jr.json",):
            (EXTRACTED / name).unlink(); (JUDGED / name).unlink(); (PARSED / name).unlink()

    def test_the_bundle_carries_the_data_the_config_and_no_keys(self):
        """A CSV of records cannot say which model wrote it, under which prompt, against which
        schema, or which rows a human corrected. The bundle is the answer to that."""
        import io, json, zipfile
        from server.storage import EXTRACTED, PARSED, write_json
        with configured():
            write_json(PARSED / "bp.json", {"id": "bp", "filename": "bp.pdf", "chunks": [
                {"id": "11111111-1111-5111-8111-111111111111", "text": "t"}],
                "source_tracking": True})
            write_json(EXTRACTED / "bp.json", {"id": "bp", "model": "gpt-4o-mini",
                                               "records": [{"compound": "ZnCl2"}],
                                               "usage": {"prompt_tokens": 10}})
            body = client.get("/api/export.zip").content
            z = zipfile.ZipFile(io.BytesIO(body))
            names = set(z.namelist())
            for expected in ("manifest.json", "README.md", "data/records.csv", "data/papers.csv",
                             "config/schema.json", "config/extract_prompt.txt",
                             "config/models.json", "extracted/bp.json", "parsed/bp.json"):
                self.assertIn(expected, names)

            manifest = json.loads(z.read("manifest.json"))
            self.assertEqual(manifest["papers"], 1)
            self.assertEqual(manifest["records"], 1)
            self.assertEqual(manifest["models"]["per_paper"]["bp"]["extract"], "gpt-4o-mini")

            # the one thing that must never be in a bundle
            whole = b"".join(z.read(n) for n in names)
            self.assertNotIn(b"sk-test-not-a-real-key", whole)
            self.assertNotIn(b"api_key", whole)
            self.assertNotIn(b"key_var", whole)

            self.assertIn("compound", z.read("data/records.csv").decode())
            (EXTRACTED / "bp.json").unlink()
            (PARSED / "bp.json").unlink()

    def test_static_files_must_be_revalidated(self):
        """Without this the browser guesses a freshness window in hours, and a fix ships to a
        server whose users keep running the old app.js -- which looks exactly like the fix not
        working."""
        r = client.get("/app.js")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("cache-control"), "no-cache")

    def test_chunks_are_tagged_short_and_citations_resolve_back(self):
        """The model is shown c1, c2, ... and what gets stored is still the chunk's real uuid.

        A uuid costs about fifteen tokens to reproduce exactly and models are bad at it: the
        same paper finished in 224s with the tags off and timed out at 280s with uuids on."""
        from server import parsing
        chunks = [{"id": "15587205-10fe-5d54-ba31-99bc4d2ddda1", "text": "first"},
                  {"id": "6d15a148-36f2-5ec9-8f87-03c8d6d71674", "text": "second"}]
        text = parsing.chunks_to_text(chunks, True)
        self.assertIn("ID: c1", text)
        self.assertIn("ID: c2", text)
        self.assertNotIn(chunks[0]["id"], text, "the uuid must not reach the model")

        # the label it was given
        self.assertEqual(parsing.resolve_labels(["c2"], chunks), [chunks[1]["id"]])
        # a uuid it produced anyway
        self.assertEqual(parsing.resolve_labels([chunks[0]["id"]], chunks), [chunks[0]["id"]])
        # a citation pointing at nothing is dropped, not stored
        self.assertEqual(parsing.resolve_labels(["c9", "nonsense", None], chunks), [])
        # and duplicates collapse
        self.assertEqual(parsing.resolve_labels(["c1", "C1"], chunks), [chunks[0]["id"]])
        # source tracking off still means no tags at all
        self.assertNotIn("ID:", parsing.chunks_to_text(chunks, False))

    def test_the_judge_is_not_shown_ids_it_is_told_to_ignore(self):
        from server.judge import build_messages
        recs = [{"catalyst": "ZnCl2", "source_chunk_ids": ["15587205-10fe-5d54-ba31-99bc4d2ddda1"]}]
        sent = build_messages("rubric", "text", recs)[1]["content"]
        self.assertIn("ZnCl2", sent)
        self.assertNotIn("source_chunk_ids", sent)

    def test_a_worked_example_is_saved_as_typed(self):
        """Examples are global -- the same one or two go to every paper -- so the text is the
        example, not a pointer to a paper that may since have been deleted."""
        client.put("/api/few-shot", json=[
            {"text": "Table 1. entry 1, 190 C, 82% yield", "records": [{"yield_percent": 82}],
             "source": "typed in"}])
        got = client.get("/api/few-shot").json()
        self.assertEqual(got[0]["text"], "Table 1. entry 1, 190 C, 82% yield")
        self.assertIsNone(got[0]["paper_id"])
        client.put("/api/few-shot", json=[])

    def test_extraction_and_judging_can_use_different_models(self):
        """The reason profiles exist: a strong extractor and a separate auditor, each with its
        own endpoint and key, in one workspace."""
        from server import config, models
        saved = client.put("/api/models", json=[
            {"name": "Extractor", "model": "azure/deploy", "api_base": "https://x.azure.com",
             "api_version": "2024-12-01-preview"},
            {"name": "Auditor", "model": "gpt-4o-mini"}]).json()
        ext, jud = saved["ids"]
        self.assertNotEqual(ext, jud)
        os.environ[models.key_var(ext)] = "azure-key"
        os.environ[models.key_var(jud)] = "openai-key"
        try:
            config.save_settings({"extract_model": ext, "judge_model": jud})
            ep, jp = models.call_params(ext), models.call_params(jud)
            self.assertEqual(ep["model"], "azure/deploy")
            self.assertEqual(ep["api_base"], "https://x.azure.com")
            self.assertEqual(ep["api_version"], "2024-12-01-preview")
            self.assertEqual(ep["api_key"], "azure-key")
            # the auditor carries neither the other one's endpoint nor its key
            self.assertEqual(jp["model"], "gpt-4o-mini")
            self.assertNotIn("api_base", jp)
            self.assertEqual(jp["api_key"], "openai-key")
        finally:
            for pid in (ext, jud):
                os.environ.pop(models.key_var(pid), None)
            client.put("/api/models", json=[])
            config.save_settings({"extract_model": "", "judge_model": ""})

    def test_a_model_key_never_comes_back_in_a_listing(self):
        from server import models
        pid = client.put("/api/models", json=[{"name": "Secret", "model": "m"}]).json()["ids"][0]
        client.put(f"/api/models/{pid}/key", json={"value": "sk-do-not-leak-this"})
        blob = client.get("/api/models").text
        self.assertNotIn("sk-do-not-leak-this", blob)
        self.assertTrue(client.get("/api/models").json()["profiles"][0]["key_set"])
        os.environ.pop(models.key_var(pid), None)
        client.put("/api/models", json=[])

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
        good = [{"text": "a paper", "records": [{"compound": "x"}], "source": "p.pdf",
                 "paper_id": "p-123"}]
        self.assertEqual(client.put("/api/few-shot", json=good).status_code, 200)
        saved = client.get("/api/few-shot").json()[0]
        self.assertEqual(saved["source"], "p.pdf")
        # the editor reopens on the right paper only if this survives the round trip
        self.assertEqual(saved["paper_id"], "p-123")

    def test_api_key_name_must_be_an_env_var(self):
        self.assertEqual(client.put("/api/api-key", json={"name": "lower", "value": "x"}).status_code, 422)
        self.assertEqual(client.get("/api/api-key/not-a-var").status_code, 400)

    def test_env_keys_never_leaks_a_secret(self):
        os.environ["OPENAI_API_KEY"] = "sk-secretsecretsecret1234"
        body = client.get("/api/env-keys").json()
        self.assertTrue(body["OPENAI_API_KEY"]["set"])
        self.assertNotIn("secretsecret", body["OPENAI_API_KEY"]["preview"])
        self.assertTrue(body["OPENAI_API_KEY"]["preview"].endswith("1234"))


class PaperTests(unittest.TestCase):
    def test_missing_paper_is_404_not_500(self):
        self.assertEqual(client.get("/api/papers/nope").status_code, 404)
        self.assertEqual(client.get("/api/papers/nope/extraction").status_code, 404)
        self.assertEqual(client.get("/api/papers/nope/judgment").status_code, 404)

    def test_stages_report_missing_papers_per_item_rather_than_failing(self):
        with configured():
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
        with configured():
            STAGE_LOCK.acquire()
            try:
                for endpoint in ("/api/extract", "/api/judge"):
                    busy = client.post(endpoint, json={"paper_ids": ["anything"]})
                    self.assertEqual(busy.status_code, 409, endpoint)
                    self.assertIn("already in progress", busy.json()["detail"])
            finally:
                STAGE_LOCK.release()
            # and the lock is genuinely released, not leaked by the error path
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


class DemoTests(unittest.TestCase):
    """The demo seeds a workspace and gets out of the way again.

    What matters is not that it copies files but that it cannot do so over anyone's work, and
    that clearing it takes the schema and prompts with it -- a demo schema left behind is the
    silent default the rest of this design refuses to have.
    """

    def setUp(self):
        import tempfile
        from server import demo
        self.demo = demo
        self.dir = Path(tempfile.mkdtemp(prefix="toolkit-demo-"))
        for name in demo.STAGES:
            (self.dir / name).mkdir(parents=True, exist_ok=True)
        self._real = {k: v for k, v in demo.STAGES.items()}
        demo.STAGES.update({name: self.dir / name for name in demo.STAGES})
        self._marker = demo.MARKER
        demo.MARKER = self.dir / ".demo"
        # The module-level opt-out is for the other tests; these are the ones about seeding.
        self._optout = os.environ.pop("TOOLKIT_SEED_DEMO", None)

    def tearDown(self):
        import shutil
        self.demo.STAGES.update(self._real)
        self.demo.MARKER = self._marker
        if self._optout is not None:
            os.environ["TOOLKIT_SEED_DEMO"] = self._optout
        shutil.rmtree(self.dir, ignore_errors=True)

    @unittest.skipUnless(Path("demo/pdfs").is_dir(), "no demo/ in this checkout")
    def test_it_seeds_an_empty_workspace_and_says_so(self):
        self.assertTrue(self.demo.seed_if_empty())
        self.assertTrue(self.demo.state()["is_demo"])
        self.assertTrue(list((self.dir / "pdfs").glob("*.pdf")))
        self.assertTrue((self.dir / "config" / "schema.json").exists())

    @unittest.skipUnless(Path("demo/pdfs").is_dir(), "no demo/ in this checkout")
    def test_it_refuses_to_seed_over_anything(self):
        (self.dir / "pdfs" / "mine.pdf").write_bytes(b"%PDF-1.4 not really")
        self.assertFalse(self.demo.seed_if_empty(), "seeded on top of a user's own paper")
        self.assertEqual([p.name for p in (self.dir / "pdfs").glob("*")], ["mine.pdf"])

    @unittest.skipUnless(Path("demo/pdfs").is_dir(), "no demo/ in this checkout")
    def test_clearing_takes_the_untouched_config_with_it(self):
        """A demo schema left behind would be applied to your papers without you choosing it.

        settings.json is the exception and stays: it holds which model each stage calls, which
        is the user's, not the demo's."""
        self.demo.seed_if_empty()
        self.demo.clear()
        self.assertFalse(self.demo.state()["is_demo"])
        self.assertFalse((self.dir / "config" / "schema.json").exists(),
                         "a demo schema survived the clear and would be applied silently")
        self.assertFalse((self.dir / "config" / "extract_prompt.txt").exists())
        self.assertFalse(any((self.dir / "pdfs").glob("*.pdf")), "demo papers must go")

