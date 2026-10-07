# Run it from a script

Everything the browser does also works from Python and from the command line. This page
does the [tutorial](../tutorial.md) again, without the browser.

## Save your model settings in a file

Make a file called `.env` in the folder you work in, with the three values from steps 2 and 3
of the tutorial:

```bash title=".env"
FILE2RECORDS_ENDPOINT=https://chat.kiconnect.nrw/api/v1
FILE2RECORDS_API_KEY=paste-your-key-here
FILE2RECORDS_MODEL=gpt-oss-120b
```

`FILE2RECORDS_MODEL` can be the model's name as any page of your service writes it, such as
`OpenAI GPT OSS 120b` or `gpt-oss-120b`, or part of it, such as `gpt-oss`.

## From a Python script

```python title="build.py"
from pydantic import BaseModel, Field
import file2records as fr

class Run(BaseModel):
    catalyst: str | None = Field(None, description="Catalyst as the paper names it, e.g. 5Ni5Zn/SiO2")
    temperature_c: float | None = Field(None, description="Reaction temperature in °C")
    pressure_bar: float | None = Field(None, description="Total pressure in bar; convert MPa by multiplying by 10")
    co2_conversion_percent: float | None = Field(None, description="CO2 conversion, %")
    main_product: str | None = Field(None, description="Main product, e.g. CO, CH4, methanol")
    selectivity_percent: float | None = Field(None, description="Selectivity to the main product, %")

project = fr.Project("my-project")
project.add("papers")
project.schema = Run
project.prompt = """Extract every CO2 hydrogenation experiment this paper reports. One record per
catalyst and reaction condition; each row of a results table is one record. Skip values quoted
from other papers. If the paper doesn't report a value, use null."""
project.rubric = """Check each record against the paper. A record is wrong if a value belongs to
a different experiment or comes from another paper. Give the correct value and quote the paper."""

print(project.check("extract"))          # [] means ready
project.extract(on_paper=print)
project.judge(on_paper=print)
project.export("co2_hydrogenation.csv")
```

```console
$ python build.py
[]
{'id': 'pmc12631322-05a5c716', 'n_records': 19, 'seconds': 18.6, 'usage': {...}}
{'id': 'pmc13614198-d3bc8887', 'n_records': 10, 'seconds': 19.2, 'usage': {...}}
{'id': 'pmc13631360-011f2613', 'n_records': 20, 'seconds': 31.5, 'usage': {...}}
{'id': 'pmc12631322-05a5c716', 'n_verdicts': 19, 'seconds': 22.1, 'usage': {...}}
{'id': 'pmc13614198-d3bc8887', 'n_verdicts': 10, 'seconds': 15.2, 'usage': {...}}
{'id': 'pmc13631360-011f2613', 'n_verdicts': 20, 'seconds': 26.1, 'usage': {...}}
```

That run took about two minutes and wrote 49 records to `co2_hydrogenation.csv`. A second
run gives slightly different numbers: language models don't answer exactly the same way twice.

`Project` reads the `.env` file itself. If you run the script again, papers that are done are
skipped. To use a different model for one run, pass it:
`project.extract(model="mistral")`.

## From the command line

The command line reads the same `.env` file. It takes the fields and prompts from the
project folder, so set those first in the browser or from Python.

```bash
file2records add my-project papers/
file2records check my-project
file2records extract my-project
file2records judge my-project
file2records export my-project co2_hydrogenation.csv
```

See the [command line reference](../reference/cli.md) for every option.
