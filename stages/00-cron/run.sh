#!/usr/bin/env bash
# Rung 0 — the honestly-fragile baseline.
#
# Runs the ONE image (the frozen unit of work) against a local MinIO via plain `docker run`.
# NO Kubernetes, NO catalog: STAC_URL is deliberately unset, so the item is written to object
# storage and nothing else. If this fails at 3am there is nowhere to look — that is the lesson
# this rung teaches. See README.md. The 0->1 delta (next rung) is: Argo runs the same image AND
# you gain a logbook (the STAC API) to look at.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

IMAGE="${EO_INGEST_IMAGE:-eo-ingest:dev}"
NETWORK="eo-rung0"
MINIO_NAME="eo-rung0-minio"
# Pinned by digest for reproducibility (same as the cluster rung will use).
MINIO_IMAGE="minio/minio@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
MC_IMAGE="minio/mc@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727"
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

# 2. A throwaway network so the ingester can reach MinIO by name.
docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null

# 3. Local MinIO — the only sink. No cluster, no kubectl, no kind.
if ! docker ps --format '{{.Names}}' | grep -qx "$MINIO_NAME"; then
  log "starting MinIO ($MINIO_NAME)"
  docker run -d --rm --name "$MINIO_NAME" --network "$NETWORK" \
    -p 9000:9000 -p 9001:9001 \
    -e "MINIO_ROOT_USER=$KEY" -e "MINIO_ROOT_PASSWORD=$KEY" \
    "$MINIO_IMAGE" server /data --console-address ":9001" >/dev/null
  log "waiting for MinIO to accept connections"
  for _ in $(seq 1 30); do
    if docker run --rm --network "$NETWORK" "$MC_IMAGE" \
         alias set rung0 "http://$MINIO_NAME:9000" "$KEY" "$KEY" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

# 4. Bucket (idempotent).
docker run --rm --network "$NETWORK" --entrypoint sh "$MC_IMAGE" -c \
  "mc alias set rung0 http://$MINIO_NAME:9000 $KEY $KEY >/dev/null && mc mb -p rung0/$BUCKET >/dev/null 2>&1 || true"

# 5. The ingest — STAC_URL is NOT set, so registration is skipped (no logbook at rung 0).
log "ingesting $COLLECTION for $DAY -> s3://$BUCKET (no catalog)"
docker run --rm --network "$NETWORK" \
  -e "S3_ENDPOINT_URL=http://$MINIO_NAME:9000" \
  -e "AWS_ACCESS_KEY_ID=$KEY" \
  -e "AWS_SECRET_ACCESS_KEY=$KEY" \
  -e "S3_BUCKET=$BUCKET" \
  -e "COLLECTION=$COLLECTION" \
  "$IMAGE" python -m eo_ingest.ingest --day "$DAY"

log "done — the asset is in MinIO. There is no logbook to consult, and no UI showed this ran."
