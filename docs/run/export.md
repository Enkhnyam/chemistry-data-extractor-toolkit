# Export

=== "Browser"

    Click **Report** at the top of the page, then **Records CSV**:

    ![The report page with the export buttons](../img/tutorial/10-report.png)

    The report also shows how complete each field is, what the judge flagged, and the
    distribution of any field.

=== "Python"

    ```python
    project.export("co2_hydrogenation.csv")
    ```

    ??? note "Using pandas?"
        The records go straight into a data frame:

        ```python
        import pandas as pd

        df = pd.DataFrame(project.records())
        ```

The CSV file has one row per record: your fields, the paper's DOI and title, the judge's
verdict and reasoning, and the model that produced it. It opens in Excel or any spreadsheet
program.

## Export only some papers

=== "Python"

    ```python
    project.export("methanation.csv", only=r"methanation")
    ```

=== "Browser"

    On the **Report** page, type the patterns into the two boxes under the export buttons.

## Share a dataset

The **full bundle** is a `.zip` file with the records and everything that produced them:
the fields, both prompts, the worked examples, the model settings without keys, and the
version of file2records.

=== "Python"

    ```python
    project.export("co2_hydrogenation.zip")
    ```

=== "Browser"

    On the **Report** page, click **Full bundle**.

!!! warning "Paper text stays out unless you ask for it"
    Many publishers let institutions analyze their papers but not share the text. The bundle
    therefore carries each record's DOI and the IDs of the passages it came from, not the
    text. Include the text only if every paper is open access: tick **bundle includes paper
    text** in the browser, or pass `include_text=True` in Python.

!!! success "Done"
    That's the whole pipeline. [All steps in one script](../guides/script.md) puts the
    Python parts together, and [Write better fields and prompts](../guides/prompts.md) helps
    you adapt them to your own chemistry.
