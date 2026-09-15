"""FastAPI app: parse PDFs, extract records, judge them. Three verbs, three stages, all
reading/writing plain JSON under workspace/. See README for the full endpoint list --
this file is short enough to read top to bottom instead.
"""
import asyncio
import csv
import io
import json
import os
import re
import threading
import time
import zipfile
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv, set_key
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
# Keys live beside the code by default, which is what you want when you cloned this and ran it.
# Under Docker they must not: the image root is the container's own writable layer, so a key
# added through Settings survived until the next `docker compose up --build` and then silently
# vanished. The Dockerfile sets ENV_FILE=/data/.env, inside the mounted volume, so the same
# setting persists the way the workspace does.
ENV_FILE = Path(os.environ.get("ENV_FILE", ROOT / ".env"))
load_dotenv(ENV_FILE)

from . import config, demo, extraction, judge, llm, models, parsing, report, timings  # noqa: E402  (after load_dotenv)
from .storage import (EXTRACTED, JUDGED, PARSED, PDFS, list_papers, paper_id_for, read_json,  # noqa: E402
                      require, version_of, write_json)

# One stage at a time per server. Two browser tabs starting extractions on the same paper wrote
# the same file from two threads and the loser's records vanished; refusing the second is both
# simpler and more honest than trying to merge them.
STAGE_LOCK = threading.Lock()


def single_flight(stage: str):
    if not STAGE_LOCK.acquire(blocking=False):
        raise HTTPException(409, f"Another run is already in progress. Wait for it to finish "
                                 f"before starting {stage}.")


app = FastAPI(title="Extraction Toolkit")


@app.exception_handler(Exception)
async def clean_error(request: Request, exc: Exception):
    """An unhandled exception on this app is almost always a bad LLM response, a bad key, or
    a bad config edit -- never something a user should see as a raw traceback. One line:
    exception type + message, which is exactly what a person can act on or paste back to us."""
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


# ---------- config: schema / prompts / few-shot / model / api key ----------

@app.get("/api/settings")
def get_settings():
    return {**config.get_settings(), "placeholders": config.placeholders()}


@app.put("/api/settings")
def put_settings(patch: dict):
    return config.save_settings(patch)


class ModelProfile(BaseModel):
    id: str | None = None
    name: str = ""
    model: str = ""
    api_base: str = ""
    api_version: str = ""


def _key_is_set(var: str) -> bool:
    import os
    return bool(os.environ.get(var))


@app.get("/api/models")
def get_models():
    """The configured endpoints, plus which stage uses which. Never the secrets."""
    settings = config.get_settings()
    return {"profiles": models.listing(_key_is_set),
            "extract": settings.get("extract_model", ""),
            "judge": settings.get("judge_model", "")}


@app.put("/api/models")
def put_models(profiles: list[ModelProfile]):
    saved = models.save_all([p.model_dump() for p in profiles])
    settings = config.get_settings()
    live = {m["id"] for m in saved}
    # This is a whole-list replace, so a stage can be left pointing at a model that has just
    # been deleted. Forgetting a dead pointer is what lets the rule below take over; without it
    # you delete your only model, add its replacement, and the stage still names the ghost.
    patch = {f"{st}_model": "" for st in ("extract", "judge")
             if settings.get(f"{st}_model") and settings[f"{st}_model"] not in live}
    # A workspace with exactly one model and a stage pointing at nothing is never what anyone
    # meant -- the dropdown is a choice between one option. Only unset stages are filled, so
    # this can never move a stage somebody deliberately pointed elsewhere.
    if len(saved) == 1:
        patch.update({f"{st}_model": saved[0]["id"] for st in ("extract", "judge")
                      if not settings.get(f"{st}_model") or f"{st}_model" in patch})
    if patch:
        config.save_settings(patch)
    return {"profiles": models.listing(_key_is_set),
            "ids": [p["id"] for p in saved]}


class ModelKey(BaseModel):
    value: str = Field(min_length=1)


@app.put("/api/models/{profile_id}/key")
def put_model_key(profile_id: str, body: ModelKey):
    if not models.get(profile_id):
        raise HTTPException(404, "no such model configuration")
    return put_api_key(ApiKey(name=models.key_var(profile_id), value=body.value))


class Discover(BaseModel):
    api_base: str = ""
    api_key: str = ""


@app.post("/api/models/{profile_id}/discover")
def discover_models(profile_id: str, body: Discover):
    """Ask the endpoint which models it actually serves.

    The failure this exists for: a model string that is right in spirit and wrong in every
    character. An OpenAI-compatible server will happily report `Qwen 3.8 27B` -- spaces and
    all -- and no amount of guessing gets there from "Qwen3.8-27B". Every such server answers
    GET /models, so the honest answer is to ask it rather than make the user divine it.
    """
    profile = models.get(profile_id) or {}
    base = (body.api_base or profile.get("api_base") or "").rstrip("/")
    if not base:
        return {"ok": False, "error": "This needs an endpoint. Providers with no endpoint "
                                      "(OpenAI, Anthropic) publish their model names instead."}
    key = body.api_key or os.environ.get(models.key_var(profile_id), "")
    try:
        r = httpx.get(f"{base}/models", timeout=20,
                      headers={"Authorization": f"Bearer {key}"} if key else {})
        r.raise_for_status()
        payload = r.json()
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    entries = payload.get("data", payload) if isinstance(payload, dict) else payload
    ids = [m.get("id") for m in entries if isinstance(m, dict) and m.get("id")] \
        if isinstance(entries, list) else []
    if not ids:
        return {"ok": False, "error": f"{base}/models answered, but with nothing that looks "
                                      f"like a model list."}
    # Prefixed here, not in the browser: what makes a string callable is litellm's business,
    # and the caller should not have to know that an endpoint implies the openai provider.
    return {"ok": True, "models": [{"id": i, "string": f"openai/{i}"} for i in sorted(ids)]}


@app.post("/api/models/{profile_id}/test")
def test_model_profile(profile_id: str):
    """One tiny completion against this exact configuration -- the only way to find out whether
    a model string, an endpoint and a key actually work together before a batch depends on it."""
    blocked = models.blockers(profile_id, "this model")
    if blocked:
        return {"ok": False, "error": " ".join(blocked)}
    params = models.call_params(profile_id)
    started = time.monotonic()
    try:
        resp = llm.complete(params, [{"role": "user", "content": "Reply with OK."}],
                            max_tokens=64)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "model": params["model"],
            "reply": (resp.choices[0].message.content or "").strip()[:40],
            "seconds": round(time.monotonic() - started, 1)}


class SchemaField(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
                      description="letters, digits, underscore; must not start with a digit")
    type: Literal["string", "number", "integer", "boolean"] = "string"
    description: str = ""


class SchemaBody(BaseModel):
    fields: list[SchemaField]


@app.get("/api/schema")
def get_schema():
    fields = config.get_schema()
    return {"fields": fields, "set": bool(fields),
            "placeholder": config.placeholders()["schema"]}


@app.put("/api/schema")
def put_schema(body: SchemaBody):
    names = [f.name for f in body.fields]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise HTTPException(400, f"duplicate field name(s): {', '.join(sorted(dupes))}")
    fields = [f.model_dump() for f in body.fields]
    config.save_schema(fields)
    return {"fields": fields}


@app.get("/api/prompts")
def get_prompts():
    """The prompts as written, plus the examples to show as placeholder text where they are
    empty. `set` is what the run buttons gate on -- whitespace does not count as a prompt."""
    extract, judge = config.get_extract_prompt(), config.get_judge_prompt()
    return {"extract": extract, "judge": judge,
            "extract_set": bool(extract.strip()), "judge_set": bool(judge.strip()),
            "placeholders": config.placeholders()}


@app.put("/api/prompts")
def put_prompts(body: dict):
    if "extract" in body:
        config.save_extract_prompt(body["extract"])
    if "judge" in body:
        config.save_judge_prompt(body["judge"])
    return get_prompts()


class FewShotExample(BaseModel):
    text: str = Field(min_length=1, description="the example paper text shown to the model")
    records: list[dict] = Field(description="the records the model should output for that text")
    source: str | None = Field(None, description="where it came from, for the examples list")
    paper_id: str | None = Field(None, description="the parsed paper it was built from, so the "
                                                   "editor can preselect it when reopened")


@app.get("/api/few-shot")
def get_few_shot():
    return config.get_few_shot()


@app.put("/api/few-shot")
def put_few_shot(examples: list[FewShotExample]):
    """Validated here, not just at extraction time -- a malformed example used to save fine
    and only surface as a bare KeyError the next time someone ran Extract, days later and with
    no connection back to the edit that caused it."""
    dumped = [e.model_dump() for e in examples]
    config.save_few_shot(dumped)
    return dumped


# Common provider env vars litellm reads; shown in Settings as suggestions, not a hard limit --
# any UPPER_SNAKE_CASE name can be set (Azure alone needs three: AZURE_API_KEY, AZURE_API_BASE,
# AZURE_API_VERSION, none of which fit a fixed "pick your provider" dropdown).
KNOWN_ENV_VARS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
                  "AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION"]


SECRET_HINTS = ("KEY", "SECRET", "TOKEN", "PASSWORD")


def _preview(name: str, value: str) -> str:
    """Enough of a value to tell two entries apart, never enough to use a secret.

    Only actual secrets are masked: an api_base or an api_version is configuration, and hiding
    it just makes the reader open a terminal to check what they set."""
    if not value:
        return ""
    if not any(hint in name for hint in SECRET_HINTS):
        return value
    return "•" * 8 + value[-4:] if len(value) > 12 else "•" * len(value)


@app.get("/api/env-keys")
def get_env_keys():
    """Which known env vars are set, plus a masked preview so Settings can list them as rows.
    Limited to the fixed list (not a scan of the whole environment): a scan also surfaces
    unrelated vars a shell profile happens to export -- noise that undermines the one thing
    this table is for. Endpoints (api_base) are shown in full; secrets never are."""
    import os
    # Custom variables come from .env itself rather than a scan of the environment: what the
    # user put in this project's file is theirs to see; what their shell exports is not ours.
    from dotenv import dotenv_values
    extra = [k for k in dotenv_values(ENV_FILE) if k not in KNOWN_ENV_VARS] if ENV_FILE.exists() else []
    return {name: {"set": bool(os.environ.get(name)),
                   "preview": _preview(name, os.environ.get(name, ""))}
            for name in KNOWN_ENV_VARS + sorted(extra)}


class ApiKey(BaseModel):
    name: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$",
                      description="an env var name, e.g. OPENAI_API_KEY or AZURE_API_BASE")
    value: str = Field(min_length=1)


@app.put("/api/api-key")
def put_api_key(body: ApiKey):
    """Written to .env (not returned by any GET) and applied to this process immediately,
    so a freshly-entered key works without a server restart."""
    import os
    ENV_FILE.touch(exist_ok=True)
    # quote_mode="never": python-dotenv defaults to writing KEY='value' and strips the quotes
    # again on load -- but Docker's env_file does not. A quoted api_base reached the container
    # as "'https://...'" and every call failed on a URL nobody could see was wrong.
    set_key(str(ENV_FILE), body.name, body.value, quote_mode="never")
    os.environ[body.name] = body.value
    return {"saved": body.name}


@app.get("/api/api-key/{name}")
def reveal_api_key(name: str):
    """The stored value, so Settings can show and edit a key rather than only overwrite one
    blind. Local-only tool, local-only .env, and it takes a deliberate click -- but it is the
    one endpoint here that returns a secret, so it is never part of any list response."""
    import os
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise HTTPException(400, "not an environment variable name")
    return {"name": name, "value": os.environ.get(name, "")}


def _blockers(stage: str) -> list[str]:
    """What is still missing before this stage can run, in the order a person would fix it.

    The UI shows the same list as a checklist; both call this so they can never disagree about
    whether a run is possible."""
    settings = config.get_settings()
    missing = list(models.blockers(settings.get(f"{stage}_model", ""),
                                   "extraction" if stage == "extract" else "judging"))
    if not config.get_schema():
        missing.append("Define the fields a record has, in Settings.")
    if stage == "extract" and not config.get_extract_prompt().strip():
        missing.append("Write an extraction prompt. Until you do, nothing tells the model what "
                       "to pull out.")
    if stage == "judge" and not config.get_judge_prompt().strip():
        missing.append("Write a judge rubric. Until you do, nothing tells the model what counts "
                       "as a good record.")
    return missing


def _stage_readiness(stage: str) -> dict:
    """Everything a stage page needs to say what is missing AND what is already chosen.

    The checklist used to read a long-dead settings["model"] and so reported "Model: not chosen"
    to people who had chosen one -- the row was describing a field nothing writes any more. It
    now names the profile the stage will actually call, from the same lookup the run uses.
    """
    profile = models.get(config.get_settings().get(f"{stage}_model", "") or "")
    return {"blockers": _blockers(stage),
            "model": models.public(profile, _key_is_set) if profile else None}


@app.get("/api/readiness")
def get_readiness():
    return {stage: _stage_readiness(stage) for stage in ("extract", "judge")}


# A clone arrives with an empty workspace and an eight-step checklist, which tells a new user
# what to do but not what they would get. Seeding the demo means the first screen is a finished
# project instead: two open-access papers, parsed, extracted and judged. It runs once, only into
# an empty workspace, and writes real files rather than installing defaults -- see server/demo.py
# for why that distinction is the whole design.
_SEEDED = demo.seed_if_empty()


@app.get("/api/demo")
def get_demo():
    return demo.state()


@app.post("/api/demo/load")
def load_demo(replace: bool = False):
    """Put the demo into the workspace on request.

    Seeding happens automatically only into an empty workspace, which is right -- it must never
    overwrite anyone's work. But that left no way to ask for it, and anyone who had already
    opened Settings before pulling this version had a workspace that was no longer empty and no
    route to the demo except deleting directories by hand. This is that route; `replace` is the
    button that says it will clear what is there first.
    """
    single_flight("a load")
    try:
        if not demo.available():
            raise HTTPException(404, "There is no demo/ directory in this checkout.")
        if not (replace or demo.is_empty()):
            raise HTTPException(409, "The workspace is not empty. Clear it first, or use "
                                     "Replace to drop what is there and load the demo.")
        demo.seed(replace=replace)
    finally:
        STAGE_LOCK.release()
    return demo.state()


@app.post("/api/demo/clear")
def clear_demo():
    """Remove the demo's papers and its untouched config, leaving everything else alone.

    Anything you added or edited survives -- see demo.clear() for why the config is treated
    differently from the papers."""
    single_flight("a clear")
    try:
        removed = demo.clear()
    finally:
        STAGE_LOCK.release()
    return {"cleared": True, "removed": removed, **demo.state()}


@app.get("/api/status")
def get_status():
    """One call describing where this workspace is in the pipeline.

    The interface needs it on every page: to badge the nav with what exists, and to show a
    first-run guide that knows which steps are already done. Cheap enough to fetch each render
    -- it reads directory listings, not paper contents."""
    papers = list_papers()
    settings = config.get_settings()
    extracted = [p for p in papers if p["extracted"]]
    records = sum(p["n_records"] or 0 for p in papers)
    return {
        "papers": len(papers),
        "extracted": len(extracted),
        "judged": sum(1 for p in papers if p["judged"]),
        "records": records,
        "has_model": bool(settings.get("extract_model")),
        "has_schema": bool(config.get_schema()),
        "has_extract_prompt": bool(config.get_extract_prompt().strip()),
        "has_judge_prompt": bool(config.get_judge_prompt().strip()),
        "blockers": {stage: _blockers(stage) for stage in ("extract", "judge")},
        # The interface says so out loud rather than letting someone mistake the demo's PET
        # chemistry for something it inferred from their own papers.
        "is_demo": (_d := demo.state())["is_demo"],
        # So the getting-started guide can offer the demo to someone whose workspace was already
        # non-empty when they pulled, and knows whether loading it would replace anything.
        "demo_available": _d["available"],
        "workspace_empty": _d["workspace_empty"],
    }


# ---------- papers: upload + parse ----------

@app.post("/api/papers")
async def upload_papers(files: list[UploadFile], source_tracking: bool | None = None):
    single_flight("a parse")
    try:
        return await _upload(files, source_tracking)
    finally:
        STAGE_LOCK.release()


async def _upload(files: list[UploadFile], source_tracking: bool | None):
    with_source = config.get_settings()["source_tracking_default"] if source_tracking is None else source_tracking
    results = []
    for f in files:
        content = await f.read()
        pid = paper_id_for(f.filename, content)
        pdf_path = PDFS / f"{pid}.pdf"
        pdf_path.write_bytes(content)
        started = time.monotonic()
        try:
            # In a thread, not inline: docling is seconds-to-minutes of blocking CPU work, and
            # running it on the event loop froze every other request for its whole duration --
            # so switching tabs mid-parse left the next page stuck on "Loading" until the PDF
            # finished, which looked exactly like a crash.
            chunks = await asyncio.to_thread(parsing.parse_pdf, pdf_path, pid)
        except Exception as e:
            # Don't leave the PDF behind: it has no parsed record, so nothing in the UI can see
            # it or clean it up, and a folder of retried failures would silently fill the disk.
            pdf_path.unlink(missing_ok=True)
            results.append({"id": pid, "filename": f.filename, "error": f"{type(e).__name__}: {e}"})
            continue
        write_json(PARSED / f"{pid}.json", {
            "id": pid, "filename": f.filename, "source_tracking": with_source, "chunks": chunks,
        })
        seconds = time.monotonic() - started
        # Measured per byte, because that is what the browser can see before it uploads. Chunk
        # count only exists once the parse is over, which is too late to estimate with.
        timings.record("parse", seconds, len(content), unit="bytes")
        results.append({"id": pid, "filename": f.filename, "n_chunks": len(chunks),
                        "source_tracking": with_source, "seconds": round(seconds, 1)})
    return results


@app.get("/api/timings")
def get_timings():
    return timings.estimates()


@app.get("/api/papers")
def get_papers():
    return list_papers()


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str):
    try:
        paper = require(PARSED / f"{paper_id}.json", "paper")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return {**paper, "chunks": parsing.with_html(paper["chunks"])}


@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: str):
    """The paper and everything derived from it. Irreversible, and it takes any reviewer
    corrections with it -- the frontend says so before asking."""
    removed = []
    for path in (PDFS / f"{paper_id}.pdf", PARSED / f"{paper_id}.json",
                 EXTRACTED / f"{paper_id}.json", JUDGED / f"{paper_id}.json"):
        if path.exists():
            path.unlink()
            removed.append(path.parent.name)
    if not removed:
        raise HTTPException(404, f"nothing to delete for {paper_id}")
    return {"deleted": paper_id, "removed": removed}


@app.delete("/api/papers/{paper_id}/extraction")
def delete_extraction(paper_id: str):
    """The extraction, and with it the judgment -- a verdict about records that no longer
    exist is worse than no verdict. Corrections and notes go too; they live in this file."""
    path = EXTRACTED / f"{paper_id}.json"
    if not path.exists():
        raise HTTPException(404, f"no extraction for {paper_id}")
    path.unlink()
    judged = JUDGED / f"{paper_id}.json"
    also = judged.exists()
    if also:
        judged.unlink()
    return {"deleted": "extraction", "also_deleted_judgment": also}


@app.delete("/api/papers/{paper_id}/judgment")
def delete_judgment(paper_id: str):
    path = JUDGED / f"{paper_id}.json"
    if not path.exists():
        raise HTTPException(404, f"no judgment for {paper_id}")
    path.unlink()
    return {"deleted": "judgment"}


# ---------- extraction ----------

class PaperIds(BaseModel):
    paper_ids: list[str]


@app.post("/api/extract")
def run_extract(body: PaperIds):
    single_flight("an extraction")
    try:
        return _extract(body)
    finally:
        STAGE_LOCK.release()


def _extract(body: PaperIds):
    settings = config.get_settings()
    blockers = _blockers("extract")
    if blockers:
        raise HTTPException(400, " ".join(blockers))
    prompt = config.get_extract_prompt()
    schema_fields = config.get_schema()
    few_shot = config.get_few_shot()
    params = models.call_params(settings.get("extract_model", ""))

    results = []
    for pid in body.paper_ids:
        try:
            paper = require(PARSED / f"{pid}.json", "paper")
        except FileNotFoundError as e:
            results.append({"id": pid, "error": str(e)})
            continue
        with_source = paper.get("source_tracking", True)
        text = parsing.chunks_to_text(paper["chunks"], with_source)
        started = time.monotonic()
        try:
            records, usage = extraction.run_extraction(params, prompt, schema_fields,
                                                       few_shot, text, with_source)
        except Exception as e:
            results.append({"id": pid, "error": f"{type(e).__name__}: {e}"})
            continue
        seconds = time.monotonic() - started
        # The model cited short labels (c17); what gets stored is the chunk's real id, so
        # everything downstream -- the review pane, the export -- keeps working unchanged.
        if with_source:
            for record in records:
                record["source_chunk_ids"] = parsing.resolve_labels(
                    record.get("source_chunk_ids"), paper["chunks"])
        timings.record("extract", seconds, len(paper["chunks"]), unit="chunks")
        write_json(EXTRACTED / f"{pid}.json",
                   {"id": pid, "records": records, "usage": usage, "model": params.get("model")})
        results.append({"id": pid, "n_records": len(records), "seconds": round(seconds, 1),
                        "usage": usage})
    return results


@app.get("/api/papers/{paper_id}/extraction")
def get_extraction(paper_id: str):
    path = EXTRACTED / f"{paper_id}.json"
    try:
        return {**require(path, "extraction"), "version": version_of(path)}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


class ReviewedExtraction(BaseModel):
    records: list[dict]
    notes: dict[str, dict] = Field(default_factory=dict, description="record index -> {flag, note}")
    # int is accepted only so a browser tab left open across this change fails as a conflict
    # -- "reload the page" -- rather than as an unexplained 422.
    version: str | int | None = Field(None, description="the version this edit was based on; an "
                                                        "opaque string, never parsed as a number")


@app.put("/api/papers/{paper_id}/extraction")
def put_extraction(paper_id: str, body: ReviewedExtraction):
    """A reviewer's corrections, from either review page (editing a field, or applying one of
    the judge's proposed fixes). The model's own output is kept under `model_records` the first
    time anything is edited: a corrected dataset that cannot be diffed against what the model
    actually said is not evidence of anything."""
    path = EXTRACTED / f"{paper_id}.json"
    try:
        current = require(path, "extraction")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e

    # Refuse to overwrite an edit this one never saw -- another tab, or a second server on the
    # same workspace. Silently winning that race loses a reviewer's corrections, which is the
    # one kind of data this tool cannot regenerate.
    if body.version is not None and str(body.version) != version_of(path):
        raise HTTPException(409, "This paper changed somewhere else since you opened it. "
                                 "Reload the page to pick up those edits before saving yours.")

    saved = {
        "id": paper_id,
        "records": body.records,
        "notes": body.notes,
        "model_records": current.get("model_records", current["records"]),
        "usage": current.get("usage", {}),
        "model": current.get("model"),
        "edited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(path, saved)
    return {**saved, "version": version_of(path)}


# ---------- judge ----------

@app.post("/api/judge")
def run_judge_endpoint(body: PaperIds):
    single_flight("a judge run")
    try:
        return _judge(body)
    finally:
        STAGE_LOCK.release()


def _judge(body: PaperIds):
    settings = config.get_settings()
    blockers = _blockers("judge")
    if blockers:
        raise HTTPException(400, " ".join(blockers))
    rubric = config.get_judge_prompt()
    params = models.call_params(settings.get("judge_model", ""))

    results = []
    for pid in body.paper_ids:
        try:
            paper = require(PARSED / f"{pid}.json", "paper")
            extracted = require(EXTRACTED / f"{pid}.json", "extraction")
        except FileNotFoundError as e:
            results.append({"id": pid, "error": str(e)})
            continue
        with_source = paper.get("source_tracking", True)
        text = parsing.chunks_to_text(paper["chunks"], with_source)
        started = time.monotonic()
        try:
            verdicts, usage = judge.run_judge(params, rubric, text, extracted["records"])
        except Exception as e:
            results.append({"id": pid, "error": f"{type(e).__name__}: {e}"})
            continue
        seconds = time.monotonic() - started
        timings.record("judge", seconds, len(extracted["records"]), unit="records")
        write_json(JUDGED / f"{pid}.json",
                   {"id": pid, "verdicts": verdicts, "usage": usage, "model": params.get("model"),
                    # what the judge actually saw, so a later edit can be spotted as post-dating it
                    "judged_records": extracted["records"]})
        results.append({"id": pid, "n_verdicts": len(verdicts), "seconds": round(seconds, 1),
                        "usage": usage})
    return results


@app.get("/api/papers/{paper_id}/judgment")
def get_judgment(paper_id: str):
    try:
        return require(JUDGED / f"{paper_id}.json", "judgment")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


# ---------- report + export ----------

@app.get("/api/report")
def get_report():
    return report.build()


@app.get("/api/export.csv")
def export_csv():
    columns, rows = report.flat_records()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="records.csv"'})


@app.get("/api/export.json")
def export_json():
    _, rows = report.flat_records()
    return Response(json.dumps(rows, indent=1, ensure_ascii=False), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="records.json"'})


def _csv_bytes(columns, rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


@app.get("/api/export.zip")
def export_bundle(pdfs: bool = False):
    """The whole project as one folder: the data, what produced it, and what it cost.

    A CSV of records on its own is not reproducible -- it cannot say which model wrote it, under
    which prompt, against which schema, or which rows a human then corrected. This is the same
    shape the source project deposits: data beside the config and a manifest that pins both.

    No key ever enters the bundle; the model profiles are copied without their key variables.
    """
    record_columns, record_rows = report.flat_records()
    paper_columns, paper_rows = report.papers_table()
    summary = report.build()
    settings = config.get_settings()
    profiles = models.listing(_key_is_set)

    manifest = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "chemistry-data-extractor-toolkit",
        "git_commit": _git_commit(),
        "papers": len(paper_rows),
        "records": len(record_rows),
        "models": {
            "extract": (models.get(settings.get("extract_model", "")) or {}).get("model"),
            "judge": (models.get(settings.get("judge_model", "")) or {}).get("model"),
            # per paper too: a corpus is often built across more than one model
            "per_paper": {r["paper_id"]: {"extract": r["extract_model"], "judge": r["judge_model"]}
                          for r in paper_rows},
        },
        "spend": summary.get("totals", {}).get("spend", {}),
        "source_tracking_default": settings.get("source_tracking_default", True),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        bundle.writestr("README.md", _bundle_readme(manifest))
        bundle.writestr("data/records.csv", _csv_bytes(record_columns, record_rows))
        bundle.writestr("data/records.json", json.dumps(record_rows, indent=1, ensure_ascii=False))
        bundle.writestr("data/papers.csv", _csv_bytes(paper_columns, paper_rows))
        bundle.writestr("data/report.json", json.dumps(summary, indent=2, ensure_ascii=False))

        # config: everything that decides what a run produces, and nothing that authenticates it
        bundle.writestr("config/schema.json",
                        json.dumps({"fields": config.get_schema()}, indent=2, ensure_ascii=False))
        bundle.writestr("config/extract_prompt.txt", config.get_extract_prompt())
        bundle.writestr("config/judge_prompt.txt", config.get_judge_prompt())
        bundle.writestr("config/few_shot.json",
                        json.dumps(config.get_few_shot(), indent=2, ensure_ascii=False))
        bundle.writestr("config/models.json", json.dumps(
            [{k: v for k, v in m.items()
              if k in ("id", "name", "model", "api_base", "api_version")} for m in profiles],
            indent=2, ensure_ascii=False))

        # the per-paper working files, so a reviewer can trace any row back to its chunk
        for stage, directory in (("extracted", EXTRACTED), ("judged", JUDGED),
                                 ("parsed", PARSED)):
            for path in sorted(directory.glob("*.json")):
                bundle.write(path, f"{stage}/{path.name}")
        if pdfs:
            for path in sorted(PDFS.glob("*.pdf")):
                bundle.write(path, f"papers/{path.name}")

    stamp = time.strftime("%Y%m%d", time.gmtime())
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f'attachment; filename="extraction-bundle-{stamp}.zip"'})


def _git_commit() -> str | None:
    """Which version of the tool produced this. None outside a checkout, which is honest."""
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                       text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
    except Exception:
        return None


def _bundle_readme(manifest: dict) -> str:
    m = manifest["models"]
    return f"""# Extraction bundle

{manifest['records']} records from {manifest['papers']} paper(s), exported
{manifest['exported_at']} by chemistry-data-extractor-toolkit.

## What is here

- `data/records.csv`, `data/records.json` — one row per record, with the judge's verdict and
  any reviewer flag or note. `extract_model` and `judge_model` say what produced each row.
- `data/papers.csv` — one row per paper: chunks in, records out, model, tokens, cost.
- `data/report.json` — completeness by field, what the judge changed, totals.
- `config/` — the schema, both prompts, the worked examples and the model settings that
  produced this. API keys are not included.
- `parsed/`, `extracted/`, `judged/` — the working files, so any row can be traced back to the
  chunk it came from. `source_chunk_ids` on a record refers to `chunks[].id` in `parsed/`.
- `papers/` — the source PDFs, if you exported with them.

## Reading it

Extraction model: `{m['extract'] or 'not set'}` · judge model: `{m['judge'] or 'not set'}`.
Papers may differ from these if the corpus was built across more than one model; see
`models.per_paper` in `manifest.json`.

`model_records` in `extracted/*.json` is what the model originally said, kept beside the
corrected records the moment anything was edited. A corrected dataset that cannot be diffed
against the model's own output is not evidence of anything.
"""


# ---------- prompt authoring ----------

class PromptRequest(BaseModel):
    kind: Literal["extract", "judge"]
    domain: str = Field(min_length=2, description="what this corpus is about, in the user's words")
    paper_id: str | None = Field(None, description="a parsed paper to ground the wording in")


PROMPT_BRIEF = """You write prompts for other language models. Write the {what} for a system
that reads one scientific paper at a time and {task}.

The domain is: {domain}

The output schema each record must fill is exactly this, and the prompt you write must not
invent, rename or drop fields:
{schema}

Requirements for the prompt you produce:
- Open by stating what the model extracts and from what kind of paper.
- Say which rows or statements to INCLUDE and, just as explicitly, which to SKIP -- cited
  literature values, modelling/optimisation designs, values that appear only in a figure, and
  anything that is not a measurement this paper made.
- Give the domain-specific conventions a careful reader of {domain} would apply: how to name
  substances, which units each numeric field takes and how to convert into them, and how to
  propagate conditions stated once for a whole table.
- Say that unreported values are null, never zero and never a placeholder.
{source_rule}
- Be concrete and specific to {domain}. No hedging, no meta-commentary.

Return ONLY the prompt text itself, ready to paste. No preamble, no markdown fences."""

TASKS = {
    "extract": ("extraction prompt", "returns one structured record per experiment it reports"),
    "judge": ("judging rubric", "audits records another model already extracted from it, "
                                "deciding field by field whether the paper supports them and "
                                "proposing corrected values where it does not"),
}


@app.post("/api/generate-prompt")
def generate_prompt(body: PromptRequest):
    """Draft a prompt for a domain, grounded in this project's own schema and, optionally, in
    one of the user's own papers -- the wording that matters ("propagate a footnote condition
    to every row of that table") comes from seeing real papers, not from a blank page."""
    schema = config.get_schema()
    if not schema:
        raise HTTPException(400, "define the schema first — the prompt is written around it")
    fields = "\n".join(f"- {f['name']} ({f.get('type', 'string')}): {f.get('description') or 'no description given'}"
                       for f in schema)
    what, task = TASKS[body.kind]
    source_rule = ("- End with a section telling the model that the text is split into chunks "
                   "tagged \"ID: <uuid>\", and that every record must list in source_chunk_ids "
                   "each chunk that supplied one of its values."
                   if config.get_settings()["source_tracking_default"] else
                   "- The text carries no chunk ids, so say nothing about citing sources.")
    brief = PROMPT_BRIEF.format(what=what, task=task, domain=body.domain, schema=fields,
                                source_rule=source_rule)

    messages = [{"role": "user", "content": brief}]
    if body.paper_id:
        paper = read_json(PARSED / f"{body.paper_id}.json")
        if paper:
            excerpt = parsing.chunks_to_text(paper["chunks"], False)[:6000]
            messages.append({"role": "user", "content":
                             "Here is the beginning of one real paper from this corpus. Make the "
                             "prompt fit papers that look like this — its table conventions, its "
                             "units, how it names things:\n\n" + excerpt})

    profile_id = config.get_settings().get("extract_model", "")
    blocked = models.blockers(profile_id, "extraction")
    if blocked:
        raise HTTPException(400, " ".join(blocked))
    params = models.call_params(profile_id)
    try:
        resp = llm.complete(params, messages)
    except Exception as e:
        raise HTTPException(502, f"{type(e).__name__}: {e}") from e
    model = params["model"]
    text = (resp.choices[0].message.content or "").strip()
    text = re.sub(r"^```[a-z]*\n|\n```$", "", text)
    return {"prompt": text, "model": model}


# ---------- the SPA ----------

class RevalidatingStatic(StaticFiles):
    """Static files that the browser must re-check before reusing.

    Without a Cache-Control header a browser is free to guess how long a response stays fresh,
    and it guesses in hours. That made every fix invisible until someone thought to hard-reload:
    the server would be running new code while the tab ran the old app.js, which is a very
    confusing thing to debug from the outside. "no-cache" means revalidate, not "do not store" --
    the ETag above still turns an unchanged file into a 304 with no body.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", RevalidatingStatic(directory=ROOT / "web", html=True), name="web")
