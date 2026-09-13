"""Reads/writes the four things that make this tool generic: the schema, the extraction
prompt, the judge rubric, and few-shot examples. All under workspace/config/, all editable
from the Settings page -- change these four and the same pipeline runs on a different
domain, no code changes."""
from . import exemplar
from .storage import CONFIG, read_json, write_json
from .dynschema import PLACEHOLDER_SCHEMA

SETTINGS_FILE = CONFIG / "settings.json"
SCHEMA_FILE = CONFIG / "schema.json"
EXTRACT_PROMPT_FILE = CONFIG / "extract_prompt.txt"
JUDGE_PROMPT_FILE = CONFIG / "judge_prompt.txt"
FEW_SHOT_FILE = CONFIG / "few_shot.json"

DEFAULT_SETTINGS = {
    "model": "",                      # no model until one is chosen; see placeholders()
    "source_tracking_default": True,  # a real default: provenance on unless turned off
}

def get_settings() -> dict:
    return {**DEFAULT_SETTINGS, **read_json(SETTINGS_FILE, {})}


def save_settings(patch: dict) -> dict:
    cfg = get_settings()
    cfg.update(patch)
    write_json(SETTINGS_FILE, cfg)
    return cfg


def get_schema() -> list[dict]:
    """Empty until someone defines one. A shipped default meant every new install began with
    ten PET fields nobody chose, and an extraction that looked like it had worked."""
    return read_json(SCHEMA_FILE, {"fields": []})["fields"]


def save_schema(fields: list[dict]) -> None:
    write_json(SCHEMA_FILE, {"fields": fields})


def _get_text(path) -> str:
    """A prompt nobody has written yet is empty, not somebody else's.

    This used to fall back to a built-in PET prompt, which meant a first run quietly extracted
    ionic-liquid chemistry from whatever you uploaded and looked like it had worked. The
    example text is still shown -- as placeholder text in the box -- but it is never the value.
    """
    return path.read_text(encoding="utf-8") if path.exists() else ""


def get_extract_prompt() -> str:
    return _get_text(EXTRACT_PROMPT_FILE)


def save_extract_prompt(text: str) -> None:
    EXTRACT_PROMPT_FILE.write_text(text, encoding="utf-8")


def get_judge_prompt() -> str:
    return _get_text(JUDGE_PROMPT_FILE)


def placeholders() -> dict:
    """Everything shown as grey example text in an empty field. None of it is ever a value."""
    return {"extract": exemplar.EXTRACT_PROMPT, "judge": exemplar.JUDGE_PROMPT,
            "model": "gpt-4o-mini", "schema": PLACEHOLDER_SCHEMA}


def save_judge_prompt(text: str) -> None:
    JUDGE_PROMPT_FILE.write_text(text, encoding="utf-8")


def get_few_shot() -> list[dict]:
    return read_json(FEW_SHOT_FILE, [])


def save_few_shot(examples: list[dict]) -> None:
    write_json(FEW_SHOT_FILE, examples)
