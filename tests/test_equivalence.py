"""Proves the Python-function Compositions (functions/dnsvalidatedcertificate,
functions/staticwebsite) produce output equivalent to their Patch-and-Transform
originals, across the reconcile-pass scenarios that actually differ (cold
start, partially observed, fully observed, and -- for StaticWebsite -- the
no-custom-domain case that currently triggers a known bug both
implementations faithfully reproduce).

Requires function-dnsvalidatedcertificate:dev and function-staticwebsite:dev
to already be built locally and loaded into the Docker daemon `crossplane
composition render` talks to -- see .github/workflows/function-iamrole.yml's
equivalence-test job, or build them yourself:

    docker build functions/dnsvalidatedcertificate --tag function-dnsvalidatedcertificate:dev
    docker build functions/staticwebsite --tag function-staticwebsite:dev
"""

import subprocess

import pytest
import yaml

IGNORE_METADATA_KEYS = {"name", "generateName", "uid", "ownerReferences", "labels", "resourceVersion"}


def normalize(doc):
    """Strip the bits that legitimately differ between two independent
    implementations (generated names, uids) so we're comparing the
    meaningful content, not incidental identifiers."""
    doc = dict(doc)
    if "metadata" in doc:
        doc["metadata"] = {k: v for k, v in doc["metadata"].items() if k not in IGNORE_METADATA_KEYS}
    if "status" in doc and isinstance(doc["status"], dict):
        doc["status"] = {k: v for k, v in doc["status"].items() if k != "conditions"}
    if "spec" in doc and isinstance(doc["spec"], dict) and "crossplane" in doc["spec"]:
        refs = doc["spec"]["crossplane"].get("resourceRefs", [])
        doc["spec"] = dict(doc["spec"])
        doc["spec"]["crossplane"] = {"resourceRefs": sorted((r["apiVersion"], r["kind"]) for r in refs)}
    return doc


def render(xr_path, composition_path, function_path, observed_resources=None):
    cmd = ["crossplane", "composition", "render", xr_path, composition_path, function_path]
    if observed_resources:
        cmd.append(f"--observed-resources={observed_resources}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    docs = [normalize(d) for d in yaml.safe_load_all(result.stdout)]
    docs.sort(key=lambda d: (d.get("apiVersion", ""), d.get("kind", "")))
    return docs


PATCH_AND_TRANSFORM = "./manifests/crossplane-compositions/function-patch-and-transform.yaml"
DNS_CERT_PYTHON_FUNCTION = "./tests/fixtures/function-dnsvalidatedcertificate-python-dev.yaml"
STATICWEBSITE_PYTHON_FUNCTION = "./tests/fixtures/function-staticwebsite-python-dev.yaml"


@pytest.mark.parametrize(
    "xr,observed_resources",
    [
        ("manifests/laz-testing-crossplane/dns-validated-certificate-example.yaml", None),
        (
            "manifests/laz-testing-crossplane/dns-validated-certificate-example.yaml",
            "tests/fixtures/dns-validated-certificate-observed.yaml",
        ),
        ("tests/fixtures/dns-validated-certificate-xr-observed.yaml", None),
    ],
    ids=["cold-start", "first-observed", "status-already-recorded"],
)
def test_dns_validated_certificate_equivalence(xr, observed_resources):
    yaml_docs = render(
        xr,
        "./manifests/crossplane-compositions/composition-dnsvalidatedcertificate.yaml",
        PATCH_AND_TRANSFORM,
        observed_resources,
    )
    python_docs = render(
        xr,
        "./manifests/crossplane-compositions/composition-dnsvalidatedcertificate-python.yaml",
        DNS_CERT_PYTHON_FUNCTION,
        observed_resources,
    )

    assert yaml_docs == python_docs


@pytest.mark.parametrize(
    "xr",
    [
        "manifests/laz-testing-crossplane/static-website-customdomain-example.yaml",
        "tests/fixtures/staticwebsite-xr-no-zone.yaml",
        "tests/fixtures/staticwebsite-xr-partial-observed.yaml",
        "tests/fixtures/staticwebsite-xr-fully-observed.yaml",
    ],
    ids=["cold-start", "no-custom-domain-bug", "certificate-not-yet-known", "fully-observed"],
)
def test_staticwebsite_equivalence(xr):
    yaml_docs = render(
        xr,
        "./manifests/crossplane-compositions/composition-staticwebsite.yaml",
        PATCH_AND_TRANSFORM,
    )
    python_docs = render(
        xr,
        "./manifests/crossplane-compositions/composition-staticwebsite-python.yaml",
        STATICWEBSITE_PYTHON_FUNCTION,
    )

    assert yaml_docs == python_docs
