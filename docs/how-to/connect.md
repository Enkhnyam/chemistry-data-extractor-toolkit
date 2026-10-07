# Set up API access

!!! example "Using RWTH KI:connect?"
    See [Example: RWTH KI:connect](../examples/rwth-kiconnect.md) for the same steps with
    screenshots of KI:connect.

file2records sends each paper to a language model through your AI service's API. For that it
needs three values from the service:

Endpoint
:   The address of the service's API. It usually ends in `/v1`.

API key
:   A secret that lets file2records use your account.

Model
:   Which of the service's models to use.

## Get the endpoint and a key

Universities and research centers often run their own AI service. Look on its website for a
page called **API**, **API keys**, or **Developer**. That page shows the endpoint and lets you
create a key. If you can't find one, ask your IT center whether its language model service
offers API access. The service must offer an OpenAI-compatible API; most do.

| Service | Endpoint |
|---|---|
| RWTH KI:connect | `https://chat.kiconnect.nrw/api/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Your organization's service | shown on its API key page |

Most services show a new key only once. Copy it right away and keep it somewhere safe.

## Choose a model

Most services have a page that lists their models. Look for three things:

- **Message limits.** You send one message per paper, and one more if you check the results.
  A model without a message limit is best.
- **Where the data is processed.** For papers that aren't public yet, choose a model that
  processes data in your country or at your institution.
- **Maximum output.** A paper with a very large table needs a model that can write a long
  answer.

## Enter them in file2records

=== "Browser"

    1. Open **Settings**, and under **Models** click **Add a model**.
    2. Fill in **Endpoint** and **API key**.
    3. Click **List models**, and click the model you chose.
    4. Click **Save changes**, then **Test connection**. You see **It works**.

=== "Command line and Python"

    Put the three values in a file called `.env` in the folder you work in:

    ```bash title=".env"
    FILE2RECORDS_ENDPOINT=https://your-service.example/api/v1
    FILE2RECORDS_API_KEY=paste-your-key-here
    FILE2RECORDS_MODEL=the-model-name
    ```

    In Python you can also pass them directly:

    ```python
    model = fr.connect(api_key, "https://your-service.example/api/v1", "the-model-name")
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
