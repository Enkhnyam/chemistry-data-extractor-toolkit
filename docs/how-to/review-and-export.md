# Review and export

## Review the records

```bash
file2records serve my-review
```

Open **Judge** and choose a paper. The paper is on the left and its records are on the right.

- Click a record to highlight the passages it cites.
- Click a field to find its value in the text. Click again to find the next match.
- Click **Edit** to change a value, or **apply** to accept the judge's suggestion.
- Mark a record **looks right** or **looks wrong**, and add a note if you like.

Your corrections are saved next to the model's original output, so you can always compare
the two.

![The review screen](../img/review.png)

## Export the dataset

=== "Browser"

    On the **Report** page, click **Records CSV**, **Records JSON** or **Full bundle**. To
    export only some papers, type a pattern into the boxes below the buttons.

=== "Command line"

    ```bash
    file2records export my-review dataset.csv
    file2records export my-review dataset.zip --only "glycoly[sz]is"
    ```

=== "Python"

    ```python
    project.export("dataset.csv")
    rows = project.records()          # the same rows as a list of dicts
    ```

Each row has the paper's DOI and title, the fields you defined, the chunks the values came
from, the judge's verdict, reasoning and suggestions, your mark and note, and the models
that produced it.

The full bundle is a `.zip` file. Besides the records, it contains the schema, both prompts,
the worked examples, the model settings without keys, the cost per paper, and the version
of file2records that produced it.

## Share a dataset

The bundle leaves out the text of the papers unless you ask for it. Many publishers let
institutions mine their papers but not pass the text on, and that includes papers downloaded
from Elsevier, Wiley, and Springer. Each record still has its paper's DOI and the IDs of the
chunks it came from, so anyone with access to the paper can check it.

If every paper is open access, you can include the text. In the browser, select **bundle
includes paper text and source files**. On the command line, use `--include-text`.

The extracted values are facts, and you can share them. Cite the papers by their DOIs.
