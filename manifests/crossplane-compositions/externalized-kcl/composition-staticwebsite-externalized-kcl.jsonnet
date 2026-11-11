// A sixth implementation of StaticWebsite -- same business logic as
// ../kcl/composition-staticwebsite-kcl.yaml, but the KCL itself lives in
// ../../../kcl-scripts/staticwebsite.k as a pure, `kcl test`-able
// composeStaticWebsite(oxr, ocds) lambda (see that file's header comment for
// why it must not call option(...) directly). This mirrors how
// composition-staticwebsite-inline-python.jsonnet externalizes
// scripts/staticwebsite.py, except KCL's function-kcl runtime expects a bare
// top-level `items` variable rather than a callable entry point, so a short
// glue line assigning `items` has to be appended after the importstr -- that
// line is deliberately kept out of staticwebsite.k itself.
{
  apiVersion: "apiextensions.crossplane.io/v1",
  kind: "Composition",
  metadata: {
    name: "staticwebsite-externalized-kcl",
    labels: { method: "externalized-kcl" },
  },
  spec: {
    compositeTypeRef: {
      apiVersion: "platform.cia-infra-test.io/v1alpha1",
      kind: "StaticWebsite",
    },
    mode: "Pipeline",
    pipeline: [
      {
        step: "compose",
        functionRef: { name: "function-kcl" },
        input: {
          apiVersion: "krm.kcl.dev/v1alpha1",
          kind: "KCLInput",
          spec: {
            source: (importstr "../../../kcl-scripts/staticwebsite.k")
              + "\nitems = composeStaticWebsite(option(\"params\").oxr, option(\"params\").ocds)\n",
          },
        },
      },
      // See function-auto-ready.yaml -- without this, this Composition's
      // resources never get marked Ready regardless of their real AWS state.
      {
        step: "auto-ready",
        functionRef: { name: "function-auto-ready" },
      },
    ],
  },
}
