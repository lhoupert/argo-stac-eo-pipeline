# Example — real Sentinel-2

> The whole ladder runs on a deterministic **synthetic** world so the demo is offline and
> reproducible. This example proves the *same* unit of work — unchanged — also ingests **real
> Sentinel-2** imagery, just by flipping env vars (AD-1).

## What it does

`make demo-real` runs the frozen ingester with `SOURCE_TYPE=earthsearch`:

```
ensure-collection  →  ingest --day <DATETIME>
  (mirrors the real      (queries Earth Search for a real S2 scene over BBOX,
   sentinel-2-l2a          fetches ONE asset into MinIO, registers the item in the logbook)
   collection locally)
```

The same `python -m eo_ingest.ingest` you've watched all along — only the data source changed.

## Run it

Needs the cluster up (`make up`) and network access to [Earth Search](https://earth-search.aws.element84.com/v1).

```bash
make demo-real                                   # defaults: a Wadden Sea bbox, a clear-sky day
make demo-real BBOX=6.50,53.50,6.55,53.55 DATETIME=2024-07-10
make browse                                      # the real item appears alongside the synthetic ones
```

### Keeping it light (`ASSET`)

Real S2 items carry ~17 assets; a single band COG is ~100 MB. To stay demo-friendly the example
ingests only the small **`thumbnail`** by default (`ASSET=thumbnail`). Any asset works:

```bash
make demo-real ASSET=red        # a real band COG — a ~100 MB download
```

The pipeline trims each item to the one configured asset, fetches it from its remote href into
MinIO, and rewrites the registered item's href to the `s3://` copy — so the logbook points at *your*
storage, not the upstream URL.

## Data licence & attribution

This example fetches **Copernicus Sentinel-2 L2A** data via Earth Search (Element 84), hosted on AWS
Open Data. Copernicus Sentinel data are **free and open**; usage is governed by the
[Copernicus terms](https://sentinels.copernicus.eu/web/sentinel/terms-conditions).

> **Attribution:** "contains modified Copernicus Sentinel data [year]".

The synthetic world used by the rest of the repo is generated (not real observations) and licensed
CC-BY-4.0 — see the main [README](../../README.md#license--attribution).
