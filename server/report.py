"""Whole-corpus summary: what was extracted, how complete it is, and where the judge and the
reviewer disagreed with it.

The panels are the ones a paper about an extracted database ends up needing -- records per
paper, completeness by field, verdict split, corrections by field, the distribution of any one
field -- but computed from whatever schema is loaded rather than from a fixed list of columns,
so the same report describes an ionic-liquid corpus and a metal-salt one without edits.
"""
from collections import Counter, defaultdict

from . import config
from .storage import EXTRACTED, JUDGED, PARSED, read_json

MAX_TOP = 25        # distinct values kept per categorical field
MAX_NUMBERS = 5000  # numeric values shipped per field, enough for any histogram


def _is_blank(v) -> bool:
    return v is None or v == ""


def build() -> dict:
    schema = config.get_schema()
    declared = [f["name"] for f in schema]
    types = {f["name"]: f.get("type", "string") for f in schema}

    papers, per_paper_records = [], []
    spend = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "priced": 0, "calls": 0}
    filled, total = Counter(), Counter()
    values, numbers = defaultdict(Counter), defaultdict(list)
    corrections, bad_fields = Counter(), Counter()
    verdicts, flags = Counter(), Counter()
    seen_fields, edited_records, dropped = list(declared), 0, 0

    for path in sorted(PARSED.glob("*.json")):
        pid = path.stem
        paper = read_json(path, {})
        extraction = read_json(EXTRACTED / f"{pid}.json")
        judgment = read_json(JUDGED / f"{pid}.json")
        records = (extraction or {}).get("records", [])
        model_records = (extraction or {}).get("model_records") or records
        notes = (extraction or {}).get("notes", {})

        for source in (extraction, judgment):
            usage = (source or {}).get("usage") or {}
            if usage:
                spend["calls"] += 1
                spend["prompt_tokens"] += usage.get("prompt_tokens", 0)
                spend["completion_tokens"] += usage.get("completion_tokens", 0)
                spend["cost_usd"] = round(spend["cost_usd"] + usage.get("cost_usd", 0.0), 6)
                spend["priced"] += bool(usage.get("cost_usd"))

        by_index = {v["record_index"]: v for v in (judgment or {}).get("verdicts", [])}
        n_bad = sum(1 for v in by_index.values() if v.get("verdict") == "incorrect")

        paper_cost = round(sum(((src or {}).get("usage") or {}).get("cost_usd", 0.0)
                               for src in (extraction, judgment)), 6)
        paper_tokens = sum(((src or {}).get("usage") or {}).get("prompt_tokens", 0) +
                           ((src or {}).get("usage") or {}).get("completion_tokens", 0)
                           for src in (extraction, judgment))
        papers.append({
            "id": pid,
            "filename": paper.get("filename", pid),
            "chunks": len(paper.get("chunks", [])),
            "records": len(records),
            "extracted": extraction is not None,
            "judged": judgment is not None,
            "incorrect": n_bad,
            "reviewed": sum(1 for n in notes.values() if n.get("flag") or n.get("note")),
            "cost_usd": paper_cost,
            "tokens": paper_tokens,
        })
        if extraction:
            per_paper_records.append(len(records))

        for i, record in enumerate(records):
            for field, value in record.items():
                if field == "source_chunk_ids":
                    continue
                if field not in seen_fields:
                    seen_fields.append(field)
                total[field] += 1
                if _is_blank(value):
                    continue
                filled[field] += 1
                if types.get(field, "string") in ("number", "integer") or isinstance(value, (int, float)):
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        numbers[field].append(float(value))
                else:
                    values[field][str(value)] += 1

            original = model_records[i] if i < len(model_records) else None
            if original is not None and any(
                    str(record.get(k, "")) != str(original.get(k, ""))
                    for k in set(record) | set(original) if k != "source_chunk_ids"):
                edited_records += 1

            verdict = by_index.get(i)
            if verdict:
                verdicts[verdict.get("verdict", "unparsed")] += 1
                dropped += bool(verdict.get("drop_record"))
                for field in verdict.get("bad_fields") or []:
                    bad_fields[field] += 1
                for fix in verdict.get("fixes") or []:
                    corrections[fix.get("field", "?")] += 1

        for note in notes.values():
            if note.get("flag"):
                flags[note["flag"]] += 1

    fields = [{
        "name": name,
        "type": types.get(name, "string"),
        "declared": name in declared,
        "filled": filled[name],
        "total": total[name],
        "completeness": round(100 * filled[name] / total[name], 1) if total[name] else 0.0,
        "corrections": corrections[name],
        "bad": bad_fields[name],
        "top": values[name].most_common(MAX_TOP),
        "numbers": numbers[name][:MAX_NUMBERS],
    } for name in seen_fields]

    return {
        "papers": papers,
        "fields": fields,
        "totals": {
            "papers_parsed": len(papers),
            # Extracted means a call was made, not that it found something. A paper that
            # legitimately yields nothing was still processed and still cost money; counting it
            # as unextracted hides both.
            "papers_extracted": sum(1 for p in papers if p["extracted"]),
            "papers_without_records": sum(1 for p in papers if p["extracted"] and not p["records"]),
            "papers_judged": sum(1 for p in papers if p["judged"]),
            "records": sum(per_paper_records),
            "records_per_paper": per_paper_records,
            "records_edited": edited_records,
            "records_dropped_by_judge": dropped,
            "verdicts": dict(verdicts),
            "flags": dict(flags),
            "spend": spend,
        },
    }


def flat_records() -> tuple[list[str], list[dict]]:
    """Every record across every paper, one row each, for CSV/JSON export."""
    columns, rows = ["paper_id", "paper", "record_index"], []
    for path in sorted(EXTRACTED.glob("*.json")):
        pid = path.stem
        extraction = read_json(path, {})
        paper = read_json(PARSED / f"{pid}.json", {})
        judgment = read_json(JUDGED / f"{pid}.json")
        by_index = {v["record_index"]: v for v in (judgment or {}).get("verdicts", [])}
        notes = extraction.get("notes", {})
        # Provenance belongs in the exported file, not only in the app: a CSV that cannot say
        # which model wrote a row is not evidence of anything.
        extract_model = extraction.get("model") or ""
        judge_model = (judgment or {}).get("model") or ""
        for i, record in enumerate(extraction.get("records", [])):
            verdict = by_index.get(i, {})
            note = notes.get(str(i), {})
            row = {"paper_id": pid, "paper": paper.get("filename", pid), "record_index": i,
                   **{k: v for k, v in record.items() if k != "source_chunk_ids"},
                   "source_chunk_ids": " ".join(record.get("source_chunk_ids") or []),
                   "judge_verdict": verdict.get("verdict", ""),
                   "judge_bad_fields": " ".join(verdict.get("bad_fields") or []),
                   "reviewer_flag": note.get("flag") or "",
                   "reviewer_note": note.get("note") or "",
                   "extract_model": extract_model,
                   "judge_model": judge_model}
            for key in row:
                if key not in columns:
                    columns.append(key)
            rows.append(row)
    return columns, rows


def papers_table() -> tuple[list[str], list[dict]]:
    """One row per paper: what went in, what came out, which model, what it cost."""
    columns = ["paper_id", "filename", "chunks", "source_tracking", "records", "judged",
               "extract_model", "judge_model", "prompt_tokens", "completion_tokens", "cost_usd",
               "edited_at"]
    rows = []
    for path in sorted(PARSED.glob("*.json")):
        pid = path.stem
        paper = read_json(path, {})
        extraction = read_json(EXTRACTED / f"{pid}.json") or {}
        judgment = read_json(JUDGED / f"{pid}.json") or {}
        usage = [(extraction.get("usage") or {}), (judgment.get("usage") or {})]
        rows.append({
            "paper_id": pid,
            "filename": paper.get("filename", pid),
            "chunks": len(paper.get("chunks", [])),
            "source_tracking": paper.get("source_tracking", True),
            "records": len(extraction.get("records", [])) if extraction else "",
            "judged": bool(judgment),
            "extract_model": extraction.get("model") or "",
            "judge_model": judgment.get("model") or "",
            "prompt_tokens": sum(u.get("prompt_tokens", 0) for u in usage),
            "completion_tokens": sum(u.get("completion_tokens", 0) for u in usage),
            "cost_usd": round(sum(u.get("cost_usd", 0.0) for u in usage), 6),
            "edited_at": extraction.get("edited_at") or "",
        })
    return columns, rows
