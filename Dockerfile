# syntax=docker/dockerfile:1
#
# The one image every rung runs (AD-2): it carries the frozen unit of work and nothing rung-
# specific. Orchestration (cron, Argo) lives outside; this just runs `python -m eo_ingest.ingest`.
#
# Base and tooling are pinned by multi-arch *index* digests so the same Dockerfile builds an
# identical, reproducible image on linux/amd64 and linux/arm64.

# python:3.12-slim
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

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
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

CMD ["python", "-m", "eo_ingest.ingest"]
