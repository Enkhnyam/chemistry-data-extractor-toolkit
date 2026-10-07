# 5. Define the fields

A record is one row of your dataset, usually one experiment. The fields are its columns.
Each field has:

Name
:   Lowercase, with underscores, such as `temperature_c`. It becomes the column name.

Type
:   `string` for text, `number` for decimals, `integer` for whole numbers, or `boolean` for
    yes or no.

Description
:   What to put in the field. The model reads it, so give the unit and any convention.

For the example papers, use these six fields:

<!-- vale Google.Latin = NO -->
| Name | Type | Description |
|---|---|---|
| `catalyst` | string | Catalyst as the paper names it, e.g. 5Ni5Zn/SiO2 |
| `temperature_c` | number | Reaction temperature in °C |
| `pressure_bar` | number | Total pressure in bar; convert MPa by multiplying by 10 |
| `co2_conversion_percent` | number | CO2 conversion, % |
| `main_product` | string | Main product, e.g. CO, CH4, methanol |
| `selectivity_percent` | number | Selectivity to the main product, % |

=== "Browser"

    1. Click **Settings**, and scroll to **Schema**.
    2. Click **Clear all** to remove the gray example rows.
    3. Click **Add field** six times, and fill in the rows from the table.
    4. Click **Save changes**.

    ![The six fields](../img/tutorial/04-fields.png)

=== "Python"

    Describe a record as a class. Each attribute is a field: the type is `str`, `float`,
    `int` or `bool`, and `description` is what the model reads.

    ```python
    from pydantic import BaseModel, Field

    class Experiment(BaseModel):
        catalyst: str | None = Field(None, description="Catalyst as the paper names it, e.g. 5Ni5Zn/SiO2")
        temperature_c: float | None = Field(None, description="Reaction temperature in °C")
        pressure_bar: float | None = Field(None, description="Total pressure in bar; convert MPa by multiplying by 10")
        co2_conversion_percent: float | None = Field(None, description="CO2 conversion, %")
        main_product: str | None = Field(None, description="Main product, e.g. CO, CH4, methanol")
        selectivity_percent: float | None = Field(None, description="Selectivity to the main product, %")

    project.schema = Experiment
    ```

    Each field is `... | None = Field(None, ...)` because a paper doesn't always report
    every value. A missing value stays empty instead of being guessed.

    To check what was saved:

    ```python
    print([f["name"] for f in project.schema])
    ```

    ```console
    ['catalyst', 'temperature_c', 'pressure_bar', 'co2_conversion_percent', 'main_product', 'selectivity_percent']
    ```
<!-- vale Google.Latin = YES -->

!!! tip "Good fields"
    Put the unit in the name and in the description, such as `temperature_c` with *in °C*.
    Show the format you want with an example, such as *5Ni5Zn/SiO2*. Start with a few fields,
    and add more once the first ones come out right.

Continue with [Write the extraction prompt](prompt.md).
