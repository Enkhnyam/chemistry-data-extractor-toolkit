# All steps in one script

The Python parts of steps 3 to 10 in one file. It needs the `.env` file from
[step 3](project.md) and the `papers` folder from [step 4](papers.md).

```python title="build.py"
from pydantic import BaseModel, Field

import file2records as fr

# 3. Create a project. The model comes from the .env file.
project = fr.Project("my-project")

# 4. Add papers.
project.add("papers")

# 5. Define the fields.
class Experiment(BaseModel):
    catalyst: str | None = Field(None, description="Catalyst as the paper names it, e.g. 5Ni5Zn/SiO2")
    temperature_c: float | None = Field(None, description="Reaction temperature in °C")
    pressure_bar: float | None = Field(None, description="Total pressure in bar; convert MPa by multiplying by 10")
    co2_conversion_percent: float | None = Field(None, description="CO2 conversion, %")
    main_product: str | None = Field(None, description="Main product, e.g. CO, CH4, methanol")
    selectivity_percent: float | None = Field(None, description="Selectivity to the main product, %")

project.schema = Experiment

# 6. Write the extraction prompt.
project.prompt = """Extract every CO2 hydrogenation experiment this paper reports. One
record per catalyst and reaction condition; each row of a results table
is one record.

Skip values quoted from other papers, values shown only in figures, and
theoretical calculations. Conditions stated once for a whole table apply
to every row of it.

If the paper doesn't report a value, use null. Never use 0 for a missing
value. Conversion and selectivity are different fields; never put one in
the other."""

# 7. Choose which papers to extract.
papers = dict(only=r"hydrogenation|methanation", exclude=r"electrocatalytic|electroreduction")

# 8. Extract the records.
project.extract(**papers, on_paper=print)

# 9. Judge the records.
project.rubric = """Check each record against the paper. A record is correct if every value
matches the experiment it describes.

A record is wrong if a value belongs to a different experiment, comes
from another paper, or puts conversion where selectivity belongs (or the
reverse). For a wrong record, give the correct value and quote the
sentence or table row that shows it."""
project.judge(**papers, on_paper=print)

# 10. Export the dataset.
project.export("co2_hydrogenation.csv", **papers)
```

Run it:

```bash
python build.py
```

Then review the records in the browser:

```bash
file2records serve my-project
```

If you run the script again, papers that are already done are skipped.
