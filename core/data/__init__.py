"""Data acquisition and persistence layer.

Pipeline overview::

    Tushare Pro ─┐
                 ├──► ingest.py ──► SQLite / Postgres
    akshare      ┘
    samples/*.csv ─► sample_loader (offline fallback for CI / no-API users)
"""

from core.data.akshare_client import AkshareClient  # noqa: F401
from core.data.ingest import IngestService  # noqa: F401
from core.data.sample_loader import SampleLoader  # noqa: F401
from core.data.tushare_client import TushareClient  # noqa: F401
