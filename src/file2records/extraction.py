"""One structured-output call per paper: prompt + optional worked examples + paper text ->
records matching whatever schema.json currently defines. Same call shape as the source
project's core/extraction.py (litellm, pydantic response_format, fenced-JSON fallback) minus
the research harness around it (curated corpora, licensing, ablation sweeps) -- none of that is
part of what makes extraction general-purpose.
"""
import json
import re

from pydantic import ValidationError

from . import llm
from .dynschema import build_response_model

# For a field with identifiers, the model also lists the other names the value goes by, only to
# look it up: "EG" stays "EG" in the dataset, as the prompt asked, and is looked up as "ethylene
# glycol", "ethane-1,2-diol" and so on until one of them is in the ontology.
SYNONYMS = "{}_synonyms"
SYNONYMS_HELP = ("Only for looking the {field} up in reference databases, never used as the "
                 "{field} itself. List every name the {field} is known by, as many as you know, "
                 "most common first: its name with every abbreviation, acronym, code and "
                 "shorthand written out; its systematic (IUPAC) name; its common and trade "
                 "names; and other spellings of these, such as with or without brackets, "
                 "hyphens, spaces or oxidation states. Empty if the {field} is empty or the "
                 "paper never says what it stands for.")


def run_extraction(params: dict, prompt: str, schema_fields: list[dict], few_shot: list[dict],
                    paper_text: str, with_source: bool,
                    spell_out: list[str] = ()) -> tuple[list[dict], dict, dict]:
    """Records, token usage, and {field: {value: [synonyms]}} for the fields in `spell_out`."""
    asked = schema_fields + [{"name": SYNONYMS.format(f), "type": "list",
                              "description": SYNONYMS_HELP.format(field=f)} for f in spell_out]
    response_model = build_response_model(asked, with_source)

    system = prompt
    if spell_out:
        system += ("\n\nThe fields ending in _synonyms are only used to look names up in a "
                   "database. Fill every other field exactly as described above.")
    if few_shot:
        system += ("\n\nThe worked examples that follow only show the format and conventions. "
                   "Never copy their records into your answer: extract only from the paper you "
                   "are given last.")
    messages = [{"role": "system", "content": system}]
    for i, example in enumerate(few_shot or []):
        if "text" not in example or "records" not in example:
            raise RuntimeError(f"Worked example {i + 1} is missing its text or records; fix it "
                               f"in Settings.")
        messages.append({"role": "user", "content": "WORKED EXAMPLE:\n" + example["text"]})
        messages.append({"role": "assistant", "content": json.dumps({"records": example["records"]})})
    messages.append({"role": "user", "content": "PAPER TO EXTRACT:\n" + paper_text})

    resp = llm.complete(params, messages, response_format=response_model)
    content = resp.choices[0].message.content
    try:
        parsed = response_model.model_validate_json(content)
    except ValidationError:
        # Some models wrap the JSON in a ```json fence despite response_format.
        stripped = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content or "", flags=re.IGNORECASE)
        try:
            parsed = response_model.model_validate_json(stripped)
        except ValidationError as e:
            raise RuntimeError(f"The model's reply did not match the schema: {str(e)[:200]}") from e
    records = [r.model_dump() for r in parsed.records]
    synonyms = _synonyms(records, spell_out)          # takes the _synonyms fields out
    return [r for r in records if not _copied(r, few_shot)], llm.usage_of(resp), synonyms


def _synonyms(records: list[dict], fields) -> dict:
    """{field: {value as written: [its other names]}}, removing the helper fields from the
    records. A value in several records gets the names from all of them, in the order first
    given; the value itself and repeats are left out."""
    found = {}
    for record in records:
        for field in fields:
            names, value = record.pop(SYNONYMS.format(field), None), record.get(field)
            if not (isinstance(value, str) and value.strip()):
                continue
            value = value.strip()
            known = found.setdefault(field, {}).setdefault(value, [])
            known += [n.strip() for n in names or []
                      if n and n.strip() and n.strip() != value and n.strip() not in known]
    return {field: {v: names for v, names in values.items() if names}
            for field, values in found.items() if any(values.values())}


def _copied(record: dict, few_shot: list[dict] | None) -> bool:
    """True when a record repeats a worked example's record value for value. Models sometimes
    copy the example into the real paper's answer; a real experiment matching a made-up
    example in every field is not a risk worth keeping such copies for."""
    values = {k: v for k, v in record.items() if k != "source_chunk_ids" and v not in (None, "")}
    for example in few_shot or []:
        for shown in example.get("records", []):
            if values and values == {k: v for k, v in shown.items() if v not in (None, "")}:
                return True
    return False
