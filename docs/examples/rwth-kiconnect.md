# Example: RWTH KI:connect

This page shows how to get API access from RWTH Aachen's KI:connect and connect it to
file2records. Other organizations' services work the same way; see
[Set up API access](../setup/api-key.md) for the general steps.

## 1. Get the endpoint and an API key

Log in at [chat.kiconnect.nrw](https://chat.kiconnect.nrw) with your RWTH account. Click your
name in the bottom-left corner, and click **API Keys Management**.

![KI:connect's API Keys Management window](../img/service/api-keys.png)

1. Next to **Endpoint**, click the copy icon, and paste the endpoint into a text file. It's
   `https://chat.kiconnect.nrw/api/v1`.
2. In **Key Name**, type `file2records`, and click **Generate Key**.
3. Next to your new key, click the copy icon, and paste the key into the same text file.

!!! warning "Copy the key now"
    KI:connect shows the key only once. If you lose it, delete it and generate a new one.

## 2. Choose a model

Open the model menu at the top of the chat page:

![KI:connect's model menu](../img/service/model-menu.png){ width="360" }

Click **Learn more** at the top of the menu to see the details of every model:

![KI:connect's model overview](../img/service/model-overview.png)

Look at three things:

Limits
:   You send one message per paper, and one more if you also check the results. A model with
    **Unlimited messages** is best.

Data processing
:   A German flag means the data stays in Germany. Choose one of these if your papers
    aren't public yet.

Max. output
:   How much the model can write in one answer, in the **API** column. Each record takes some
    of it. A paper with a very large table needs a model with a large maximum output.

Use **OpenAI GPT OSS 120b**. It has unlimited messages, stays in Germany, and gave the best
results of KI:connect's models in a benchmark on chemistry papers.

## 3. Enter them in file2records

=== "Browser"

    1. Open **Settings**, and under **Models** click **Add a model**.
    2. Paste the endpoint into **Endpoint** and the key into **API key**.
    3. Click **List models**, then click `gpt-oss-120b`.
    4. Click **Save changes**, then **Test connection**. You see **It works**.

    ![A successful connection test](../img/tutorial/03-test-connection.png)

=== "Command line and Python"

    Put these three lines in a file called `.env` in the folder you work in:

    ```bash title=".env"
    FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1
    FILE2RECORDS_API_KEY=paste-your-key-here
    FILE2RECORDS_MODEL=gpt-oss-120b
    ```

KI:connect writes each model's name differently on each page. For example, the chat menu
calls one model **Mistral Small 4 119b**, the overview calls it `mistral-small-4-119b-2603`,
and the API calls it `mistralai-mistral-small-4-119b`. You can use any of these spellings,
or part of one, such as `mistral`.
