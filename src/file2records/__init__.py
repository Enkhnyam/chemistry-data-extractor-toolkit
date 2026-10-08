"""file2records: turn a folder of papers into a structured dataset you can check.

    import file2records as fr
    project = fr.Project("my-review")
    project.add("papers/")
    project.extract()                     # model from .env, see fr.connect
    project.export("dataset.csv")

See project.py for the API, cli.py for the command line, main.py for the web app.
"""
__version__ = "0.3.1"

from .project import Project, connect  # noqa: E402

__all__ = ["Project", "connect", "__version__"]
