"""file2records: turn a folder of papers into a structured dataset you can check.

    import file2records as fr
    project = fr.Project("my-review")
    project.add("papers/")
    project.extract(model=fr.rwth())
    project.export("dataset.csv")

See project.py for the API, cli.py for the command line, main.py for the web app.
"""
__version__ = "0.2.0"

from .project import Project, rwth  # noqa: E402

__all__ = ["Project", "rwth", "__version__"]
