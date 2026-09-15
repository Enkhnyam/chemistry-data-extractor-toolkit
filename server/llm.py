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


def complete(params: dict, messages: list[dict], **kwargs):
    """One completion. `params` carries model, api_key, api_base and api_version for the chosen
    profile, passed explicitly rather than read from the environment -- so extraction and
    judging can sit behind different providers in the same workspace."""
    if not params.get("model"):
        raise RuntimeError("No model configured. Choose one in Settings.")
    try:
        return litellm.completion(messages=messages, num_retries=5,
                                  timeout=REQUEST_TIMEOUT, **params, **kwargs)
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
