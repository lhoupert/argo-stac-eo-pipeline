#!/usr/bin/env python
"""CLI shim: reset the demo data plane — clear the logbook + empty the asset bucket (T29).

Thin entry point so `make clean` can run it; the testable logic lives in `eo_ingest.reset`.
Requires STAC_URL + S3 env (the Makefile `clean` target port-forwards MinIO + the STAC API and
sets them). Leaves the cluster + the Argo run-history archive in place — that's `make down`.
"""

from eo_ingest.reset import main

if __name__ == "__main__":
    raise SystemExit(main())
