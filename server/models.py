"""Named model configurations, one per endpoint you actually call.

Extraction and judging want different models more often than not -- a strong extractor and a
cheaper auditor, or deliberately different families so the judge is not marking its own work --
and each may live behind its own endpoint and key. So a model here is a small named record:
what to call, where, and with which credential.

The secret never lives in this file. It is written to .env under a variable derived from the
profile's id, and only the variable name is stored here, so a config directory can be copied,
inspected or backed up without carrying a key with it.
"""
import re
import uuid

from .storage import CONFIG, read_json, write_json

FILE = CONFIG / "models.json"


def key_var(profile_id: str) -> str:
    """The .env variable holding this profile's secret."""
    return "MODEL_" + re.sub(r"[^A-Z0-9]+", "_", profile_id.upper()) + "_KEY"


def public(profile: dict, key_is_set) -> dict:
    from . import llm
    return {
        "id": profile["id"],
        "name": profile.get("name") or profile.get("model") or "untitled",
        "model": profile.get("model", ""),
        "api_base": profile.get("api_base", ""),
        "api_version": profile.get("api_version", ""),
        "key_var": key_var(profile["id"]),
        "key_set": key_is_set(key_var(profile["id"])),
        # Answered by litellm's own router, so the interface can say "this model string will not
        # route" while the model is being configured, instead of at the first paid call.
        "provider_problem": llm.provider_problem(profile.get("model", "")),
    }


def listing(key_is_set) -> list[dict]:
    return [public(p, key_is_set) for p in read_json(FILE, [])]


def get(profile_id: str) -> dict | None:
    return next((p for p in read_json(FILE, []) if p["id"] == profile_id), None)


def save_all(profiles: list[dict]) -> list[dict]:
    """Whole-list replace, ids preserved where given and minted where not."""
    stored = []
    for p in profiles:
        stored.append({
            "id": p.get("id") or uuid.uuid4().hex[:8],
            "name": (p.get("name") or "").strip(),
            "model": (p.get("model") or "").strip(),
            "api_base": (p.get("api_base") or "").strip(),
            "api_version": (p.get("api_version") or "").strip(),
        })
    write_json(FILE, stored)
    return stored


def call_params(profile_id: str) -> dict:
    """What to hand litellm for this profile.

    Credentials are passed per call rather than left to provider environment variables: one
    workspace can then hold an Azure deployment for extraction and an OpenAI model for judging
    without the two fighting over which OPENAI_API_KEY is in scope.
    """
    import os
    profile = get(profile_id)
    if not profile:
        return {}
    params = {"model": profile["model"]}
    secret = os.environ.get(key_var(profile_id))
    if secret:
        params["api_key"] = secret
    if profile.get("api_base"):
        params["api_base"] = profile["api_base"]
    if profile.get("api_version"):
        params["api_version"] = profile["api_version"]
    return params


def blockers(profile_id: str, stage_label: str) -> list[str]:
    """What stops this profile from being usable, phrased as the thing to go and do."""
    import os
    if not profile_id:
        return [f"Choose a model for {stage_label} in Settings."]
    profile = get(profile_id)
    if not profile:
        return [f"The model chosen for {stage_label} no longer exists. Pick another in Settings."]
    if not profile.get("model"):
        return [f"The model for {stage_label} has no model string. Add one in Settings."]
    missing = []
    if not os.environ.get(key_var(profile_id)):
        missing.append(f"{profile.get('name') or profile['model']} has no API key. "
                       f"Add it in Settings.")
    from . import llm
    if problem := llm.provider_problem(profile["model"]):
        missing.append(problem)
    return missing
