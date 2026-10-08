# Python API

```python
import file2records as fr
```

## `fr.Project(path="workspace")`

A project folder, the same one the browser app shows. The folder is created if it doesn't exist.

### Settings

| Attribute | Get / set |
|---|---|
| `project.schema` | The fields. Set it to a dict `{name: (type, description)}`, a list of `{"name", "type", "description"}`, a path to a JSON file, or a pydantic model class. Reads back as a list. |
| `project.prompt` | The extraction prompt. Set it to text, or to a `Path` to a text file. |
| `project.examples` | Worked examples: a list of `{"text": ..., "records": [...]}`. |
| `project.rubric` | The judge rubric. Set it the same way as `prompt`. |
| `project.identifiers` | Fields whose values get an ontology identifier in the export: `{"main_product": "chebi"}` adds `main_product_curie` (such as `CHEBI:16183`), `main_product_curie_name` and `main_product_synonyms`. Any ontology in EBI's Ontology Lookup Service works. |

### Papers

| Method | Returns |
|---|---|
| `add(*paths, source_tracking=True, on_file=None)` | One dict per file with `id`, `filename`, `format`, `doi` and `n_chunks`, or with `error` if the file couldn't be read. |
| `papers()` | One dict per paper with `id`, `filename`, `format`, `doi`, `title`, `extracted`, `judged` and `n_records`. |
| `search(pattern, ignore_case=True)` | The papers whose text matches, most matches first. Each has a `matches` count and up to three `snippets`. |
| `select(only=None, exclude=None)` | The IDs of the papers that match `only` and don't match `exclude`. |

### Model stages

| Method | Does |
|---|---|
| `check(stage="extract", model=None)` | A list of what's missing. An empty list means ready. |
| `extract(model=None, *, only=None, exclude=None, redo=False, on_paper=None)` | Extracts the papers that aren't done yet and returns one result dict per paper. |
| `judge(model=None, *, only=None, exclude=None, redo=False, on_paper=None)` | Checks the extracted papers that aren't judged yet. |

`model` is usually left out: then the model chosen in the browser's settings is used, or the
one set by `FILE2RECORDS_ENDPOINT`, `FILE2RECORDS_API_KEY` and `FILE2RECORDS_MODEL`
(`FILE2RECORDS_JUDGE_MODEL`, if set, for `judge`). Otherwise
pass `fr.connect(...)` or a model name. If a stage isn't ready, it raises `RuntimeError` with a list of what's
missing. If one paper fails, its result has an `error` and the other papers still run.

### Results

| Method | Returns |
|---|---|
| `records(*, only=None, exclude=None)` | One dict per record with `doi`, `title`, your fields, `source_chunk_ids`, `judge_verdict`, `judge_critique` and more. |
| `export(path, *, only=None, exclude=None, include_text=False, include_files=False)` | Writes a `.csv` file, a `.json` file or a `.zip` bundle, and returns its path. |

## `fr.connect(api_key=None, endpoint=None, model=None)`

A model from your AI service: its endpoint, your key, and the model's name as any of the
service's pages write it, or part of it. Each argument defaults to its `FILE2RECORDS_*`
variable. It asks the service for its models and raises `RuntimeError` if the key is rejected,
the endpoint can't be reached, or the name matches no model or several.

## Errors

| Raised | When |
|---|---|
| `ValueError` | A regex that isn't valid, an export path with an unknown extension, or a schema with a mistake in it. |
| `RuntimeError` | A stage that isn't ready. The message lists what's missing. |
| `FileNotFoundError` | A path given to `add` doesn't exist. |
