# Argo Workflows (core)

The workflow engine for the ladder: from rung 1 on, every stage is an Argo `Workflow` /
`CronWorkflow` running the one ingester image.

## What's installed

| File | Purpose |
|------|---------|
| `install.yaml` | Vendored upstream namespace-install (CRDs + `workflow-controller` + `argo-server`), pinned to v4.0.6, images by digest. |
| `rbac.yaml` | Least-privilege `argo-workflow` ServiceAccount that workflow pods run as. |
| `hello.yaml` | One-step smoke workflow proving the install works end-to-end. |

Everything lives in the single `eo` namespace, alongside MinIO and the STAC API, so workflows reach
them by short DNS (`http://minio:9000`, `http://stac-api`).

## Apply

`install.yaml` is vendored verbatim from upstream and carries no `namespace:` fields, so it must
be applied *into* `eo`. `--server-side` is required: the v4 CRDs exceed the client-side annotation
size limit. (`make up` runs all of this.)

```sh
kubectl apply --server-side -n eo -f deploy/core/argo/install.yaml
kubectl apply -f deploy/core/argo/rbac.yaml
kubectl -n eo rollout status deploy/workflow-controller deploy/argo-server
```

## Auth mode

The `argo-server` runs with `--auth-mode=server`: the UI and API act as the server's own
ServiceAccount, so there is no login or token behind a port-forward. This is for the local demo
only — it assumes the only way to reach the server is your own `kubectl port-forward`. Do not
expose this server on a network; for anything shared, switch to `--auth-mode=client` (or SSO).

## Open the UI

The server runs with `--secure=false`, so it serves plain HTTP behind the local port-forward:

```sh
kubectl -n eo port-forward svc/argo-server 2746:2746
# then open http://localhost:2746  (no login — auth-mode=server)
```

## Least-privilege RBAC

Three distinct identities, each scoped to `eo` (Roles, never ClusterRoles):

- `workflow-controller` (SA `argo`) — schedules workflow pods, watches CRDs.
- `argo-server` (SA `argo-server`) — serves the UI/API.
- `argo-workflow` (this repo's `rbac.yaml`) — what workflow pods run as. Its entire permission
  set is `create`/`patch` on `workflowtaskresults` (how a step reports its result to the
  controller).

Prove the workflow SA is not over-privileged:

```sh
kubectl auth can-i --as=system:serviceaccount:eo:argo-workflow -n eo create workflowtaskresults  # yes
kubectl auth can-i --as=system:serviceaccount:eo:argo-workflow -n eo '*' '*'                      # no
kubectl auth can-i --as=system:serviceaccount:eo:argo-workflow create secrets -n eo               # no
```

## Smoke test

```sh
argo submit -n eo --watch deploy/core/argo/hello.yaml
# phase should reach Succeeded
```

## Re-vendoring `install.yaml`

To bump versions, re-download the upstream asset and re-apply the local deltas (header, two image
digests, `--auth-mode=server`, `--secure=false`) so the diff stays a clean, reviewable patch:

```sh
curl -fsSL -o deploy/core/argo/install.yaml \
  https://github.com/argoproj/argo-workflows/releases/download/vX.Y.Z/namespace-install.yaml
```
