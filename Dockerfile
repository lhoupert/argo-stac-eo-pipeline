# syntax=docker/dockerfile:1
#
# The one image every rung runs (AD-2): it carries the frozen unit of work and nothing rung-
# specific. Orchestration (cron, Argo) lives outside; this just runs `python -m eo_ingest.ingest`.
#
# Base and tooling are pinned by multi-arch *index* digests so the same Dockerfile builds an
# identical, reproducible image on linux/amd64 and linux/arm64.

# python:3.12-alpine (2026-06-27) — smaller footprint, musl-based, far fewer OS-level CVEs.
# All runtime deps (boto3, pystac, pillow, httpx …) ship musllinux wheels on PyPI so no build
# toolchain is needed inside the image.
FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df

# Keep OS packages current; apk upgrade is fast on Alpine's minimal package set.
RUN apk upgrade --no-cache

# uv 0.5.18 — copied in (not used as the base) so we install against the frozen lock.
COPY --from=ghcr.io/astral-sh/uv:0.5.18@sha256:e2101b9e627153b8fe4e8a1249cc4194f1b38ece7f28a5a9b8f958e3b560e69c /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

# Install runtime deps + the package from the locked versions; no dev group in the image.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Drop privileges — the unit of work needs no root.
RUN adduser -D -u 1000 app && chown -R app:app /app
USER app

CMD ["python", "-m", "eo_ingest.ingest"]
