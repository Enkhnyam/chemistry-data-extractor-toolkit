# Use the command line

The `file2records` command runs the same steps as Python. Before you use it, set the
project's fields and prompts in the browser or in Python. It's useful for long runs on a server
or in a scheduled job.

It reads the model settings from the same `.env` file as Python
([step 3](../get-started/project.md)).

```bash
file2records add my-project papers/       # add papers
file2records check my-project             # what's still missing
file2records extract my-project           # extract the papers not done yet
file2records judge my-project             # judge them
file2records export my-project out.csv    # write the records
```

`extract`, `judge` and `export` take the same paper filters as Python:

```bash
file2records extract my-project --only "hydrogenation|methanation" --exclude "electrocatalytic|electroreduction"
```

To search the papers' text, use `file2records search my-project "CO2\s+conversion"`.

The [command line reference](../reference/cli.md) lists every command and option.
