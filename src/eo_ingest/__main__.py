"""``python -m eo_ingest`` entrypoint — ingest one unit of work."""

from .ingest import main

if __name__ == "__main__":
    raise SystemExit(main())
