# Connect your model

You need an API key. For a service that runs its own server, such as RWTH KI:connect, you
also need its address, called the endpoint. You don't need to know any model names:
file2records asks the service which models it has and picks a good one.

## RWTH KI:connect

1. Log in at [chat.kiconnect.nrw](https://chat.kiconnect.nrw) with your RWTH account.
2. Click your name in the bottom-left corner, then **API Key Management**, then
   **Create Key**.
3. Put the key and the endpoint in a file called `.env`, in the folder you work in:

    ```bash title=".env"
    FILE2RECORDS_API_KEY=6ac63d...your-whole-key...
    FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1
    ```

That's all. Check it:

```console
$ file2records check my-review
extract: ready
judge: ready
```

On KI:connect, file2records uses `gpt-oss-120b`, which is free for RWTH members.

## Other services

Keys from OpenAI, Anthropic, Google Gemini, Groq and xAI are recognized from how they start,
so you only need the key:

```bash title=".env"
FILE2RECORDS_API_KEY=sk-ant-...
```

For any other service with an OpenAI-compatible API, such as a server your group runs, add
its endpoint as `FILE2RECORDS_ENDPOINT`, the same way as for KI:connect.

## In the browser

Go to **Settings**, then **Models**, and click **Add a model**, or **Add RWTH KI:connect** to
have the endpoint filled in. Paste the key and click **Test connection**. Leave **Model**
empty and one is picked for you.

## In a script

```python
import file2records as fr

model = fr.connect("6ac63d...your-whole-key...", "https://chat.kiconnect.nrw/api/v1")
project.extract(model=model)
```

With `FILE2RECORDS_API_KEY` set, `project.extract()` with no `model` works too.

## Choose a different model

Give part of its name. The match is case-insensitive.

=== "Command line"

    ```bash
    file2records extract my-review --model mistral
    ```

=== "Python"

    ```python
    fr.connect(key, endpoint, model="mistral")
    ```

=== "Browser"

    Type `mistral` into the **Model** field, or click **List models** to see them all.

If the part you give matches more than one model, file2records lists them so you can be more
specific.

## Troubleshooting

"rejected the API key"
:   The key is incomplete or belongs to a different service. Copy it again, including
    everything after the colon.

"Can't tell which service this key belongs to"
:   Add `FILE2RECORDS_ENDPOINT` with the service's address.

"answered HTTP 404"
:   The endpoint is the website address instead of the API address. For KI:connect it's
    `https://chat.kiconnect.nrw/api/v1`.

Rate limit errors
:   KI:connect accepts a few requests at a time, and file2records sends one at a time. Some
    models have an hourly limit that a large batch exceeds. For large batches, use
    `gpt-oss-120b`.
