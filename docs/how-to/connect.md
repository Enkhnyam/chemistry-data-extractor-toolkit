# Connect your model

file2records needs three values from your AI service:

Endpoint
:   The address of the service's API. It usually ends in `/v1`.

API key
:   A secret that lets file2records use your account.

Model
:   Which of the service's models to use.

[Steps 2 and 3 of the tutorial](../tutorial.md#2-get-your-endpoint-and-api-key) show
where to find them, with RWTH KI:connect as the example.

## Where to find them at your organization

Universities and research centers often run their own AI service. Look on its website for a
page called **API**, **API keys**, or **Developer**. That page shows the endpoint and lets you
create a key. If you can't find one, ask your IT center whether its language model service
offers API access. The service must offer an OpenAI-compatible API; most do.

| Service | Endpoint |
|---|---|
| RWTH KI:connect | `https://chat.kiconnect.nrw/api/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Your organization's service | shown on its API key page |

## Enter them

=== "Browser"

    Go to **Settings**, then **Models**, and click **Add a model**. Fill in **Endpoint** and
    **API key**, click **List models**, and click the model you want. Click **Save changes**,
    then **Test connection**.

=== "Command line and Python"

    Put the three values in a file called `.env` in the folder you work in:

    ```bash title=".env"
    FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1
    FILE2RECORDS_API_KEY=paste-your-key-here
    FILE2RECORDS_MODEL=gpt-oss-120b
    ```

    In Python you can also pass them directly:

    ```python
    model = fr.connect(api_key, "https://chat.kiconnect.nrw/api/v1", "gpt-oss-120b")
    project.extract(model=model)
    ```

Then check them:

```console
$ file2records check my-project
extract: ready
judge: ready
```

## How to write the model name

A service often spells one model differently on different pages. KI:connect, for example,
calls the same model "Mistral Small 4 119b" in its chat menu, `mistral-small-4-119b-2603` on
its overview page, and `mistralai-mistral-small-4-119b` in its API. Any of these works, and so
does part of the name, such as `mistral`. file2records looks up the name on your service and
uses its API spelling.

If the name matches more than one model, or none, file2records lists the models your service
offers, so you can pick one.

## Choose a model

Look at the service's model overview for three things:

- **Message limits.** You send one message per paper, and one more if you check the results.
- **Where the data is processed.** For papers that aren't public yet, choose a model that
  processes data in your country or at your institution.
- **Maximum output.** A paper with a very large table needs a model that can write a long
  answer.

On RWTH KI:connect, `gpt-oss-120b` gave the best results in a benchmark on chemistry
papers. It has no message limit and processes data in Germany.

## Troubleshooting

"rejected the API key"
:   The key is incomplete or belongs to a different service. Copy it again, including
    everything after a colon.

"answered HTTP 404"
:   The endpoint is the website address instead of the API address.

"is not one of the models this service offers"
:   Check the spelling, or use one of the names in the list that follows the message.

"Could not reach"
:   Check your internet connection. Some services only work from your institution's network
    or VPN.

Rate limit errors
:   The service accepts only a few requests at a time or per hour. file2records sends one at
    a time. Choose a model without a message limit for large batches.
