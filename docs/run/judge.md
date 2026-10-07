# Judge

The judge reads each extracted paper again and checks every record against it, using your
[rubric](../define/rubric.md). It marks each record **correct** or **incorrect**, explains
why, and suggests corrected values.

=== "Browser"

    1. Click **Judge** at the top of the page.
    2. Click **Run judge on selected**.

    When it's done, the **Review** section below shows the results. See
    [Review](review.md).

=== "Python"

    ```python
    project.judge(
        only=r"hydrogenation|methanation",
        exclude=r"electrocatalytic|electroreduction",
    )

    rows = project.records()
    wrong = [row for row in rows if row["judge_verdict"] == "incorrect"]
    print(len(rows), "records,", len(wrong), "judged incorrect")
    ```

    !!! success "You should see"
        ```console
        69 records, 2 judged incorrect
        ```

    To read why a record was judged incorrect:

    ```python
    print(wrong[0]["judge_critique"])
    ```

    ```console
    The temperature listed (300 °C) is not reported in the paper for the 10Ni/C-Al-3NH4OH
    catalyst; the maximum conversion of 83.5 % is reported for a temperature range of
    350–325 °C, not a specific 300 °C. No selectivity value is given in the text.
    ```

!!! info "Only new papers are judged"
    Papers that are already judged are skipped. To judge again, for example after changing
    the rubric, pass `redo=True` in Python, or tick the papers on the **Judge** page.

Continue with [Review](review.md).
