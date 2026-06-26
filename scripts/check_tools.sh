#!/usr/bin/env bash
# Preflight for the cluster rungs (T29). Verifies the host has the tools `make up` needs, so a
# fresh clone fails *here* with a clear hint rather than deep inside `make up`. Read-only: it only
# runs `command -v` and `docker info`. The dev container / Codespace ships all of these pinned
# (see README → Prerequisites), so this is for the host-install path.
set -uo pipefail

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
ok=1

# present <cmd> <why> <hint>: ✓ if on PATH, else ✗ + how to get it (and flip the exit flag).
present() {
	if command -v "$1" >/dev/null 2>&1; then
		printf '  %s✓%s %-8s %s\n' "$GREEN" "$RESET" "$1" "$2"
	else
		printf '  %s✗%s %-8s MISSING — %s\n' "$RED" "$RESET" "$1" "$3"
		ok=0
	fi
}

echo "Preflight — tools needed to run the cluster ladder (rungs 1–4):"

present uv "Python deps + the demo scripts" \
	"https://docs.astral.sh/uv/  ·  curl -LsSf https://astral.sh/uv/install.sh | sh"

# Docker is special: installed-but-daemon-down is a common, confusing failure, so check both.
if command -v docker >/dev/null 2>&1; then
	if docker info >/dev/null 2>&1; then
		printf '  %s✓%s %-8s container runtime (daemon running)\n' "$GREEN" "$RESET" "docker"
	else
		printf '  %s✗%s %-8s installed but the daemon is NOT running — start Docker Desktop / dockerd\n' \
			"$RED" "$RESET" "docker"
		ok=0
	fi
else
	printf '  %s✗%s %-8s MISSING — https://docs.docker.com/get-docker/\n' "$RED" "$RESET" "docker"
	ok=0
fi

present kind "local Kubernetes (cluster runs v0.32)" \
	"https://kind.sigs.k8s.io/  ·  brew install kind"
present kubectl "talk to the cluster (v1.34)" \
	"https://kubernetes.io/docs/tasks/tools/  ·  brew install kubectl"
present argo "submit + watch workflows (v3.7)" \
	"https://github.com/argoproj/argo-workflows/releases  ·  brew install argo"

# Advisory only — jq makes the `curl … | jq` verify one-liners nicer but isn't required.
if command -v jq >/dev/null 2>&1; then
	printf '  %s✓%s %-8s (optional) pretty verify output\n' "$GREEN" "$RESET" "jq"
else
	printf '  %s~%s %-8s (optional) not found — the `curl … | jq` verify snippets want it (brew install jq)\n' \
		"$YELLOW" "$RESET" "jq"
fi

echo
if [ "$ok" -eq 1 ]; then
	echo "${GREEN}All required tools present.${RESET} Next: make up"
	exit 0
fi
echo "${RED}Missing required tools above.${RESET} The dev container / Codespace ships them all pinned —"
echo "see README → Prerequisites. Install what's missing, then re-run: make check"
exit 1
