"""The one place that calls the model.

Extraction and judging had identical copies of the same retry-and-translate-the-error block,
which is how two copies drift. It also answers "what did that cost", because a tool that
spends money per paper should not make you read a provider dashboard to find out.
"""
import litellm

REQUEST_TIMEOUT = 600      # seconds; slower than this is stuck, not working


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


def missing_credentials(model: str) -> str | None:
    """The env var this model needs and does not have, or None.

    litellm knows which variable each provider reads, so ask it rather than keeping our own
    table. Without this the first thing a new user sees is the provider's own words --
    "InternalServerError ... pass an `api_key`, `workload_identity`, `admin_api_key`" -- which
    names three things that are not the one thing to do.
    """
    import os
    # Empty is not set. Copying .env.example leaves `OPENAI_API_KEY=`, which becomes an empty
    # string that litellm's check counts as present -- and litellm re-reads the .env itself on
    # import, so stripping the blanks at startup does not hold. They are removed here, for the
    # length of the check, and put back: this function answers a question, it does not tidy up.
    blanks = {k: v for k, v in os.environ.items() if v == ""}
    for k in blanks:
        os.environ.pop(k, None)
    try:
        check = litellm.validate_environment(model=model)
    except Exception:
        return None
    finally:
        os.environ.update(blanks)
    missing = [k for k in (check.get("missing_keys") or []) if k]
    if check.get("keys_in_environment") or not missing:
        return None
    return (f"{model} needs {' and '.join(missing)}, which is not set. "
            f"Add it under Keys in Settings.")


def complete(model: str, messages: list[dict], **kwargs):
    """One completion, with provider errors translated into something a person can act on."""
    gap = missing_credentials(model)
    if gap:
        raise RuntimeError(gap)
    try:
        return litellm.completion(model=model, messages=messages, num_retries=5,
                                  timeout=REQUEST_TIMEOUT, **kwargs)
    except litellm.AuthenticationError as e:
        raise RuntimeError(f"Authentication failed: {e}. Check the key for this provider in "
                           f"Settings.") from e
    except litellm.RateLimitError as e:
        raise RuntimeError(f"Rate limited: {e}. Wait, or run fewer papers at once.") from e
    except litellm.ContextWindowExceededError as e:
        raise RuntimeError(f"The paper plus the prompt exceeds this model's context window: {e}. "
                           f"Use a longer-context model, or remove a few-shot example.") from e
    except litellm.APIError as e:
        raise RuntimeError(f"The provider returned an error: {e}") from e
