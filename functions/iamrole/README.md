# function-iamrole

A [Crossplane composition function][functions], built from
[function-template-python][template], that composes an `IAMRole` XR into an
AWS IAM `Role` plus one `RolePolicyAttachment` per entry in
`spec.managedPolicyArns`.

This replaces the inline `function-python` script previously embedded in
`manifests/crossplane-compositions/custom-python/composition-iamrole-custom-python.yaml`
-- the same logic now lives here as a standalone, testable, reusable
Function package.

```shell
# Run unit tests - see tests/test_fn.py
uv run pytest

# Run the code in development mode, for `crossplane beta render`
uv run python function/main.py --insecure --debug

# Build the function's runtime image - see Dockerfile
docker build . --tag=runtime

# Build a function package - see package/crossplane.yaml
crossplane xpkg build -f package --embed-runtime-image=runtime
```

After building, push the resulting `.xpkg` (or the runtime image, if
pushing separately) to a registry, and point
`manifests/crossplane-compositions/custom-python/function-iamrole.yaml`'s `spec.package`
at it.

[functions]: https://docs.crossplane.io/latest/concepts/composition-functions
[template]: https://github.com/crossplane/function-template-python
