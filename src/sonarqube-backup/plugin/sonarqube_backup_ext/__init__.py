"""SonarQube extension for the BAUER GROUP BackupHelper engine.

Ships one engine extension point (wired via an entry point in pyproject.toml):

* a **hooks** registration (``hooks.register``) - a post_restore hook that drops
  SonarQube's Elasticsearch indexes, so SonarQube rebuilds them from the restored
  database on its next start.
"""

__version__ = "0.1.0"
