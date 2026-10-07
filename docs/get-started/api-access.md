# 2. Set up API access

!!! example "Using RWTH KI:connect?"
    [Example: RWTH KI:connect](../examples/rwth-kiconnect.md) shows this step with
    screenshots of KI:connect.

file2records sends each paper to a language model through your AI service's API. Get these
three values from the service and write them into a text file:

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

!!! warning "Copy the key right away"
    Most services show a new key only once. If you lose it, delete it and create a new one.

## Choose a model

Most services have a page that lists their models. Look for three things:

- **Message limits.** You send one message per paper, and one more if you check the results.
  A model without a message limit is best.
- **Where the data is processed.** For papers that aren't public yet, choose a model that
  processes data in your country or at your institution.
- **Maximum output.** A paper with a very large table needs a model that can write a long
  answer.

You can write the model's name as any page of the service writes it, or part of it.
KI:connect, for example, calls one model "Mistral Small 4 119b" in its chat menu,
`mistral-small-4-119b-2603` on its overview page, and `mistralai-mistral-small-4-119b` in its
API. Any of these works, and so does `mistral`. In the next step, file2records also shows you
the list of models your service offers.

Continue with [Create a project](project.md).
