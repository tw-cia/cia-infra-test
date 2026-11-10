// A fourth implementation of IAMRole, alongside Patch-and-Transform
// (composition-iamrole-patch-and-transform.yaml), the custom-packaged
// Python function (composition-iamrole.yaml), and the inline function-python
// script authored as plain YAML (composition-iamrole-inline-python.yaml).
//
// This one is the same inline function-python approach, but the script
// lives in its own file (scripts/iamrole.py) and is spliced in with
// `importstr` at Argo CD sync time -- no manual YAML indentation, no
// generated ConfigMap byproduct (contrast with the Kustomize approach),
// since importstr produces a plain string value rather than text-templating
// a YAML block scalar. Argo CD auto-detects .jsonnet files in a directory
// source and evaluates them itself; no extra Application config needed.
{
  apiVersion: "apiextensions.crossplane.io/v1",
  kind: "Composition",
  metadata: {
    name: "iamrole-jsonnet",
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
    ],
  },
}
