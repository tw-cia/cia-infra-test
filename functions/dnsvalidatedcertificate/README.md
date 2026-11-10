# function-dnsvalidatedcertificate

A Python Crossplane composition function that replicates
`manifests/crossplane-compositions/composition-dnsvalidatedcertificate.yaml`
(a Patch-and-Transform Composition) resource-for-resource: a DNS-validated
ACM `Certificate`, the Route53 `Record` ACM asks for, and the
`CertificateValidation` that waits for AWS to confirm it.

Built to test equivalence between the two approaches -- see
`tests/test_render.py` at the repo root for the comparison.

```shell
uv run pytest
uv run python function/main.py --insecure --debug
docker build . --tag=runtime
crossplane xpkg build -f package --embed-runtime-image=runtime
```
