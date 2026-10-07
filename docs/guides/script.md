# All steps in one script

Everything from [Get started](../get-started.md) in one Python file. Put these next to it:

- `.env` with your endpoint, key, and model ([API key](../setup/api-key.md),
  [models](../setup/models.md))
- `papers/` with your papers ([Papers](../setup/papers.md))
- `prompt.txt` and `rubric.txt` ([prompt](../define/prompt.md), [rubric](../define/rubric.md))

```python title="build.py"
from pathlib import Path

import file2records as fr

# Set up: the model comes from .env
project = fr.Project("my-project")
project.add("papers")

# Define what to extract
project.schema = {
    "catalyst": ("string", "Catalyst as the paper names it, e.g. 5Ni5Zn/SiO2"),
    "temperature_c": ("number", "Reaction temperature in °C"),
    "pressure_bar": ("number", "Total pressure in bar; convert MPa by multiplying by 10"),
    "co2_conversion_percent": ("number", "CO2 conversion, %"),
    "main_product": ("string", "Main product, e.g. CO, CH4, methanol"),
    "selectivity_percent": ("number", "Selectivity to the main product, %"),
}
project.prompt = Path("prompt.txt")
project.rubric = Path("rubric.txt")

# Run
papers = {
    "only": r"hydrogenation|methanation",
    "exclude": r"electrocatalytic|electroreduction",
}
for result in project.extract(**papers):
    print("extracted", result["id"], result.get("n_records"), result.get("error", ""))

for result in project.judge(**papers):
    print("judged", result["id"], result.get("n_verdicts"), result.get("error", ""))

project.export("co2_hydrogenation.csv", **papers)
```

Run it, then review the records in the browser:

```bash
python build.py
file2records serve my-project
```

!!! success "You should see"
    ```console
    extracted pmc12631322-05a5c716 24
    extracted pmc13614198-d3bc8887 18
    extracted pmc13631360-011f2613 13
    judged pmc12631322-05a5c716 24
    judged pmc13614198-d3bc8887 18
    judged pmc13631360-011f2613 13
    ```

    The numbers vary a little from run to run. If you run the script again, papers that are
    already done are skipped, and nothing is printed for them.
