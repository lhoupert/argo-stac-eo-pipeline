# Dev container

This folder ships the **whole ladder toolchain** — `uv`, `kind`, `kubectl`, `argo`, and
Docker-in-Docker — pinned to the versions the cluster actually runs. 

**Most people never touch the
commands below**, you can just open the repo in VS Code and **Reopen in Container**, or launch a **GitHub
Codespace**, and everything here is applied automatically. See
[Dev container / Codespaces](../README.md#dev-container--codespaces) in the README for that path.

The notes here are for **validating the container itself from a terminal** — no editor in the loop.
Useful for a quick "does the Codespace path still work?" check or a maintainer pass over this
less-exercised route.

## Prerequisites

- Docker running on the host.
- Node.js + npm (only to install the Dev Containers CLI).

## Exercise the ladder from the terminal if you don't want to open VS Code in the devcontainer

Run from the **repo root**:

```bash
# 1. Dev Containers CLI (one time)
npm install -g @devcontainers/cli

# 2. Build the image + Docker-in-Docker, then run `uv sync` (the slow step)
devcontainer up --workspace-folder .

# 3. Confirm the pinned toolchain inside the container
devcontainer exec --workspace-folder . bash -lc \
  'uv --version; kubectl version --client; kind version; argo version; docker --version'

# 4. Fast offline unit tests
devcontainer exec --workspace-folder . bash -lc 'uv run pytest tests/unit -q'

# 5. Rung 0 — a real ingest, no Kubernetes (proves Docker-in-Docker works)
devcontainer exec --workspace-folder . bash -lc './stages/00-cron/run.sh'

# 6. The full ladder — nested kind cluster + rungs 1–4
devcontainer exec --workspace-folder . bash -lc 'make check'
devcontainer exec --workspace-folder . bash -lc 'make up'
devcontainer exec --workspace-folder . bash -lc 'make demo STAGE=01'
```

Each `devcontainer exec … bash -lc '…'` just runs a command **inside** the container. Working
interactively instead? Open one shell with `devcontainer exec --workspace-folder . bash` and run the
`make …` targets normally — the per-command form above is only for driving it non-interactively.

## Clean up

```bash
# delete the in-cluster kind cluster (frees the most)
devcontainer exec --workspace-folder . bash -lc 'make down'
# remove the dev container itself
docker rm -f "$(docker ps -aq --filter label=devcontainer.local_folder=$PWD)"
```

## Two things to know

- **`uv sync` runs twice** — once automatically as the container's `postCreateCommand`, so steps 3+
  already have dependencies; you don't run it yourself.
- **Sizing** — steps 1–5 are light, but step 6 runs a *nested* Kubernetes cluster and needs the
  4-core / 8 GB+ tier (a free 2-core Codespace only handles rung 0). See the
  [honest sizing table](../README.md#dev-container--codespaces).
