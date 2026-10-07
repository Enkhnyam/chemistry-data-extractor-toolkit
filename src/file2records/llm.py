"""The one place that calls the model.

Extraction and judging had identical copies of the same retry-and-translate-the-error block,
which is how two copies drift. It also answers "what did that cost", because a tool that
spends money per paper should not make you read a provider dashboard to find out.
"""
import re

import litellm

# A single call's ceiling. Generous, because a reasoning model on a long paper genuinely takes
# minutes -- but it is a ceiling, and the retries below are few, because the failure mode being
# avoided is a run that sits silent for the better part of an hour. 600s x 6 attempts was that.
REQUEST_TIMEOUT = 600      # seconds
MAX_ATTEMPTS = 2           # one retry, not five: a timeout repeated five times is just a wait


def usage_of(resp) -> dict:
    """Tokens and dollars for one call. Cost is best-effort: litellm knows the price of most
    models but not of a private deployment, and an unknown price is reported as 0.0 rather
    than guessed."""
    usage = getattr(resp, "usage", None)
    try:
        cost = float(litellm.completion_cost(completion_response=resp) or 0.0)
    except Exception:
        cost = float((getattr(resp, "_hidden_params", {}) or {}).get("response_cost") or 0.0)
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "cost_usd": round(cost, 6),
    }


def complete(params: dict, messages: list[dict], **kwargs):
    """One completion. `params` carries model, api_key, api_base and api_version for the chosen
    profile, passed explicitly rather than read from the environment -- so extraction and
    judging can sit behind different providers in the same workspace."""
    if not params.get("model"):
        raise RuntimeError("No model configured. Choose one in Settings.")
    try:
        return litellm.completion(messages=messages, num_retries=MAX_ATTEMPTS - 1,
                                  timeout=REQUEST_TIMEOUT, **params, **kwargs)
    except litellm.AuthenticationError as e:
        raise RuntimeError(f"Authentication failed: {e}. Check the key for this provider in "
                           f"Settings.") from e
    except litellm.RateLimitError as e:
        raise RuntimeError(f"Rate limited: {e}. Wait, or run fewer papers at once.") from e
    except litellm.ContextWindowExceededError as e:
        raise RuntimeError(f"The paper plus the prompt exceeds this model's context window: {e}. "
                           f"Use a longer-context model, or remove a few-shot example.") from e
    except litellm.Timeout as e:
        raise RuntimeError(
            f"No reply within {REQUEST_TIMEOUT // 60} minutes, twice. That is usually the model "
            f"rather than the connection: a reasoning model writes a long hidden answer before "
            f"the first visible character. Try a faster model for extraction, or split the "
            f"paper. ({e})") from e
    except litellm.APIError as e:
        raise RuntimeError(f"The provider returned an error: {e}") from e


def provider_problem(model: str) -> str:
    """Empty if litellm can route this model string; otherwise why it cannot, and what to write.

    litellm decides which provider to call from a prefix on the model string, and a bare name it
    does not recognise fails with "LLM Provider NOT provided" -- at the moment of the first real
    call, after the papers are parsed and the prompt is written. Asking litellm's own router the
    question up front turns that into a line in the checklist, and it is litellm answering, so
    this can never disagree with what the call would do.
    """
    model = (model or "").strip()
    if not model:
        return ""
    try:
        litellm.get_llm_provider(model=model)
        return ""
    except Exception:
        return (f'litellm cannot tell which provider "{model}" belongs to. Model strings carry '
                f'their provider as a prefix: write "openai/{model}" for any OpenAI-compatible '
                f'endpoint (most self-hosted servers, vLLM, Together, a proxy), '
                f'"ollama/{model}" for a local Ollama, or "azure/{model}" for an Azure '
                f'deployment.')


# ---------- from a key to a callable model ----------
#
# A researcher has a key, and for a service like RWTH's KI:connect an endpoint. They should not
# have to know that litellm wants "openai/" in front of a self-hosted model, nor guess that the
# server calls its Mistral "mistralai-mistral-small-4-119b". So: ask the endpoint what it serves,
# drop what cannot extract (embeddings, audio, images), and pick or match a model.

# Keys whose first characters say which service issued them. Anything else needs the endpoint.
# (litellm prefix, model-list URL)
KEY_PREFIXES = {
    "sk-ant-": ("anthropic/", "https://api.anthropic.com/v1"),
    "AIza": ("gemini/", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "gsk_": ("groq/", "https://api.groq.com/openai/v1"),
    "xai-": ("xai/", "https://api.x.ai/v1"),
    "sk-": ("openai/", "https://api.openai.com/v1"),     # last: the others also start "sk-"
}
NOT_CHAT = re.compile(r"embed|\be5-|rerank|whisper|tts|transcri|moderation|dall-e|image|"
                      r"audio|realtime|search|vision-only", re.I)
# The default when nobody names a model: the first of these the service has. gpt-oss-120b is
# free on KI:connect and was the most dependable judge on the PET corpus.
# ponytail: a short hand-kept list; extend it when a service picks badly.
PREFERRED = ["gpt-oss-120b", "claude-sonnet", "gemini-2.5-flash", "gpt-4.1-mini", "gpt-4o-mini",
             "llama-3.3-70b", "grok"]


def list_models(endpoint: str, api_key: str) -> list[str]:
    """Model ids the endpoint serves that can extract, as the endpoint spells them."""
    import httpx
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    if api_key.startswith("sk-ant-"):
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    try:
        r = httpx.get(endpoint.rstrip("/") + "/models", headers=headers, timeout=30)
    except httpx.HTTPError as e:
        raise RuntimeError(f"Could not reach {endpoint}: {e}") from e
    if r.status_code in (401, 403):
        raise RuntimeError(f"{endpoint} rejected the API key (HTTP {r.status_code}). Check that "
                           f"the key is complete and belongs to this service.")
    if r.status_code >= 400:
        raise RuntimeError(f"{endpoint}/models answered HTTP {r.status_code}. Is this the API "
                           f"address (usually ending in /v1), not the website?")
    data = r.json()
    entries = data.get("data", data) if isinstance(data, dict) else data
    ids = [str(m["id"]).removeprefix("models/") for m in entries
           if isinstance(m, dict) and m.get("id")]
    return [i for i in ids if not NOT_CHAT.search(i)]


def pick(ids: list[str], wanted: str | None = None) -> str:
    """`wanted` matched exactly, else as a unique case-insensitive fragment; else the default."""
    if wanted:
        if wanted in ids:
            return wanted
        hits = [i for i in ids if wanted.lower() in i.lower()]
        if len(hits) == 1:
            return hits[0]
        raise RuntimeError(f'"{wanted}" {"matches several" if hits else "is not one"} of the '
                           f"models offered: {', '.join(hits or ids)}.")
    for preferred in PREFERRED:
        hits = sorted((i for i in ids if preferred in i.lower()), reverse=True)  # newest first
        if hits:
            return hits[0]
    if not ids:
        raise RuntimeError("The service lists no models that can extract text.")
    return ids[0]


def connect(api_key: str, endpoint: str | None = None, model: str | None = None) -> dict:
    """Call parameters for litellm from a key, plus the endpoint for services that need one
    (RWTH KI:connect, self-hosted servers). `model` is optional and may be a fragment
    of the name ("mistral")."""
    if not api_key:
        raise RuntimeError("No API key.")
    if endpoint:
        ids = list_models(endpoint, api_key)
        return {"model": "openai/" + pick(ids, model), "api_base": endpoint.rstrip("/") + "/",
                "api_key": api_key}
    for prefix, (litellm_prefix, url) in KEY_PREFIXES.items():
        if api_key.startswith(prefix):
            return {"model": litellm_prefix + pick(list_models(url, api_key), model),
                    "api_key": api_key}
    raise RuntimeError("Can't tell which service this key belongs to. Give its endpoint too, "
                       "e.g. https://chat.kiconnect.nrw/api/v1 for RWTH KI:connect.")
