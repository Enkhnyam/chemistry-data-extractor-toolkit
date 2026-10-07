# Fields

A **record** is one row of your dataset, usually one experiment. The **fields** are its
columns. Each field has three parts:

Name
:   Lowercase, with underscores, such as `temperature_c`. It becomes the column name.

Type
:   `string` for text, `number` for decimals, `integer` for whole numbers, or `boolean` for
    yes or no.

Description
:   What to put in the field. The model reads it, so give the unit and how to convert.

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

## Set the fields

=== "Browser"

    1. Click **Settings**, and scroll to **Schema**.
    2. Click **Clear all** to remove the gray example rows.
    3. Click **Add field** six times, and fill in the rows from the table.
    4. Click **Save changes**.

    !!! success "You should see"
        ![The six fields](../img/tutorial/04-fields.png)

=== "Python"

    Write the fields as a dictionary: the name, then the type and the description.

    ```python
    project.schema = {
        "catalyst": ("string", "Catalyst as the paper names it, e.g. 5Ni5Zn/SiO2"),
        "temperature_c": ("number", "Reaction temperature in °C"),
        "pressure_bar": ("number", "Total pressure in bar; convert MPa by multiplying by 10"),
        "co2_conversion_percent": ("number", "CO2 conversion, %"),
        "main_product": ("string", "Main product, e.g. CO, CH4, methanol"),
        "selectivity_percent": ("number", "Selectivity to the main product, %"),
    }
    ```

    !!! success "To check"
        ```python
        print([field["name"] for field in project.schema])
        ```

        ```console
        ['catalyst', 'temperature_c', 'pressure_bar', 'co2_conversion_percent', 'main_product', 'selectivity_percent']
        ```

    ??? note "Other ways to write the fields"
        A text field can be just its description:
        `{"catalyst": "Catalyst as the paper names it"}`.

        If you use pydantic, a model class works too:

        ```python
        from pydantic import BaseModel, Field

        class Experiment(BaseModel):
            catalyst: str | None = Field(None, description="Catalyst as the paper names it")
            temperature_c: float | None = Field(None, description="Reaction temperature in °C")

        project.schema = Experiment
        ```

        And a JSON file: `project.schema = "schema.json"`.
<!-- vale Google.Latin = YES -->

## Tips

!!! tip "Good fields"
    - **Put the unit in the name and the description**, such as `temperature_c` with
      *in °C*.
    - **Say how to convert**, such as *convert MPa by multiplying by 10*.
    - **Show the format you want** with an example, such as *5Ni5Zn/SiO2*.
    - **Start with a few fields.** Add more once the first ones come out right.

!!! info "Missing values stay empty"
    When a paper doesn't report a value, the field stays empty. The model is told not to
    guess, and the judge flags records where it did.

Continue with [Extraction prompt](prompt.md).
