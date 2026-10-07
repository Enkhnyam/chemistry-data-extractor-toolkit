# Use RWTH KI:connect

RWTH's [KI:connect](https://chat.kiconnect.nrw) speaks the OpenAI API, and its open models
cost nothing. `gpt-oss-120b` is the default here.

## Get a key

1. Log in at [chat.kiconnect.nrw](https://chat.kiconnect.nrw) with RWTH single sign-on.
2. Click your name (bottom left) → **API Key Management** → **Create Key**.

## Use it

=== "Browser"

    Settings → Models → **Add RWTH KI:connect**, paste the key, press **Test connection**.
    The key is saved in `.env` inside the project folder and never shown again.

=== "Command line"

    ```bash
    export RWTH_API_KEY=...          # or put RWTH_API_KEY=... in a .env file
    file2records extract my-review --model rwth/gpt-oss-120b
    ```

=== "Python"

    ```python
    project.extract(model=fr.rwth())                         # gpt-oss-120b
    project.extract(model=fr.rwth("mistral-small-4-119b-2603"))
    ```

    `fr.rwth()` reads `RWTH_API_KEY` from the environment; pass `api_key=` to give it directly.

## Check it

```console
$ file2records check my-review --model rwth/gpt-oss-120b
extract: ready
judge: ready
```

## If it goes wrong

- **"No RWTH key"** — `RWTH_API_KEY` isn't set in this shell or in a `.env` in the folder you
  run from.
- **Which models are there?** In the browser, **List models** asks the endpoint. Any name it
  lists works as `rwth/<name>`.
- **Rate limits** — the endpoint allows a few requests at a time. file2records sends one at a
  time, so you shouldn't hit them. Some models (such as `gpt-5.5`) have hourly caps that a large
  batch will exceed; use the open models for batches.
