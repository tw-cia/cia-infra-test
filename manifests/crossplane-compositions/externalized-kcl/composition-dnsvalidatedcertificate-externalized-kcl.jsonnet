// A sixth implementation of DnsValidatedCertificate -- see
// composition-staticwebsite-externalized-kcl.jsonnet for the externalization
// approach (KCL logic lives in ../../../kcl-scripts/dnsvalidatedcertificate.k
// as a pure, `kcl test`-able composeCertificate(oxr, ocds) lambda; this file
// just importstr's it and appends the option()-reading glue line).
{
  apiVersion: "apiextensions.crossplane.io/v1",
  kind: "Composition",
  metadata: {
    name: "dnsvalidatedcertificate-externalized-kcl",
    labels: { method: "externalized-kcl" },
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
        functionRef: { name: "function-kcl" },
        input: {
          apiVersion: "krm.kcl.dev/v1alpha1",
          kind: "KCLInput",
          spec: {
            source: (importstr "../../../kcl-scripts/dnsvalidatedcertificate.k")
              + "\nitems = composeCertificate(option(\"params\").oxr, option(\"params\").ocds)\n",
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
