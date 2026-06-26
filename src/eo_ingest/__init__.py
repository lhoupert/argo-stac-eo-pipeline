"""eo_ingest — the shared, stable ingestion business logic for the EO maturity-ladder demo.

The unit-of-work (`ingest`) stays frozen across rungs; only the orchestration around it grows.
See SPEC.md for the full design.
"""

__version__ = "0.1.0"
