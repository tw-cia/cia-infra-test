// LambdaFunction, externalized-kcl only for now -- see
// composition-staticwebsite-externalized-kcl.jsonnet for the externalization
// approach (KCL logic lives in ../../../kcl-scripts/lambdafunction.k as a
// pure, `kcl test`-able composeLambdaFunction(oxr, ocds) lambda; this file
// just importstr's it and appends the option()-reading glue line).
//
// Delegates to the IAMRole composite for its execution role -- the same
// nested-XR pattern StaticWebsite uses for DnsValidatedCertificate.
{
  apiVersion: "apiextensions.crossplane.io/v1",
  kind: "Composition",
  metadata: {
    name: "lambdafunction-externalized-kcl",
    labels: { method: "externalized-kcl" },
  },
  spec: {
    compositeTypeRef: {
      apiVersion: "platform.cia-infra-test.io/v1alpha1",
      kind: "LambdaFunction",
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
            source: (importstr "../../../kcl-scripts/lambdafunction.k")
              + "\nitems = composeLambdaFunction(option(\"params\").oxr, option(\"params\").ocds)\n",
          },
        },
      },
      {
        step: "auto-ready",
        functionRef: { name: "function-auto-ready" },
      },
    ],
  },
}
