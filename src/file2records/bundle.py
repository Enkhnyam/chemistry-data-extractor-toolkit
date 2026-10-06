"""The export bundle: a dataset together with what produced it.

A CSV of records on its own is not reproducible -- it cannot say which model wrote it, under
which prompt, against which schema, or which rows a human then corrected. The bundle is the data
beside the config and a manifest that pins both.

What it leaves out by default matters as much. Papers obtained through publishers' text-and-data
mining agreements may be read and mined, not redistributed -- and a bundle is made to be shared.
So the paper text and the source files go in only when asked for (`include_text`,
`include_files`), which is the right call for open-access papers and the caller's to make.
Without them every record still names its paper's DOI and the ids of the chunks it came from,
which is enough for anyone with access to the paper to check it.

No key ever enters the bundle; model settings are copied without their key variables.
"""
import csv
import io
import json
import subprocess
import time
import zipfile
from pathlib import Path

from . import __version__, config, models, report, storage
from .storage import read_json


def csv_bytes(columns, rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def git_commit() -> str | None:
    """Which checkout produced this, when run from one. None for an installed package, whose
    version is recorded instead."""
    try:
        return subprocess.check_output(["git", "-C", str(Path(__file__).resolve().parent),
                                        "rev-parse", "HEAD"],
                                       text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
    except Exception:
        return None


def build(paper_ids: list[str] | None = None, *, include_text: bool = False,
          include_files: bool = False, profiles: list[dict] | None = None) -> bytes:
    """The zip as bytes. `paper_ids` limits it to those papers (None: all of them)."""
    record_columns, record_rows = report.flat_records(paper_ids)
    paper_columns, paper_rows = report.papers_table(paper_ids)
    summary = report.build()
    settings = config.get_settings()
    if profiles is None:
        profiles = [{k: v for k, v in p.items()} for p in models.listing(lambda _: False)]
    chosen = {r["paper_id"] for r in paper_rows}

    manifest = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "file2records",
        "version": __version__,
        "git_commit": git_commit(),
        "papers": len(paper_rows),
        "records": len(record_rows),
        "includes_paper_text": include_text,
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
        bundle.writestr("README.md", _readme(manifest))
        bundle.writestr("data/records.csv", csv_bytes(record_columns, record_rows))
        bundle.writestr("data/records.json", json.dumps(record_rows, indent=1, ensure_ascii=False))
        bundle.writestr("data/papers.csv", csv_bytes(paper_columns, paper_rows))
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
        for stage, directory in (("extracted", storage.EXTRACTED), ("judged", storage.JUDGED)):
            for path in sorted(directory.glob("*.json")):
                if path.stem in chosen:
                    bundle.write(path, f"{stage}/{path.name}")
        for path in sorted(storage.PARSED.glob("*.json")):
            if path.stem not in chosen:
                continue
            paper = read_json(path, {})
            if not include_text:
                paper["chunks"] = [{"id": c["id"]} for c in paper.get("chunks", [])]
            bundle.writestr(f"parsed/{path.name}", json.dumps(paper, indent=1, ensure_ascii=False))
        if include_files:
            for pid in sorted(chosen):
                if (source := storage.source_file(pid)) is not None:
                    bundle.write(source, f"papers/{source.name}")
    return buffer.getvalue()


def _readme(manifest: dict) -> str:
    m = manifest["models"]
    text_note = (
        "`chunks[].text` holds the paper text, because this bundle was exported with it. Check "
        "the papers' licences before sharing it."
        if manifest["includes_paper_text"] else
        "Paper text is not included -- papers obtained under text-and-data-mining terms may be "
        "mined, not redistributed. Each chunk keeps its `id`, and each record its paper's DOI, "
        "so anyone with access to the paper can check a value against its source.")
    return f"""# file2records bundle

{manifest['records']} records from {manifest['papers']} paper(s), exported
{manifest['exported_at']} by file2records {manifest['version']}.

## What is here

- `data/records.csv`, `data/records.json` — one row per record, with the paper's DOI, the
  judge's verdict and any reviewer flag or note. `extract_model` and `judge_model` say what
  produced each row.
- `data/papers.csv` — one row per paper: DOI, chunks in, records out, model, tokens, cost.
- `data/report.json` — completeness by field, what the judge changed, totals.
- `config/` — the schema, both prompts, the worked examples and the model settings that
  produced this. API keys are not included.
- `parsed/`, `extracted/`, `judged/` — the working files, so any row can be traced back to the
  chunk it came from. `source_chunk_ids` on a record refers to `chunks[].id` in `parsed/`.
- `papers/` — the source files, if you exported with them.

{text_note}

## Reading it

Extraction model: `{m['extract'] or 'not set'}` · judge model: `{m['judge'] or 'not set'}`.
Papers may differ from these if the corpus was built across more than one model; see
`models.per_paper` in `manifest.json`.

`model_records` in `extracted/*.json` is what the model originally said, kept beside the
corrected records the moment anything was edited. A corrected dataset that cannot be diffed
against the model's own output is not evidence of anything.
"""
