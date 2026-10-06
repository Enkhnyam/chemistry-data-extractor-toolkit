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

    messages = [{"role": "system", "content": prompt}]
    for i, example in enumerate(few_shot or []):
        if "text" not in example or "records" not in example:
            raise RuntimeError(f"Worked example {i + 1} is missing its text or records; fix it "
                               f"in Settings.")
        messages.append({"role": "user", "content": example["text"]})
        messages.append({"role": "assistant", "content": json.dumps({"records": example["records"]})})
    messages.append({"role": "user", "content": paper_text})

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
    return [r.model_dump() for r in parsed.records], llm.usage_of(resp)
