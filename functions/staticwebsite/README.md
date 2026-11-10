# function-staticwebsite

A Python Crossplane composition function that replicates
`manifests/crossplane-compositions/composition-staticwebsite.yaml` (a
Patch-and-Transform Composition) resource-for-resource, including its
known bug: `distribution`'s `viewerCertificate.acmCertificateArn` gate is
unconditional, so a `StaticWebsite` with no custom `zone` can never actually
get a `Distribution`. This is intentional for now -- the point of this
function is to prove equivalence with the YAML version before fixing it.
See `tests/test_render.py` at the repo root for the comparison.

```shell
uv run pytest
uv run python function/main.py --insecure --debug
docker build . --tag=runtime
crossplane xpkg build -f package --embed-runtime-image=runtime
```
