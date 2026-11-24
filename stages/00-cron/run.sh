#!/usr/bin/env bash
# Rung 0 — run the one image (the frozen unit of work) against a local S3 store via plain
# `docker run`. No Kubernetes, no catalog: STAC_URL is deliberately unset, so the item is
# written to object storage and nothing else. See README.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

IMAGE="${EO_INGEST_IMAGE:-eo-ingest:dev}"
NETWORK="eo-rung0"
MINIO_NAME="eo-rung0-minio"
# The S3-compatible store, pinned by digest (same as the cluster rung). RustFS replaces MinIO,
# whose community images are no longer published on Docker Hub (Nov 2026).
S3_IMAGE="rustfs/rustfs:1.0.6@sha256:ee717072290bec9b11abfc0365f8310b00df1cd9b3639943edae47bdef05044a"
BUCKET="${S3_BUCKET:-eo-assets}"
COLLECTION="${COLLECTION:-synthetic-aurora-veil}"
DAY="${1:-2026-03-14}"
KEY="minioadmin"

log() { printf '\033[1;34m[rung0]\033[0m %s\n' "$*"; }

# 1. The one image — built on first use, then reused unchanged across every rung.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  log "building $IMAGE"
  docker build -t "$IMAGE" "$REPO_ROOT"
fi

# 2. A throwaway network so the ingester can reach the store by name.
docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null

# 3. Local object store — the only sink.
if ! docker ps --format '{{.Names}}' | grep -qx "$MINIO_NAME"; then
  log "starting the S3 store ($MINIO_NAME)"
  docker run -d --rm --name "$MINIO_NAME" --network "$NETWORK" \
    -p 9000:9000 -p 9001:9001 \
    -e "RUSTFS_ACCESS_KEY=$KEY" -e "RUSTFS_SECRET_KEY=$KEY" -e "RUSTFS_CONSOLE_ENABLE=true" \
    "$S3_IMAGE" >/dev/null
fi

# 4. Bucket (idempotent; waits for the store to accept connections).
docker run --rm --network "$NETWORK" \
  -e "S3_ENDPOINT_URL=http://$MINIO_NAME:9000" \
  -e "AWS_ACCESS_KEY_ID=$KEY" \
  -e "AWS_SECRET_ACCESS_KEY=$KEY" \
  -e "S3_BUCKET=$BUCKET" \
  "$IMAGE" python -m eo_ingest.bucket >/dev/null

# 5. The ingest — STAC_URL is not set, so registration is skipped.
log "ingesting $COLLECTION for $DAY -> s3://$BUCKET (no catalog)"
docker run --rm --network "$NETWORK" \
  -e "S3_ENDPOINT_URL=http://$MINIO_NAME:9000" \
  -e "AWS_ACCESS_KEY_ID=$KEY" \
  -e "AWS_SECRET_ACCESS_KEY=$KEY" \
  -e "S3_BUCKET=$BUCKET" \
  -e "COLLECTION=$COLLECTION" \
  "$IMAGE" python -m eo_ingest.ingest --day "$DAY"

log "done — the asset is in the S3 store. There is no logbook to consult, and no UI showed this ran."
