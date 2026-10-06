"""Reads/writes the four things that make this tool generic: the schema, the extraction
prompt, the judge rubric, and few-shot examples. All under workspace/config/, all editable
from the Settings page -- change these four and the same pipeline runs on a different
domain, no code changes."""
from . import exemplar
from . import storage
from .storage import read_json, write_json
from .dynschema import PLACEHOLDER_SCHEMA



def settings_file():
    return storage.CONFIG / "settings.json"


def schema_file():
    return storage.CONFIG / "schema.json"


def extract_prompt_file():
    return storage.CONFIG / "extract_prompt.txt"


def judge_prompt_file():
    return storage.CONFIG / "judge_prompt.txt"


def few_shot_file():
    return storage.CONFIG / "few_shot.json"

DEFAULT_SETTINGS = {
    # Which named model profile each stage calls; see server/models.py. Empty until chosen.
    "extract_model": "",
    "judge_model": "",
    "source_tracking_default": True,  # a real default: provenance on unless turned off
}

def get_settings() -> dict:
    return {**DEFAULT_SETTINGS, **read_json(settings_file(), {})}


def save_settings(patch: dict) -> dict:
    cfg = get_settings()
    cfg.update(patch)
    write_json(settings_file(), cfg)
    return cfg


def get_schema() -> list[dict]:
    """Empty until someone defines one. A shipped default meant every new install began with
    ten PET fields nobody chose, and an extraction that looked like it had worked."""
    return read_json(schema_file(), {"fields": []})["fields"]


def save_schema(fields: list[dict]) -> None:
    write_json(schema_file(), {"fields": fields})


def _get_text(path) -> str:
    """A prompt nobody has written yet is empty, not somebody else's.

    This used to fall back to a built-in PET prompt, which meant a first run quietly extracted
    ionic-liquid chemistry from whatever you uploaded and looked like it had worked. The
    example text is still shown -- as placeholder text in the box -- but it is never the value.
    """
    return path.read_text(encoding="utf-8") if path.exists() else ""


def get_extract_prompt() -> str:
    return _get_text(extract_prompt_file())


def save_extract_prompt(text: str) -> None:
    extract_prompt_file().write_text(text, encoding="utf-8")


def get_judge_prompt() -> str:
    return _get_text(judge_prompt_file())


def placeholders() -> dict:
    """Everything shown as grey example text in an empty field. None of it is ever a value."""
    return {"extract": exemplar.EXTRACT_PROMPT, "judge": exemplar.JUDGE_PROMPT,
            "model": "gpt-4o-mini", "schema": PLACEHOLDER_SCHEMA}


def save_judge_prompt(text: str) -> None:
    judge_prompt_file().write_text(text, encoding="utf-8")


def get_few_shot() -> list[dict]:
    return read_json(few_shot_file(), [])


def save_few_shot(examples: list[dict]) -> None:
    write_json(few_shot_file(), examples)
