# Dev container for the eo-ladder — everything to run the WHOLE ladder locally (rungs 0–4):
# uv, kind, kubectl, argo (Docker-in-Docker comes from the devcontainer feature, see
# devcontainer.json). Tool versions are pinned to what the cluster actually runs (kind node /
# kubectl v1.34, Argo v3.7.4) so a Codespace behaves like a maintainer's laptop. The shipped
# *runtime* image (../Dockerfile) is digest-pinned; this dev image version-pins its CLIs.
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# uv — copied from the very same pinned image the runtime Dockerfile uses, so dev and the built
# image resolve dependencies with one identical uv.
COPY --from=ghcr.io/astral-sh/uv:0.5.18@sha256:e2101b9e627153b8fe4e8a1249cc4194f1b38ece7f28a5a9b8f958e3b560e69c /uv /uvx /usr/local/bin/

ARG KUBECTL_VERSION=v1.34.1
ARG KIND_VERSION=v0.32.0
ARG ARGO_VERSION=v3.7.4

# Pinned CLIs, architecture-aware (works on amd64 CI and arm64 Apple Silicon).
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    curl -fsSLo /usr/local/bin/kubectl \
        "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}/kubectl"; \
    curl -fsSLo /usr/local/bin/kind \
        "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${arch}"; \
    curl -fsSL \
        "https://github.com/argoproj/argo-workflows/releases/download/${ARGO_VERSION}/argo-linux-${arch}.gz" \
        | gunzip > /usr/local/bin/argo; \
    chmod +x /usr/local/bin/kubectl /usr/local/bin/kind /usr/local/bin/argo; \
    kubectl version --client; kind version; argo version
