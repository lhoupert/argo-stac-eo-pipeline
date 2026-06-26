#!/usr/bin/env python
"""CLI shim: seed the STAC logbook with deliberate per-collection gaps (T17).

Thin entry point so `make seed` can run it; the testable logic lives in `eo_ingest.seed`.
Requires STAC_URL + S3 env (the Makefile `seed` target port-forwards MinIO + the STAC API and
sets them). Data: synthetic, CC-BY-4.0 (see `eo_ingest.synthetic.build_collection`).
"""

from eo_ingest.seed import main

if __name__ == "__main__":
    raise SystemExit(main())
