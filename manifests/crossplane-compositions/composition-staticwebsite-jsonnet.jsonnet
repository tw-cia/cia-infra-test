// A fourth implementation of StaticWebsite -- see
// composition-iamrole-jsonnet.jsonnet for why this approach (vs. Helm or
// Kustomize) for inlining the script.
{
  apiVersion: "apiextensions.crossplane.io/v1",
  kind: "Composition",
  metadata: {
    name: "staticwebsite-jsonnet",
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
        functionRef: { name: "function-python" },
        input: {
          apiVersion: "python.fn.crossplane.io/v1beta1",
          kind: "Script",
          script: importstr "scripts/staticwebsite.py",
        },
      },
    ],
  },
}
