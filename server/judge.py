"""LLM-as-judge, one call per paper: rubric + full text + all its records -> a verdict and
field-level fixes per record. Ported near-verbatim from the source project's core/judge.py --
that code was already schema-agnostic (records are plain dicts, fields are whatever the
rubric names), so nothing here is PET- or ionic-liquid-specific."""
import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from . import llm


class FieldFix(BaseModel):
    field: str = Field(description="Name of the field to correct")
    value: str | float | None = Field(None, description="Corrected value, or null to empty it")
    evidence: str = Field("", description="Where in the paper the corrected value comes from")


class RecordVerdict(BaseModel):
    record_index: int
    critique: str = Field(description="2-5 sentences citing the specific evidence")
    bad_fields: list[str] = Field(default_factory=list)
    verdict: Literal["correct", "incorrect"]
    fixes: list[FieldFix] = Field(default_factory=list)
    drop_record: bool = Field(False, description="True if the record should be removed, not fixed")


class BatchVerdict(BaseModel):
    verdicts: list[RecordVerdict]


OUTPUT_SPEC = (
    'Return ONLY a JSON object with one entry per record, matching record_index:\n'
    '{"verdicts": [{"record_index": <int>, "critique": "...", "bad_fields": [...], '
    '"verdict": "correct" | "incorrect", '
    '"fixes": [{"field": "...", "value": <number|string|null>, "evidence": "..."}], '
    '"drop_record": true | false}, ...]}')


def strip_json_comments(text: str) -> str:
    """Drop // line comments outside string literals, and the comma they orphan."""
    lines = []
    for line in (text or "").splitlines():
        in_string = escaped = False
        cut = None
        for i, char in enumerate(line):
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = not in_string
            elif char == "/" and not in_string and line[i + 1:i + 2] == "/":
                cut = i
                break
        lines.append(line[:cut].rstrip() if cut is not None else line)
    return re.sub(r",(\s*[}\]])", r"\1", "\n".join(lines))


def build_messages(rubric: str, paper_text: str, records: list[dict]) -> list[dict]:
    numbered = "\n\n".join(f"RECORD {i}:\n{json.dumps(r, indent=2)}" for i, r in enumerate(records))
    return [{"role": "system", "content": rubric + "\n\n" + OUTPUT_SPEC},
            {"role": "user", "content": f"PAPER TEXT:\n{paper_text}\n\n"
                                       f"Judge each of the {len(records)} extracted records below.\n\n{numbered}"}]


def run_judge(params: dict, rubric: str, paper_text: str, records: list[dict]) -> tuple[list[dict], dict]:
    if not records:
        return [], {}
    resp = llm.complete(params, build_messages(rubric, paper_text, records),
                        response_format=BatchVerdict)
    content = resp.choices[0].message.content
    outermost = content[content.find("{"): content.rfind("}") + 1]
    for candidate in (content, outermost, strip_json_comments(content), strip_json_comments(outermost)):
        try:
            batch = BatchVerdict.model_validate_json(candidate)
            break
        except (ValidationError, ValueError):
            continue
    else:
        raise RuntimeError("The judge's reply was not valid JSON, even after repair. Try again, "
                           "or use a model that honours response_format.")

    by_index = {v.record_index: v for v in batch.verdicts}
    verdicts = [
        {"record_index": i, "parsed_ok": i in by_index, **(by_index[i].model_dump() if i in by_index else {})}
        for i in range(len(records))
    ]
    return verdicts, llm.usage_of(resp)
