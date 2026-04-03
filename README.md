# Runtime Catalog

This repo is the publication surface for `runwithrook/runtime-catalog`.

It exists to do one thing well:

- build deterministic runtime catalog JSON
- sign and attest it with Sigstore
- verify it locally before publish
- publish immutable release trees
- promote `canary` and `stable` into the mutable root state
- roll back root publication state without mutating immutable releases

The actual catalog mechanics live in the Rook CLI. This repo is the operator and CI wrapper around that CLI.

## Repo Files

- [runtime-catalog.json](runtime-catalog.json): source-of-truth catalog definition
- [runtime-trust-policy.json](runtime-trust-policy.json): local verify policy for source signatures and provenance
- [scripts/attest_catalog.py](scripts/attest_catalog.py): attest built catalog documents before publish
- [.github/workflows/validate.yaml](.github/workflows/validate.yaml): lightweight CI validation
- [.github/workflows/publish.yaml](.github/workflows/publish.yaml): publish/promote/rollback workflow

## Release Model

The workflow uses the release model already implemented in Rook:

- immutable releases under `releases/<release_id>/...`
- mutable root state at:
  - `runtime-channels.json`
  - `publication-snapshot.json`
  - `promotions.jsonl`

Recommended rollout posture:

- `canary` points at the newest release under evaluation
- `stable` points at the approved release for wider rollout
- when both point at the same release, rollout is aligned

## Default CI Behavior

The publish workflow uses one stable builder identity:

- `https://github.com/runwithrook/runtime-catalog/.github/workflows/publish.yaml@refs/heads/main`

That identity is what the sample trust policy expects for both signatures and provenance.

Default workflow behavior:

- push to `main`: build a new immutable release and promote it to `canary`
- manual dispatch `publish_canary`: same as above, with optional `promote_stable_now`
- manual dispatch `promote_stable`: move `stable` to an already-published release
- manual dispatch `rollback_previous`: restore the previous root publication version
- manual dispatch `rollback_to_version`: restore a specific historical root publication version

The workflow publishes the static files to the `gh-pages` branch.

## Current Bootstrap Assumption

Until the main Rook repo is moved under `runwithrook`, the workflows default to checking out:

- `andreidavid/rook`

You can override that in `workflow_dispatch` with:

- `rook_repository`
- `rook_ref`

Once the main repo moves, update the workflow default to `runwithrook/rook`.

## Before First Real Publish

Replace the placeholder data in [runtime-catalog.json](runtime-catalog.json):

- artifact digests
- artifact refs
- version ids
- manifest contents

Then confirm the local path works with:

```bash
PYTHONPATH=/path/to/rook/src python3 -m rook runtime catalog build --definition runtime-catalog.json --output-dir catalog
PYTHONPATH=/path/to/rook/src python3 -m rook runtime catalog sign --catalog-dir catalog
python3 scripts/attest_catalog.py --catalog-dir catalog --builder-identity "https://github.com/runwithrook/runtime-catalog/.github/workflows/publish.yaml@refs/heads/main" --source-repo "https://github.com/runwithrook/runtime-catalog" --source-ref "refs/heads/main"
ROOK_RUNTIME_TRUST_POLICY_PATH=runtime-trust-policy.json PYTHONPATH=/path/to/rook/src python3 -m rook runtime catalog verify-local --catalog-dir catalog
```

## Publish Outputs

The workflow uploads:

- the built `catalog/`
- the rendered `publication/`
- JSON operation reports for publish/promote/rollback/history

That makes it easier to inspect a failed run without reconstructing the state locally.
