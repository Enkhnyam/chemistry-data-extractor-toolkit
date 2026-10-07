"""The pipeline itself -- add a paper, extract, judge -- with no web server in it.

These loops used to live inside the HTTP handlers, which meant the only way to run the pipeline
was through a browser. The web app, the command line and the Python API now all call these
functions, so there is one implementation of each stage and three ways to reach it.
"""
import os
import time
from collections.abc import Callable
from pathlib import Path

from . import config, extraction, judge, llm, models, parsing, readers, storage, timings
from .storage import paper_id_for, require, write_json

# RWTH's KI:connect service: OpenAI-compatible, unmetered for its open models. Spelled out once
# here so a researcher writes "rwth/gpt-oss-120b" instead of an endpoint and a provider prefix.
RWTH_API_BASE = "https://chat.kiconnect.nrw/api/v1/"
RWTH_DEFAULT = "gpt-oss-120b"
RWTH_KEY_VAR = "RWTH_API_KEY"


def rwth(name: str = RWTH_DEFAULT, api_key: str | None = None) -> dict:
    """Call parameters for a model on RWTH's KI:connect. The key comes from RWTH_API_KEY unless
    given; create one at https://chat.kiconnect.nrw (API Key Management)."""
    name = name.removeprefix("rwth/").removeprefix("openai/")
    return {"model": f"openai/{name}", "api_base": RWTH_API_BASE,
            "api_key": api_key or os.environ.get(RWTH_KEY_VAR, "")}


def resolve_model(model, stage: str) -> dict:
    """What to hand litellm. None means the model chosen for this stage in the project's
    settings; a string is a litellm model string ("rwth/<name>" is the RWTH shorthand); a dict
    is taken as it is."""
    if model is None:
        return models.call_params(config.get_settings().get(f"{stage}_model", ""))
    if isinstance(model, dict):
        return dict(model)
    model = str(model).strip()
    if model.startswith("rwth/"):
        return rwth(model)
    return {"model": model}


def blockers(stage: str, params: dict | None = None) -> list[str]:
    """What is still missing before this stage can run, in the order a person would fix it.

    With `params` the model was given directly (command line or Python) rather than chosen in
    Settings, so the model check is about that string instead of a saved profile."""
    label = "extraction" if stage == "extract" else "judging"
    if params is None:
        missing = list(models.blockers(config.get_settings().get(f"{stage}_model", ""), label))
    else:
        missing = []
        if not params.get("model"):
            missing.append(f"No model given for {label}.")
        elif problem := llm.provider_problem(params["model"]):
            missing.append(problem)
        if params.get("api_base") == RWTH_API_BASE and not params.get("api_key"):
            missing.append(f"No RWTH key. Set {RWTH_KEY_VAR}, or create one at "
                           f"https://chat.kiconnect.nrw under API Key Management.")
    if not config.get_schema():
        missing.append("Define the fields a record has: Settings → Schema in the web app, or "
                       "config/schema.json in the project folder.")
    if stage == "extract" and not config.get_extract_prompt().strip():
        missing.append("Write an extraction prompt (in the web app, or config/extract_prompt.txt). "
                       "Until you do, nothing tells the model what to pull out.")
    if stage == "judge" and not config.get_judge_prompt().strip():
        missing.append("Write a judge rubric (in the web app, or config/judge_prompt.txt). "
                       "Until you do, nothing tells the model what counts as a good record.")
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
        records, usage = extraction.run_extraction(params, prompt, schema_fields,
                                                   few_shot, text, with_source)
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
               {"id": pid, "records": records, "usage": usage, "model": params.get("model")})
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
