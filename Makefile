# argo-stac-eo-pipeline — local ladder control surface (T13)
#
# One command brings up the whole core stack on a kind cluster; one tears it down. Every rung from
# 1 on runs `make demo STAGE=NN`, which submits that stage's Argo workflow against the SAME
# ingester image loaded here.
#
#   make up                 # kind + MinIO + STAC API + stac-browser + Argo + bucket
#   make ui                 # port-forward the Argo UI
#   make browse             # port-forward the STAC API + stac-browser UI
#   make demo STAGE=01      # submit stage 01's workflow and watch it
#   make seed               # seed the logbook with deliberate gaps (T17)
#   make down               # delete the cluster

SHELL := /usr/bin/env bash

# --- knobs (override on the command line) --------------------------------------------------------
CLUSTER ?= eo-ladder
NS      ?= eo
IMAGE   ?= eo-ingest:dev

KIND_CONFIG := deploy/kind-cluster.yaml
CORE        := deploy/core


.DEFAULT_GOAL := help
.PHONY: help check up down ui browse status seed demo clean reset clip stills slides tools-record build rebuild _check-stage

# -------------------------------------------------------------------------------------------------
help: ## Show this help
	@echo "argo-stac-eo-pipeline — local ladder"
	@echo
	@echo "First run:  make check  →  make up  →  make demo STAGE=01  →  make browse / make ui"
	@echo "Reset:      make clean (keeps the cluster)  ·  make reset (clean + re-seed)  ·  make down"
	@echo
	@echo "All targets:"
	@grep -E '^[a-z][a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

check: ## Preflight: are Docker (running) + kind/kubectl/argo/uv installed? Run before `make up`.
	@scripts/check_tools.sh

# --- guards (run as prerequisites, before any docker/kind/kubectl work) --------------------------
_check-stage:
	@if [ -z "$(STAGE)" ]; then \
		echo "STAGE is required, e.g. 'make demo STAGE=01'."; \
		echo "Available stages:"; ls -d stages/*/ 2>/dev/null | sed 's,stages/,  ,;s,/$$,,' || true; \
		exit 2; \
	fi

# --- lifecycle -----------------------------------------------------------------------------------
build: ## Build the one ingester image (skipped if it already exists)
	@if docker image inspect "$(IMAGE)" >/dev/null 2>&1; then \
		echo "image $(IMAGE) already built — skipping"; \
	else \
		echo "building $(IMAGE)"; docker build -t "$(IMAGE)" .; \
	fi

rebuild: ## Force-rebuild the ingester image and reload it into the cluster (after code changes)
	docker build -t "$(IMAGE)" .
	kind load docker-image "$(IMAGE)" --name "$(CLUSTER)"

up: build ## Bring up the full core stack on kind
	@# 1. Cluster (idempotent).
	@if kind get clusters 2>/dev/null | grep -qx "$(CLUSTER)"; then \
		echo "kind cluster $(CLUSTER) already exists"; \
	else \
		echo "creating kind cluster $(CLUSTER)"; kind create cluster --config $(KIND_CONFIG); \
	fi
	@# 2. Make the one image available to in-cluster workflow pods.
	kind load docker-image "$(IMAGE)" --name "$(CLUSTER)"
	@# 3. Namespace, then the stack. Manifests carry `namespace: eo`; Argo's vendored
	@#    install.yaml does not, so it alone needs `-n $(NS)`.
	kubectl apply -f $(CORE)/namespace.yaml
	kubectl apply -f $(CORE)/minio/
	kubectl apply -f $(CORE)/stac/
	kubectl apply --server-side -n $(NS) -f $(CORE)/argo/install.yaml
	kubectl apply -f $(CORE)/argo/rbac.yaml
	@# Workflow archive on the pgSTAC Postgres (durable run history for the rung-4 report). Both the
	@# controller and the server read this config at startup, so restart them to pick up persistence.
	kubectl apply -f $(CORE)/argo/archive.yaml
	kubectl -n $(NS) rollout restart deploy/workflow-controller deploy/argo-server
	@# 4. Wait for everything to be Ready (pgSTAC migrates on first boot — give it room).
	kubectl -n $(NS) rollout status deploy/minio --timeout=120s
	kubectl -n $(NS) rollout status deploy/pgstac --timeout=300s
	kubectl -n $(NS) rollout status deploy/stac-api --timeout=120s
	kubectl -n $(NS) rollout status deploy/stac-browser --timeout=120s
	kubectl -n $(NS) rollout status deploy/workflow-controller deploy/argo-server --timeout=120s
	kubectl -n $(NS) wait --for=condition=complete job/minio-bucket-bootstrap --timeout=120s
	@echo
	@echo "core stack is up. Next: open the Argo UI ('make ui'), then in a 2nd terminal run"
	@echo "  'make demo STAGE=01' and watch it execute · 'make browse' for the logbook"
	@echo "  full guided tour (rungs 0→4): docs/walkthrough.md"

down: ## Delete the kind cluster (idempotent)
	@if kind get clusters 2>/dev/null | grep -qx "$(CLUSTER)"; then \
		echo "deleting kind cluster $(CLUSTER)"; kind delete cluster --name "$(CLUSTER)"; \
	else \
		echo "kind cluster $(CLUSTER) not found — nothing to do"; \
	fi

# --- access ---------------------------------------------------------------------------------------
# _url PORT — resolve the right URL for a given port.
#   • Locally:             http://localhost:PORT
#   • GitHub Codespaces:   https://<name>-PORT.<domain>   (port must be forwarded / set to Public)
define _url
$$(if [ -n "$$CODESPACE_NAME" ]; then \
	echo "https://$$CODESPACE_NAME-$(1).$${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"; \
else \
	echo "http://localhost:$(1)"; \
fi)
endef

# _open PORT — open the browser if possible; fall back to printing the URL.
#   • macOS (local):      `open` launches the default browser.
#   • Codespace:          prints the proxy URL (browser can't reach localhost).
#   • devcontainer/Linux: `open` and `xdg-open` don't work; VS Code's onAutoForward
#                         in devcontainer.json re-opens the tab automatically, but we
#                         also print the URL so it's always visible in the terminal.
define _open
if [ -n "$$CODESPACE_NAME" ]; then \
	d=$${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}; \
	echo "  open in browser -> https://$$CODESPACE_NAME-$(1).$$d"; \
	echo "  (ports are set to Public via devcontainer.json — no auth needed)"; \
elif command -v open >/dev/null 2>&1; then \
	open "http://localhost:$(1)"; \
else \
	echo "  open in browser -> http://localhost:$(1)"; \
	( command -v xdg-open >/dev/null 2>&1 && xdg-open "http://localhost:$(1)" ) || true; \
fi
endef

ui: ## Port-forward the Argo Workflows UI and open it (localhost:2746 or Codespace URL)
	@# Background the forward, wait for it to bind, open/print the URL, then hold with `wait`.
	@# argo-server runs with --secure=false (plain HTTP), so there is no cert warning to accept.
	@kubectl -n $(NS) port-forward svc/argo-server 2746:2746 >/dev/null 2>&1 & \
		ui_pf=$$!; trap 'kill $$ui_pf 2>/dev/null' EXIT; sleep 2; \
		echo "Argo UI -> http://localhost:2746  (auth-mode=server, no token)"; \
		$(call _open,2746); \
		wait $$ui_pf

browse: ## Port-forward STAC API + MinIO + stac-browser and open the browser UI
	@# stac-browser is a client-side app that fetches SB_catalogUrl from the *user's real browser*.
	@# Locally that's http://localhost:8081.  In a Codespace the browser can't reach localhost, so
	@# we patch the deployment to use the codespace proxy URL before starting the port-forwards.
	@# MinIO is on 9100 for browser-fetchable thumbnail previews.
	@if [ -n "$$CODESPACE_NAME" ]; then \
		d=$${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}; \
		catalog_url="https://$$CODESPACE_NAME-8081.$$d"; \
		echo "Codespace detected — patching stac-browser SB_catalogUrl -> $$catalog_url"; \
		kubectl -n $(NS) set env deploy/stac-browser SB_catalogUrl="$$catalog_url"; \
		kubectl -n $(NS) rollout status deploy/stac-browser --timeout=60s; \
	fi
	@kubectl -n $(NS) port-forward svc/stac-api 8081:80 >/dev/null 2>&1 & \
		api_pf=$$!; \
		kubectl -n $(NS) port-forward svc/minio 9100:9000 >/dev/null 2>&1 & \
		minio_pf=$$!; \
		kubectl -n $(NS) port-forward svc/stac-browser 8082:80 >/dev/null 2>&1 & \
		sb_pf=$$!; \
		trap 'kill $$api_pf $$minio_pf $$sb_pf 2>/dev/null' EXIT; sleep 2; \
		echo "STAC API     -> http://localhost:8081"; \
		echo "MinIO assets -> http://localhost:9100"; \
		echo "stac-browser -> http://localhost:8082"; \
		$(call _open,8082); \
		wait $$api_pf $$minio_pf $$sb_pf

status: ## Show cluster health (pods) + the demo URLs at a glance
	@if ! kind get clusters 2>/dev/null | grep -qx "$(CLUSTER)"; then \
		echo "kind cluster $(CLUSTER) not found — run 'make up' first"; \
	else \
		echo "pods in namespace $(NS):"; \
		kubectl -n $(NS) get pods; \
		echo; \
		if [ -n "$$CODESPACE_NAME" ]; then \
			d=$${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}; \
			echo "URLs (Codespace — set ports to Public if access is denied):"; \
			echo "  Argo UI      https://$$CODESPACE_NAME-2746.$$d   (make ui)"; \
			echo "  STAC API     https://$$CODESPACE_NAME-8081.$$d   (make browse)"; \
			echo "  stac-browser https://$$CODESPACE_NAME-8082.$$d   (make browse)"; \
		else \
			echo "URLs (each needs its port-forward — the command in parentheses):"; \
			echo "  Argo UI        http://localhost:2746    (make ui)"; \
			echo "  STAC API       http://localhost:8081    (make browse)"; \
			echo "  stac-browser   http://localhost:8082    (make browse)"; \
		fi; \
	fi

# --- demos --------------------------------------------------------------------------------------
ARGS ?=  # extra argo submit flags, e.g. ARGS="-p collection=synthetic-tidal-glass"

demo: _check-stage ## Submit a stage's workflow and watch it (STAGE=NN required, ARGS optional)
	@dir=$$(ls -d stages/$(STAGE)-*/ 2>/dev/null | head -n1); dir=$${dir%/}; \
	if [ -z "$$dir" ]; then \
		echo "no stage matching 'stages/$(STAGE)-*' — has it been built yet?"; exit 2; \
	fi; \
	wf=$$dir/workflows; \
	if [ ! -d "$$wf" ] || [ -z "$$(ls -A $$wf/*.yaml 2>/dev/null)" ]; then \
		echo "no workflows in $$wf"; exit 2; \
	fi; \
	echo "submitting $$wf"; \
	for f in $$wf/*.yaml; do argo submit -n $(NS) --watch "$$f" $(ARGS); done


seed: ## Seed the logbook with two missions + deliberate gaps (T17)
	@# The seed reuses the full ingest path, so it needs BOTH the object store (assets) and the
	@# logbook (items). Port-forward both, set the env the ingester reads, run the script; the
	@# trap tears the forwards down on exit.
	@echo "seeding logbook (two collections with planted gaps) via scripts/seed_stac.py"
	@# Pin EVERY value the seed reads, so an ambient S3_BUCKET / S3_ENDPOINT_URL / SOURCE_TYPE in the
	@# caller's shell (e.g. a real cloud profile) can't leak into this local demo run.
	@kubectl -n $(NS) port-forward svc/minio 9100:9000 >/dev/null 2>&1 & m=$$!; \
		kubectl -n $(NS) port-forward svc/stac-api 8081:80 >/dev/null 2>&1 & s=$$!; \
		trap 'kill $$m $$s 2>/dev/null' EXIT; sleep 3; \
		SOURCE_TYPE=synthetic \
		S3_ENDPOINT_URL=http://localhost:9100 S3_BUCKET=eo-assets \
		AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
		STAC_URL=http://localhost:8081 \
		ASSET_BASE_URL=http://localhost:9100/eo-assets \
		uv run python scripts/seed_stac.py

clean: ## Reset demo state — delete workflows + clear the logbook + empty the bucket (keeps the cluster)
	@# Removes what a demo *produced* without tearing the cluster down (that's `make down`): the
	@# submitted Argo objects, the STAC items/collections, and the MinIO assets. The Argo
	@# run-history archive is durable and intentionally left in place. All one shell so the
	@# cluster guard can exit early and the port-forward trap cleans up on exit.
	@if ! kind get clusters 2>/dev/null | grep -qx "$(CLUSTER)"; then \
		echo "kind cluster $(CLUSTER) not found — nothing to clean (already gone)"; \
		exit 0; \
	fi; \
	echo "deleting Argo workflows + cronworkflows in namespace $(NS)"; \
	kubectl -n $(NS) delete workflows.argoproj.io,cronworkflows.argoproj.io --all --ignore-not-found || true; \
	echo "clearing the logbook + emptying the asset bucket via scripts/reset_demo.py"; \
	kubectl -n $(NS) port-forward svc/minio 9100:9000 >/dev/null 2>&1 & m=$$!; \
		kubectl -n $(NS) port-forward svc/stac-api 8081:80 >/dev/null 2>&1 & s=$$!; \
		trap 'kill $$m $$s 2>/dev/null' EXIT; sleep 3; \
		S3_ENDPOINT_URL=http://localhost:9100 S3_BUCKET=eo-assets \
		AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
		STAC_URL=http://localhost:8081 \
		uv run python scripts/reset_demo.py && \
		echo "clean done — cluster still up ('make down' for a fully pristine cluster)"

reset: ## Soft-reset then re-seed: `make clean`, then re-plant the seeded gaps (`make seed`)
	@$(MAKE) clean
	@$(MAKE) seed
