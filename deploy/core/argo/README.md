# Argo Workflows (core)

The workflow engine for the ladder. From rung 1 on, every stage is an Argo `Workflow` /
`CronWorkflow` running the **one ingester image** — Argo gives us retries, fan-out, and a UI to
watch it happen.

## What's installed

| File | Purpose |
|------|---------|
| `install.yaml` | Vendored upstream **namespace-install** (CRDs + `workflow-controller` + `argo-server`), pinned to **v3.7.4**, images by digest. |
| `rbac.yaml` | Least-privilege `argo-workflow` ServiceAccount that **workflow pods** run as. |
| `hello.yaml` | One-step smoke workflow proving the install works end-to-end. |

Everything lives in the single `eo` namespace, alongside MinIO and the STAC API, so workflows reach
them by short DNS (`http://minio:9000`, `http://stac-api`).

## Apply

`install.yaml` is vendored verbatim from upstream and carries **no `namespace:` fields**, so it must
be applied *into* `eo`:

```sh
kubectl apply -n eo -f deploy/core/argo/install.yaml   # controller + server + CRDs
kubectl apply -f       deploy/core/argo/rbac.yaml       # workflow SA (namespaced in-file)
kubectl -n eo rollout status deploy/workflow-controller deploy/argo-server
```

(`make up` will wire this in at T13.)

## Auth mode

The `argo-server` runs with **`--auth-mode=server`**: the UI and API act as the server's own
ServiceAccount, so there's **no login or token** behind a port-forward. This is deliberate and is
**for the local demo only** — it assumes the only way to reach the server is your own
`kubectl port-forward`. Do not expose this server on a network; for anything shared, switch to
`--auth-mode=client` (or SSO) and remove the flag's comment in `install.yaml`.

## Open the UI

The server serves **HTTPS** with a self-signed cert:

```sh
kubectl -n eo port-forward svc/argo-server 2746:2746
# then open https://localhost:2746  (accept the self-signed-cert warning)
```

## Least-privilege RBAC

Three distinct identities, each scoped to `eo` (Roles, never ClusterRoles):

- **`workflow-controller`** (SA `argo`) — schedules workflow pods, watches CRDs. Namespaced.
- **`argo-server`** (SA `argo-server`) — serves the UI/API. Namespaced.
- **`argo-workflow`** (this repo's `rbac.yaml`) — what **workflow pods** run as. Its entire
  permission set is `create`/`patch` on `workflowtaskresults` (how a step reports its result to the
  controller). Nothing else.

Prove the workflow SA is not over-privileged:

```sh
kubectl auth can-i --as=system:serviceaccount:eo:argo-workflow -n eo create workflowtaskresults  # yes
kubectl auth can-i --as=system:serviceaccount:eo:argo-workflow -n eo '*' '*'                      # no
kubectl auth can-i --as=system:serviceaccount:eo:argo-workflow create secrets -n eo               # no
```

## Smoke test

```sh
argo submit -n eo --watch deploy/core/argo/hello.yaml
# phase should reach Succeeded; logs print "hello from the eo ladder — argo is live"
```

## Re-vendoring `install.yaml`

To bump versions, re-download the upstream asset and re-apply the local deltas (header, two image
digests, the `--auth-mode=server` arg) so the diff stays a clean, reviewable patch:

```sh
curl -fsSL -o deploy/core/argo/install.yaml \
  https://github.com/argoproj/argo-workflows/releases/download/vX.Y.Z/namespace-install.yaml
```
