// A fourth implementation of DnsValidatedCertificate -- see
// composition-iamrole-jsonnet.jsonnet for why this approach (vs. Helm or
// Kustomize) for inlining the script.
{
  apiVersion: "apiextensions.crossplane.io/v1",
  kind: "Composition",
  metadata: {
    name: "dnsvalidatedcertificate-jsonnet",
  },
  spec: {
    compositeTypeRef: {
      apiVersion: "platform.cia-infra-test.io/v1alpha1",
      kind: "DnsValidatedCertificate",
    },
    mode: "Pipeline",
    pipeline: [
      {
        step: "compose",
        functionRef: { name: "function-python" },
        input: {
          apiVersion: "python.fn.crossplane.io/v1beta1",
          kind: "Script",
          script: importstr "scripts/dnsvalidatedcertificate.py",
        },
      },
    ],
  },
}
