# syntax=docker/dockerfile:1
#
# The one image every rung runs: it carries the frozen unit of work and nothing rung-
# specific. Orchestration (cron, Argo) lives outside; this just runs `python -m eo_ingest.ingest`.
#
# Base and tooling are pinned by multi-arch *index* digests so the same Dockerfile builds an
# identical, reproducible image on linux/amd64 and linux/arm64.

# uv: a named stage rather than COPY --from=<image>, because Dependabot only reads FROM lines.
FROM ghcr.io/astral-sh/uv:0.13.10@sha256:a3ea1357342c1a4bf9a0c53a3deb1b55379aefa037338d8113d5771efa01774f AS uv

# python:3.12-alpine — smaller footprint, musl-based, far fewer OS-level CVEs.
# All runtime deps (boto3, pystac, pillow, httpx …) ship musllinux wheels on PyPI so no build
# toolchain is needed inside the image.
FROM python:3.12-alpine@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89

RUN apk upgrade --no-cache

# uv — copied in (not used as the base) so we install against the frozen lock.
COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

RUN adduser -D -u 1000 app && chown -R app:app /app
USER app

CMD ["python", "-m", "eo_ingest.ingest"]
