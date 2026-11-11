# function-lambdafunction

A [Crossplane composition function][functions], built from
[function-template-python][template], that composes a `LambdaFunction` XR
into an AWS Lambda `Function`, a delegated `IAMRole` composite for its
execution role, and an optional `FunctionUrl`.

See `tests/behaviour/test_lambdafunction_security.py` at the repo root for
the render-based cross-method behaviour/security checks this logic has to
satisfy.

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
`manifests/crossplane-compositions/custom-python/function-lambdafunction.yaml`'s
`spec.package` at it.

[functions]: https://docs.crossplane.io/latest/concepts/composition-functions
[template]: https://github.com/crossplane/function-template-python
