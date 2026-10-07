# Write better fields and prompts

The first extraction is rarely the best one. This page shows how to improve it, in the order
that helps most.

## Work on a few papers first

Extract two or three papers, review them, change the fields or the prompt, and extract them
again. Only then run all your papers.

=== "Browser"

    On the **Extract** page, tick only a few papers. To run a paper again, open it under
    **Review** and click **Delete this run**, then extract it again.

=== "Python"

    ```python
    project.extract(only=r"Ni/Al2O3")                 # a pattern only a few papers match
    project.extract(only=r"Ni/Al2O3", redo=True)      # again, after changing the prompt
    ```

## Improve the fields

- **Put the unit in the name and in the description**, such as `temperature_c` with
  *in °C*.
- **Say how to convert**, such as *convert MPa by multiplying by 10*.
- **Show the format you want** with an example, such as *5Ni5Zn/SiO2*.
- **Use text for values you don't want converted**, such as a catalyst loading written
  *1 wt%*. Make it a `string` field.

## Improve the prompt

These rules made the biggest difference on a corpus of about 1,000 PET depolymerization
papers, roughly in order of how much they helped:

1. Define a record. For example: one record per run, and each row of a results table is a
   run.
2. List what to skip: values quoted from other papers, predictions from a design of
   experiments, and values that appear only in a figure.
3. Say that conditions given once in a table caption or footnote apply to every row.
4. Say that missing values are null and never 0.
5. Name the fields that are easy to confuse. Conversion and yield are the usual pair.

How long the prompt is matters less than these rules. A short and a long prompt with the same
rules scored about the same.

!!! warning
    Don't copy values from papers you plan to extract into the prompt's examples. The model
    then gets those papers right for the wrong reason. Use made-up names such as Cat-A instead.

In the browser, the prompt box shows a complete example prompt in gray. **Start from the
example** copies it into the box so you can edit it.

## Improve the judge rubric

Say what makes a record correct, for example that every value matches the run it describes.
Then list the mistakes to look for: a value from another run, a value quoted from another
paper, or conversion entered as yield. The judge suggests corrections but never changes a
record itself.

## Add worked examples

A worked example is a short piece of paper text together with the records it should produce.
The model sees it before every paper. Add examples in the browser on the **Extract** page,
under **Worked examples**. Use two or three at most, because each one is sent with every
paper.

## Where the settings are stored

The browser and Python save the same files in the project folder, so you can edit them
either way, or directly:

| Setting | Browser | Python | File |
|---|---|---|---|
| Fields | **Settings**, then **Schema** | `project.schema` | `config/schema.json` |
| Extraction prompt | **Extract**, then **Extraction prompt** | `project.prompt` | `config/extract_prompt.txt` |
| Judge rubric | **Judge**, then **Judge rubric** | `project.rubric` | `config/judge_prompt.txt` |
