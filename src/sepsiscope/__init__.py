"""SepsiScope: explainable, alarm-budgeted sepsis early warning (research prototype)."""

# Must stay the first import: disables telemetry before mlflow can be imported.
from sepsiscope import _privacy  # noqa: F401  # isort: skip

from importlib.metadata import version as _version

__version__ = _version("sepsiscope")
