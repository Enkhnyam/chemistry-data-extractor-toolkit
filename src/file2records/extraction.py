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


def run_extraction(params: dict, prompt: str, schema_fields: list[dict], few_shot: list[dict],
                    paper_text: str, with_source: bool) -> tuple[list[dict], dict]:
    response_model = build_response_model(schema_fields, with_source)

    system = prompt
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
    return [r for r in records if not _copied(r, few_shot)], llm.usage_of(resp)


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
