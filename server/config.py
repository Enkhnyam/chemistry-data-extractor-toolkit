"""Reads/writes the four things that make this tool generic: the schema, the extraction
prompt, the judge rubric, and few-shot examples. All under workspace/config/, all editable
from the Settings page -- change these four and the same pipeline runs on a different
domain, no code changes."""
from .storage import CONFIG, read_json, write_json
from .dynschema import DEFAULT_SCHEMA

SETTINGS_FILE = CONFIG / "settings.json"
SCHEMA_FILE = CONFIG / "schema.json"
EXTRACT_PROMPT_FILE = CONFIG / "extract_prompt.txt"
JUDGE_PROMPT_FILE = CONFIG / "judge_prompt.txt"
FEW_SHOT_FILE = CONFIG / "few_shot.json"

DEFAULT_SETTINGS = {
    "model": "gpt-4o-mini",
    "source_tracking_default": True,
}

DEFAULT_EXTRACT_PROMPT = """You extract experimental records from a scientific paper's text and tables.
Extract only what is stated; leave anything unreported as null. The output structure is
enforced by the response schema below -- focus on getting the values (and their sources,
if the schema asks for them) right.

- Extract EVERY qualifying row: N rows of raw data -> N records. Don't merge rows or stop early.
- Skip literature/cited results, values that appear only in a figure, and anything not
  actually measured in this study.
- A condition stated once (methods text, a table footnote) applies to every row it covers --
  propagate it rather than leaving it null.
- Use null, never a placeholder, when a value is genuinely not reported.

This is a starting prompt -- rewrite it for your own schema and paper set in Settings.

## Source chunks
If the text below is tagged "ID: <uuid>" per chunk, list in source_chunk_ids every chunk id
that supplied a value for that record.
"""

DEFAULT_JUDGE_PROMPT = """You are auditing a database of records extracted from scientific papers.
You will be given the full text of ONE paper (possibly split into chunks tagged "ID: <uuid>")
and several records extracted from it. Judge EACH record independently: would a careful
expert accept it as an accurate rendering of something actually reported in THIS paper?

Judge only the data fields the schema defines. Ignore source_chunk_ids -- provenance is not
part of correctness.

A field is bad if it contradicts the paper, invents a value the paper does not give, or is
null although the paper reports (or lets you derive) a value for it. Do not penalize
formatting, ordering, or other harmless surface differences.

For each record report, in this order:
- critique: 2-5 sentences citing the specific evidence, before deciding the verdict.
- bad_fields: names of the fields you found wrong or unsupported. Empty if none.
- verdict: "incorrect" if the record has any bad field, else "correct".
- fixes: for every bad field the paper supports a specific value for, give that value.
  Numbers as numbers, in the units the field name implies. Use null to empty a field the
  paper does not support at all. Leave fixes empty for a record you judged correct.
- drop_record: true only when the record should be deleted rather than repaired -- it does
  not describe anything this paper reports at all (a literature-comparison row, a duplicate,
  an invented value).

This is a starting rubric -- rewrite it to match your own schema in Settings.
"""


def get_settings() -> dict:
    return {**DEFAULT_SETTINGS, **read_json(SETTINGS_FILE, {})}


def save_settings(patch: dict) -> dict:
    cfg = get_settings()
    cfg.update(patch)
    write_json(SETTINGS_FILE, cfg)
    return cfg


def get_schema() -> list[dict]:
    return read_json(SCHEMA_FILE, {"fields": DEFAULT_SCHEMA})["fields"]


def save_schema(fields: list[dict]) -> None:
    write_json(SCHEMA_FILE, {"fields": fields})


def _get_text(path, default: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default


def get_extract_prompt() -> str:
    return _get_text(EXTRACT_PROMPT_FILE, DEFAULT_EXTRACT_PROMPT)


def save_extract_prompt(text: str) -> None:
    EXTRACT_PROMPT_FILE.write_text(text, encoding="utf-8")


def get_judge_prompt() -> str:
    return _get_text(JUDGE_PROMPT_FILE, DEFAULT_JUDGE_PROMPT)


def save_judge_prompt(text: str) -> None:
    JUDGE_PROMPT_FILE.write_text(text, encoding="utf-8")


def get_few_shot() -> list[dict]:
    return read_json(FEW_SHOT_FILE, [])


def save_few_shot(examples: list[dict]) -> None:
    write_json(FEW_SHOT_FILE, examples)
