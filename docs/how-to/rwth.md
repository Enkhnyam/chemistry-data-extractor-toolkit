# Use RWTH KI:connect

KI:connect is RWTH's language model service. It uses the same API as OpenAI, and its open
models are free for RWTH members. file2records uses `gpt-oss-120b` by default.

## Get a key

1. Log in at [chat.kiconnect.nrw](https://chat.kiconnect.nrw) with your RWTH account.
2. Click your name in the bottom-left corner, then **API Key Management**, then
   **Create Key**.

## Use the key

=== "Browser"

    Go to **Settings**, then **Models**, and click **Add RWTH KI:connect**. Paste the key and
    click **Test connection**. The key is saved in the `.env` file in the project folder, and
    the browser doesn't show it again.

=== "Command line"

    ```bash
    export RWTH_API_KEY=...
    file2records extract my-review --model rwth/gpt-oss-120b
    ```

    You can put `RWTH_API_KEY=...` in a `.env` file instead of exporting it.

=== "Python"

    ```python
    project.extract(model=fr.rwth())
    project.extract(model=fr.rwth("mistral-small-4-119b-2603"))
    ```

    `fr.rwth()` reads `RWTH_API_KEY` from the environment. To pass the key yourself, use
    `fr.rwth(api_key=...)`.

## Check the setup

```console
$ file2records check my-review --model rwth/gpt-oss-120b
extract: ready
judge: ready
```

## Troubleshooting

No RWTH key
:   `RWTH_API_KEY` isn't set in your shell, and there's no `.env` file with it in the folder
    you're running from.

You want a different model
:   In the browser, **List models** shows every model the service offers. On the command line
    and in Python, use any of them as `rwth/<name>`.

Rate limit errors
:   The service accepts a few requests at a time, and file2records sends one at a time.
    Some models, such as `gpt-5.5`, also have an hourly limit that a large batch exceeds. For
    large batches, use the open models.
