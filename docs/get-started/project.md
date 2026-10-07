# 3. Create a project

A project is a folder that holds everything for one dataset: the papers, your fields and
prompts, the records, and your model settings. Here it's called `my-project`.

=== "Browser"

    1. In the terminal, run:

        ```bash
        file2records serve my-project
        ```

        Your browser opens on the new, empty project. The **Getting started** box lists what's
        still missing:

        ![A new project with the Getting started box](../img/tutorial/01-new-project.png)

        Leave the terminal open while you work. To stop file2records, press ++ctrl+c++ in
        the terminal.

    2. Click **Settings** at the top of the page. Under **Models**, click **Add a model**.
    3. Type a name, such as `My AI service`.
    4. Paste your endpoint into **Endpoint** and your key into **API key**.
    5. Click **List models**. file2records asks your service which models it has:

        ![The models the service offers](../img/tutorial/02-list-models.png)

    6. Click your model. In these screenshots, it's `gpt-oss-120b` on RWTH KI:connect.
    7. At the bottom of the page, click **Save changes**.
    8. Click **Test connection**. After a few seconds you see **It works**:

        ![A successful connection test](../img/tutorial/03-test-connection.png)

=== "Python"

    1. In the folder where you'll run your script, make a file called `.env` with the three
       values from step 2:

        ```bash title=".env"
        FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1
        FILE2RECORDS_API_KEY=paste-your-key-here
        FILE2RECORDS_MODEL=gpt-oss-120b
        ```

    2. Create the project and ask what's still missing:

        ```python
        import file2records as fr

        project = fr.Project("my-project")
        print(project.check())
        ```

        ```console
        ['Define the fields a record has: Settings → Schema in the browser, or project.schema in Python.', 'Write the extraction prompt: on the Extract page in the browser, or project.prompt in Python.']
        ```

        The model is set up: it isn't in the list. The next steps add the fields and the
        prompt. If the key or the endpoint is wrong, the list says so instead.

Both ways create the same folder. You can start in Python and open the project in the
browser later with `file2records serve my-project`, or the other way round.

Continue with [Add papers](papers.md).
