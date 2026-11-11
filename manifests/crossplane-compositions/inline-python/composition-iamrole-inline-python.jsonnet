// A third implementation of IAMRole, alongside Patch-and-Transform
// (../yaml-patching/composition-iamrole-yaml-patching.yaml) and the
// custom-packaged Python function (../custom-python/composition-iamrole-custom-python.yaml).
//
// The script lives in its own file (scripts/iamrole.py) and is spliced in with
// `importstr` at Argo CD sync time -- no manual YAML indentation, no
// generated ConfigMap byproduct (contrast with the Kustomize approach),
// since importstr produces a plain string value rather than text-templating
// a YAML block scalar. Argo CD auto-detects .jsonnet files in a directory
// source and evaluates them itself; no extra Application config needed.
{
  apiVersion: "apiextensions.crossplane.io/v1",
  kind: "Composition",
  metadata: {
    name: "iamrole-inline-python",
  },
  spec: {
    compositeTypeRef: {
      apiVersion: "platform.cia-infra-test.io/v1alpha1",
      kind: "IAMRole",
    },
    mode: "Pipeline",
    pipeline: [
      {
        step: "compose",
        functionRef: { name: "function-python" },
        input: {
          apiVersion: "python.fn.crossplane.io/v1beta1",
          kind: "Script",
          script: importstr "scripts/iamrole.py",
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
