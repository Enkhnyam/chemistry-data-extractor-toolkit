"""FastAPI app: parse PDFs, extract records, judge them. Three verbs, three stages, all
reading/writing plain JSON under workspace/. See README for the full endpoint list --
this file is short enough to read top to bottom instead.
"""
import asyncio
import csv
import io
import json
import re
import threading
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv, set_key
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
load_dotenv(ENV_FILE)

from . import config, extraction, judge, parsing, report, timings  # noqa: E402  (after load_dotenv)
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
    return config.get_settings()


@app.put("/api/settings")
def put_settings(patch: dict):
    return config.save_settings(patch)


class SchemaField(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
                      description="letters, digits, underscore; must not start with a digit")
    type: Literal["string", "number", "integer", "boolean"] = "string"
    description: str = ""


class SchemaBody(BaseModel):
    fields: list[SchemaField]


@app.get("/api/schema")
def get_schema():
    return {"fields": config.get_schema()}


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
    return {"extract": config.get_extract_prompt(), "judge": config.get_judge_prompt()}


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
    source: str | None = Field(None, description="where it came from, for the Settings list")


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


@app.post("/api/test-model")
def test_model():
    """One tiny completion against the configured model. Answers "is my model string plus my
    keys actually going to work" in two seconds and for a fraction of a cent -- instead of
    that question being answered twenty minutes into a batch run, by a failure."""
    import litellm
    from . import llm
    model = config.get_settings()["model"]
    gap = llm.missing_credentials(model)
    if gap:
        return {"ok": False, "model": model, "error": gap}
    started = time.monotonic()
    try:
        resp = litellm.completion(model=model, messages=[{"role": "user", "content": "Reply with OK."}],
                                  max_tokens=5, timeout=30)
    except Exception as e:
        return {"ok": False, "model": model, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "model": model,
            "reply": (resp.choices[0].message.content or "").strip()[:40],
            "seconds": round(time.monotonic() - started, 1)}


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
    prompt = config.get_extract_prompt()
    schema_fields = config.get_schema()
    few_shot = config.get_few_shot()

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
            records, usage = extraction.run_extraction(settings["model"], prompt, schema_fields,
                                                       few_shot, text, with_source)
        except Exception as e:
            results.append({"id": pid, "error": f"{type(e).__name__}: {e}"})
            continue
        seconds = time.monotonic() - started
        timings.record("extract", seconds, len(paper["chunks"]), unit="chunks")
        write_json(EXTRACTED / f"{pid}.json",
                   {"id": pid, "records": records, "usage": usage, "model": settings["model"]})
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
    version: int | None = Field(None, description="the version this edit was based on")


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
    if body.version is not None and body.version != version_of(path):
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
    rubric = config.get_judge_prompt()

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
            verdicts, usage = judge.run_judge(settings["model"], rubric, text, extracted["records"])
        except Exception as e:
            results.append({"id": pid, "error": f"{type(e).__name__}: {e}"})
            continue
        seconds = time.monotonic() - started
        timings.record("judge", seconds, len(extracted["records"]), unit="records")
        write_json(JUDGED / f"{pid}.json",
                   {"id": pid, "verdicts": verdicts, "usage": usage, "model": settings["model"],
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

    import litellm
    model = config.get_settings()["model"]
    try:
        resp = litellm.completion(model=model, messages=messages, timeout=180)
    except Exception as e:
        raise HTTPException(502, f"{type(e).__name__}: {e}") from e
    text = (resp.choices[0].message.content or "").strip()
    text = re.sub(r"^```[a-z]*\n|\n```$", "", text)
    return {"prompt": text, "model": model}


# ---------- the SPA ----------

app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
