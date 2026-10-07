# Write the schema and prompts

Three things decide what you get: the **schema** (the fields of one record), the **extraction
prompt** (what to extract and what to skip) and the **judge rubric** (what counts as right).

## Where they live

| | Browser | Python | File in the project folder |
|---|---|---|---|
| Schema | Settings → Schema | `project.schema = ...` | `config/schema.json` |
| Extraction prompt | Extract → Extraction prompt | `project.prompt = ...` | `config/extract_prompt.txt` |
| Judge rubric | Judge → Judge rubric | `project.rubric = ...` | `config/judge_prompt.txt` |

All three routes write the same files, so edit wherever is convenient.

## The schema

One record is one experiment. Each field has a name, a type (`string`, `number`, `integer`,
`boolean`) and a description — **the model reads the description**, so put the unit and the
convention in it:

```python
from pydantic import BaseModel, Field

class Experiment(BaseModel):
    catalyst: str | None = Field(None, description="Catalyst exactly as the paper names it; 'none' if uncatalysed")
    catalyst_amount: str | None = Field(None, description="Loading as stated, with unit, e.g. '1 wt%'")
    temperature_c: float | None = Field(None, description="Reaction temperature in °C")
    time_min: float | None = Field(None, description="Reaction time in minutes (convert hours)")
    bhet_yield_percent: float | None = Field(None, description="BHET yield, %")

project.schema = Experiment
```

A JSON file works too: `project.schema = "schema.json"` with
`{"fields": [{"name": "catalyst", "type": "string", "description": "..."}]}`.

## The extraction prompt

What worked on the PET depolymerisation corpus, in order of impact:

1. **What counts as one record** — "one record per run; each row of a results table is a run".
2. **What to skip** — values quoted from other papers (a "Ref." column, "[12]"), model
   predictions from design-of-experiments, values only in a figure.
3. **Conditions stated once** — "conditions in a table caption or footnote apply to every row".
4. **Nulls** — "anything not reported is null, never 0".
5. **Easily confused fields** — "conversion and yield are different; never swap them".

Length matters less than these rules: terse and verbose prompts with the same rules scored
within noise of each other.

!!! warning "Don't put real answers in the prompt"
    Examples copied from papers you will extract inflate the results. Use made-up catalysts
    ("Cat-A") in examples.

The browser's prompt box shows a full working example in grey; **Start from the example** copies
it in.

## The judge rubric

Say what makes a record right ("every value matches the run, units converted") and wrong
("a value from another run", "a value quoted from another paper", "conversion in the yield
field"). The judge proposes fixes; it never applies them.

## Worked examples (optional)

A short piece of paper text paired with the records it should produce, sent with every paper.
Add them in the browser (Extract → Worked examples). Two or three at most — each is re-sent on
every call.
