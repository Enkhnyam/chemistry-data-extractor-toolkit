"""Builds a pydantic response model from the user's own field list, so the extractor
works on whatever schema.json currently says -- ionic liquids today, anything else after
an edit in Settings. Mirrors the pattern in the source project's core/schema.py (a fixed
Experiment model, `source_chunk_ids` added only when source tracking is on) but reads the
field list from data instead of hardcoding it."""
from pydantic import BaseModel, ConfigDict, Field, create_model

TYPE_MAP = {"string": str, "number": float, "integer": int, "boolean": bool}

DEFAULT_SCHEMA = [
    {"name": "catalyst", "type": "string", "description": "Catalyst name exactly as written"},
    {"name": "solvent", "type": "string", "description": "Solvent name exactly as written"},
    {"name": "temperature_c", "type": "number", "description": "Temperature in Celsius"},
    {"name": "reaction_time_min", "type": "number", "description": "Reaction time in minutes"},
    {"name": "catalyst_amount_g", "type": "number", "description": "Catalyst amount in grams"},
    {"name": "substrate_amount_g", "type": "number", "description": "Substrate amount in grams"},
    {"name": "solvent_amount_g", "type": "number", "description": "Solvent amount in grams"},
    {"name": "yield_percent", "type": "number", "description": "Yield %"},
    {"name": "selectivity_percent", "type": "number", "description": "Selectivity %"},
    {"name": "conversion_percent", "type": "number", "description": "Conversion %"},
]


def build_response_model(fields: list[dict], with_source: bool) -> type[BaseModel]:
    kwargs = {}
    for f in fields:
        py_type = TYPE_MAP.get(f.get("type", "string"), str)
        kwargs[f["name"]] = (py_type | None, Field(None, description=f.get("description", "")))
    if with_source:
        kwargs["source_chunk_ids"] = (
            list[str],
            Field(default_factory=list, description="IDs of the text chunks these values came from"),
        )
    record = create_model("Record", __config__=ConfigDict(extra="ignore"), **kwargs)
    return create_model("ExtractionResponse", records=(list[record], Field(default_factory=list)))
