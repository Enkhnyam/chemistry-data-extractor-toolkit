# API key and endpoint

file2records sends each paper to a language model through your AI service's API. It needs
two values from the service:

Endpoint
:   The address of the service's API. It usually ends in `/v1`.

API key
:   A secret that lets file2records use your account.

!!! example "Using RWTH KI:connect?"
    [Example: RWTH KI:connect](../examples/rwth-kiconnect.md) shows where to find both, with
    screenshots.

## Get them from your AI service

Universities and research centers often run their own AI service. On its website, look for
a page called **API**, **API keys**, or **Developer**. It shows the endpoint and lets you
create a key. If you can't find one, ask your IT center whether its language model service
offers API access.

| Service | Endpoint |
|---|---|
| RWTH KI:connect | `https://chat.kiconnect.nrw/api/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Your organization's service | shown on its API key page |

!!! warning "Copy the key right away"
    Most services show a new key only once. Paste it into a text file before you close the
    page. If you lose it, delete it and create a new one.

## Save them for file2records

=== "Python"

    Make a file called `.env` in the folder you work in:

    ```bash title=".env"
    FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1
    FILE2RECORDS_API_KEY=paste-your-key-here
    ```

    file2records reads this file whenever you create a project. The model name goes into the
    same file in the [next step](models.md).

    !!! warning "Keep the key private"
        Don't share the `.env` file or put it in a Git repository. If you use Git, add
        `.env` to your `.gitignore` file.

=== "Browser"

    You enter the endpoint and key when you add a model, in the [next step](models.md).
    The browser saves the key in a `.env` file inside the project folder and never shows
    it again.

Continue with [Extraction and judge models](models.md).
