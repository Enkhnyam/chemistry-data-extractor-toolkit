# Write the schema and prompts

Three settings decide what you get out of a project:

- The schema lists the fields of one record.
- The extraction prompt says what to extract and what to skip.
- The judge rubric says what makes a record right or wrong.

## Where to edit them

| Setting | Browser | Python | File in the project folder |
|---|---|---|---|
| Schema | **Settings**, then **Schema** | `project.schema = ...` | `config/schema.json` |
| Extraction prompt | **Extract**, then **Extraction prompt** | `project.prompt = ...` | `config/extract_prompt.txt` |
| Judge rubric | **Judge**, then **Judge rubric** | `project.rubric = ...` | `config/judge_prompt.txt` |

The browser and Python both save to these files, so you can use whichever you like.

## Write the schema

A record is usually one experiment. Each field has a name, a type, and a description. The
type is `string`, `number`, `integer` or `boolean`. The model reads the descriptions, so put
the unit and any conventions there:

```python
from pydantic import BaseModel, Field

class Experiment(BaseModel):
    catalyst: str | None = Field(None, description="Catalyst exactly as the paper names it; 'none' if uncatalyzed")
    catalyst_amount: str | None = Field(None, description="Loading as stated, with unit, e.g. '1 wt%'")
    temperature_c: float | None = Field(None, description="Reaction temperature in °C")
    time_min: float | None = Field(None, description="Reaction time in minutes; convert hours")
    bhet_yield_percent: float | None = Field(None, description="BHET yield, %")

project.schema = Experiment
```

You can also load a JSON file with `project.schema = "schema.json"`. The file looks like
`{"fields": [{"name": "catalyst", "type": "string", "description": "..."}]}`.

## Write the extraction prompt

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

## Write the judge rubric

Say what makes a record correct, for example that every value matches the run it describes.
Then list the mistakes to look for: a value from another run, a value quoted from another
paper, or conversion entered as yield. The judge suggests corrections but never changes a
record itself.

## Add worked examples

A worked example is a short piece of paper text together with the records it should produce.
The model sees it before every paper. Add examples in the browser on the **Extract** page.
Use two or three at most, because each one is sent with every paper and adds to the cost.
