# 10. Export the dataset

=== "Browser"

    Click **Report** at the top of the page, then **Records CSV**:

    ![The report page with the export buttons](../img/tutorial/10-report.png)

    The report also shows how complete each field is, what the judge flagged, and the
    distribution of any field.

=== "Python"

    ```python
    project.export("co2_hydrogenation.csv")
    ```

    If you use pandas, the records go straight into a data frame:

    ```python
    import pandas as pd

    df = pd.DataFrame(project.records())
    ```

The CSV file has one row per record: your fields, the paper's DOI and title, the judge's
verdict and reasoning, and the model that produced it. It opens in Excel or any spreadsheet
program.

## Export only some papers

Use the same patterns as in [step 7](choose.md):

=== "Browser"

    Type the patterns into the two boxes under the export buttons on the **Report** page.

=== "Python"

    ```python
    project.export("methanation.csv", only=r"methanation")
    ```

## Share a dataset

**Full bundle** in the browser, or a `.zip` filename in Python, exports the records
together with what produced them: the fields, both prompts, the model settings without
keys, and the version of file2records.

!!! warning "Paper text stays out unless you ask for it"
    Many publishers let institutions analyze their papers but not share the text. The bundle
    therefore carries each record's DOI and the IDs of the passages it came from, not the
    text. Include the text only if every paper is open access: tick **bundle includes paper
    text** in the browser, or pass `include_text=True` in Python.

The extracted values are facts, and you can share them. Cite the papers by their DOIs.

That's the whole pipeline. [All steps in one script](script.md) shows the Python parts
together, and [Write better fields and prompts](../guides/prompts.md) helps you adapt them to
your own chemistry.
