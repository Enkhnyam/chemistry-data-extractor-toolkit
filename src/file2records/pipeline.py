"""The pipeline itself -- add a paper, extract, judge -- with no web server in it.

These loops used to live inside the HTTP handlers, which meant the only way to run the pipeline
was through a browser. The web app, the command line and the Python API now all call these
functions, so there is one implementation of each stage and three ways to reach it.
"""
import os
import time
from collections.abc import Callable
from pathlib import Path

from . import (config, extraction, identifiers, judge, llm, models, parsing, readers,
               storage, timings)
from .storage import paper_id_for, require, write_json

# RWTH's KI:connect service: OpenAI-compatible, unmetered for its open models. Spelled out once
# here so a researcher writes "rwth/gpt-oss-120b" instead of an endpoint and a provider prefix.
# The three things an AI service gives you, read from the shell or a .env file whenever no model
# was chosen in the browser's Settings.
KEY_VAR, ENDPOINT_VAR, MODEL_VAR = "FILE2RECORDS_API_KEY", "FILE2RECORDS_ENDPOINT", "FILE2RECORDS_MODEL"
JUDGE_MODEL_VAR = "FILE2RECORDS_JUDGE_MODEL"     # optional: judge with a different model
NO_MODEL = (f"No model yet. Add one in Settings, or put {ENDPOINT_VAR}, {KEY_VAR} and "
            f"{MODEL_VAR} in a .env file.")


def connect(api_key: str | None = None, endpoint: str | None = None,
            model: str | None = None) -> dict:
    """A model from your service's endpoint, your key and the model's name as any of the
    service's pages spell it. Each defaults to its FILE2RECORDS_* variable."""
    return llm.connect(api_key or os.environ.get(KEY_VAR, ""),
                       endpoint or os.environ.get(ENDPOINT_VAR) or None,
                       model or os.environ.get(MODEL_VAR) or None)


def resolve_model(model, stage: str) -> dict:
    """What to hand litellm. May ask the endpoint which models it has, so it can raise
    RuntimeError with a message for the user (wrong key, unknown model, unreachable address).

    None: the model chosen for this stage in Settings, else the FILE2RECORDS_* variables. A
    string: a model name, looked up on FILE2RECORDS_ENDPOINT if that is set, else a litellm
    model string. A dict: litellm parameters, completed by connect() if it has a key."""
    if model is None:
        profile = config.get_settings().get(f"{stage}_model", "")
        if profile:
            return models.call_params(profile)
        if not os.environ.get(KEY_VAR):
            return {}
        return connect(model=os.environ.get(JUDGE_MODEL_VAR) if stage == "judge" else None)
    params = given(model)
    if params.get("api_key") and "/" not in (params.get("model") or ""):
        params.update(llm.connect(params["api_key"], params.get("api_base"), params.get("model")))
    return params


def given(model) -> dict | None:
    """The model as the caller gave it, before anything is looked up."""
    if model is None or isinstance(model, dict):
        return model and dict(model)
    model = str(model).strip()
    if "/" not in model and os.environ.get(KEY_VAR):         # a name: look it up
        return {k: v for k, v in {"api_key": os.environ[KEY_VAR], "model": model,
                                  "api_base": os.environ.get(ENDPOINT_VAR)}.items() if v}
    return {"model": model}


def ready(stage: str, model=None) -> tuple[dict, list[str]]:
    """Call parameters for `stage`, and what is missing. Asks the endpoint only once nothing
    else is missing, so a wrong key or model name is reported here rather than mid-run."""
    missing = blockers(stage, given(model))
    if missing:
        return {}, missing
    try:
        return resolve_model(model, stage), []
    except RuntimeError as e:
        return {}, [str(e)]


def blockers(stage: str, params: dict | None = None) -> list[str]:
    """What is still missing before this stage can run, in the order a person would fix it.
    Never touches the network: the browser asks this on every page.

    `params` is the model as given on the command line or in Python, before resolve_model; None
    means the one chosen in Settings, or the FILE2RECORDS_* environment variables."""
    label = "extraction" if stage == "extract" else "judging"
    profile = config.get_settings().get(f"{stage}_model", "")
    missing = []
    if params is None:
        if profile:
            missing += models.blockers(profile, label)
        elif not os.environ.get(KEY_VAR):
            missing.append(NO_MODEL)
    elif not params.get("model") and not params.get("api_key"):
        missing.append(f"No model given for {label}.")
    elif params.get("model") and not params.get("api_key") and \
            (problem := llm.provider_problem(params["model"])):
        missing.append(problem)
    if not config.get_schema():
        missing.append("Define the fields a record has: Settings → Schema in the browser, or "
                       "project.schema in Python.")
    if stage == "extract" and not config.get_extract_prompt().strip():
        missing.append("Write the extraction prompt: on the Extract page in the browser, or "
                       "project.prompt in Python.")
    if stage == "judge" and not config.get_judge_prompt().strip():
        missing.append("Write the judge rubric: on the Judge page in the browser, or "
                       "project.rubric in Python.")
    return missing


# ---------- adding papers ----------

def add_file(filename: str, content: bytes, source_tracking: bool | None = None) -> dict:
    """Store one paper file and parse it. Returns what the upload list shows, or an error for
    this file alone -- one unreadable file never stops the rest of a folder."""
    with_source = (config.get_settings()["source_tracking_default"]
                   if source_tracking is None else source_tracking)
    pid = paper_id_for(filename, content)
    suffix = Path(filename).suffix.lower() or ".txt"
    stored = storage.PDFS / f"{pid}{suffix}"
    stored.write_bytes(content)
    started = time.monotonic()
    try:
        chunks, meta, fmt = readers.parse(stored, pid)
    except Exception as e:
        # Don't leave the file behind: it has no parsed record, so nothing in the UI can see it
        # or clean it up, and a folder of retried failures would silently fill the disk.
        stored.unlink(missing_ok=True)
        message = str(e) if isinstance(e, (readers.UnsupportedFile, RuntimeError)) else \
            f"{type(e).__name__}: {e}"
        return {"id": pid, "filename": filename, "error": message}
    write_json(storage.PARSED / f"{pid}.json", {
        "id": pid, "filename": filename, "source_tracking": with_source, "format": fmt,
        "meta": meta, "chunks": chunks,
    })
    seconds = time.monotonic() - started
    # Measured per byte, because that is what the browser can see before it uploads.
    if fmt == "pdf":
        timings.record("parse", seconds, len(content), unit="bytes")
    return {"id": pid, "filename": filename, "format": fmt, "doi": meta.get("doi", ""),
            "n_chunks": len(chunks), "source_tracking": with_source, "seconds": round(seconds, 1)}


def collect_files(paths) -> list[Path]:
    """Every supported file under the given files and folders, in a stable order."""
    found = []
    for p in map(Path, paths):
        if p.is_dir():
            found += sorted(f for f in p.rglob("*")
                            if f.is_file() and f.suffix.lower() in readers.SUFFIXES
                            and not f.name.startswith("."))
        elif p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(f"No such file or folder: {p}")
    return found


# ---------- the two model stages ----------

def extract(paper_ids: list[str], params: dict,
            on_paper: Callable[[dict], None] | None = None) -> list[dict]:
    """Extract records from each paper, one model call per paper, writing extracted/<id>.json.
    Failures are reported per paper; the rest of the batch carries on."""
    prompt = config.get_extract_prompt()
    schema_fields = config.get_schema()
    few_shot = config.get_few_shot()
    results = []
    for pid in paper_ids:
        result = _extract_one(pid, params, prompt, schema_fields, few_shot)
        results.append(result)
        if on_paper:
            on_paper(result)
    return results


def _extract_one(pid, params, prompt, schema_fields, few_shot) -> dict:
    try:
        paper = require(storage.PARSED / f"{pid}.json", "paper")
    except FileNotFoundError as e:
        return {"id": pid, "error": str(e)}
    with_source = paper.get("source_tracking", True)
    text = parsing.chunks_to_text(paper["chunks"], with_source)
    started = time.monotonic()
    try:
        records, usage, synonyms = extraction.run_extraction(
            params, prompt, schema_fields, few_shot, text, with_source,
            spell_out=list(identifiers.chosen()))
    except Exception as e:
        return {"id": pid, "error": f"{type(e).__name__}: {e}"}
    seconds = time.monotonic() - started
    # The model cited short labels (c17); what gets stored is the chunk's real id, so
    # everything downstream -- the review pane, the export -- keeps working unchanged.
    if with_source:
        for record in records:
            record["source_chunk_ids"] = parsing.resolve_labels(
                record.get("source_chunk_ids"), paper["chunks"])
    timings.record("extract", seconds, len(paper["chunks"]), unit="chunks")
    write_json(storage.EXTRACTED / f"{pid}.json",
               {"id": pid, "records": records, "usage": usage, "model": params.get("model"),
                "synonyms": synonyms})
    identifiers.for_records(records, synonyms)     # looked up now, so review and export don't wait
    return {"id": pid, "n_records": len(records), "seconds": round(seconds, 1), "usage": usage}


def judge_papers(paper_ids: list[str], params: dict,
                 on_paper: Callable[[dict], None] | None = None) -> list[dict]:
    """Audit each paper's records against its text, writing judged/<id>.json."""
    rubric = config.get_judge_prompt()
    results = []
    for pid in paper_ids:
        result = _judge_one(pid, params, rubric)
        results.append(result)
        if on_paper:
            on_paper(result)
    return results


def _judge_one(pid, params, rubric) -> dict:
    try:
        paper = require(storage.PARSED / f"{pid}.json", "paper")
        extracted = require(storage.EXTRACTED / f"{pid}.json", "extraction")
    except FileNotFoundError as e:
        return {"id": pid, "error": str(e)}
    with_source = paper.get("source_tracking", True)
    text = parsing.chunks_to_text(paper["chunks"], with_source)
    started = time.monotonic()
    try:
        verdicts, usage = judge.run_judge(params, rubric, text, extracted["records"])
    except Exception as e:
        return {"id": pid, "error": f"{type(e).__name__}: {e}"}
    verdicts = judge.fit_fixes(verdicts, config.get_schema())
    seconds = time.monotonic() - started
    timings.record("judge", seconds, len(extracted["records"]), unit="records")
    write_json(storage.JUDGED / f"{pid}.json",
               {"id": pid, "verdicts": verdicts, "usage": usage, "model": params.get("model"),
                # what the judge actually saw, so a later edit can be spotted as post-dating it
                "judged_records": extracted["records"]})
    return {"id": pid, "n_verdicts": len(verdicts), "seconds": round(seconds, 1), "usage": usage}


def paper_ids() -> list[str]:
    return [p.stem for p in sorted(storage.PARSED.glob("*.json"))]


def done(stage: str, pid: str) -> bool:
    return (storage.EXTRACTED if stage == "extract" else storage.JUDGED).joinpath(
        f"{pid}.json").exists()
