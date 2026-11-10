"""Proves that each of the three implementations we have per composite kind
(Patch-and-Transform, a custom-packaged Python function, and an inline
function-python script) produce equivalent output, across the reconcile-pass
scenarios that actually differ (cold start, partially observed, fully
observed, and -- for StaticWebsite -- the no-custom-domain case that
currently triggers a known bug all three implementations faithfully
reproduce).

Requires function-iamrole:dev, function-dnsvalidatedcertificate:dev, and
function-staticwebsite:dev to already be built locally and loaded into the
Docker daemon `crossplane composition render` talks to -- see
.github/workflows/function-iamrole.yml's equivalence-test job, or build them
yourself:

    docker build functions/iamrole --tag function-iamrole:dev
    docker build functions/dnsvalidatedcertificate --tag function-dnsvalidatedcertificate:dev
    docker build functions/staticwebsite --tag function-staticwebsite:dev
"""

import json
import subprocess

import pytest
import yaml

IGNORE_METADATA_KEYS = {"name", "generateName", "uid", "ownerReferences", "labels", "resourceVersion"}


def _parse_json_strings(value):
    """Recursively replace any string that happens to be valid JSON with its
    parsed form, e.g. an IAM assumeRolePolicy or S3 bucket policy document.
    Two implementations can produce semantically identical JSON with
    different whitespace (json.dumps's default separators vs. a hand-written
    Patch-and-Transform format string) -- compare the parsed value, not the
    exact string."""
    if isinstance(value, dict):
        return {k: _parse_json_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_parse_json_strings(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return value
        return parsed if isinstance(parsed, (dict, list)) else value
    return value


def normalize(doc):
    """Strip the bits that legitimately differ between independent
    implementations (generated names, uids, JSON string formatting) so
    we're comparing the meaningful content, not incidental identifiers."""
    doc = dict(doc)
    if "metadata" in doc:
        doc["metadata"] = {k: v for k, v in doc["metadata"].items() if k not in IGNORE_METADATA_KEYS}
    if "status" in doc and isinstance(doc["status"], dict):
        doc["status"] = {k: v for k, v in doc["status"].items() if k != "conditions"}
    if "spec" in doc and isinstance(doc["spec"], dict) and "crossplane" in doc["spec"]:
        refs = doc["spec"]["crossplane"].get("resourceRefs", [])
        doc["spec"] = dict(doc["spec"])
        doc["spec"]["crossplane"] = {"resourceRefs": sorted((r["apiVersion"], r["kind"]) for r in refs)}
    return {k: _parse_json_strings(v) for k, v in doc.items()}


def render(xr_path, composition_path, function_path, observed_resources=None):
    cmd = ["crossplane", "composition", "render", xr_path, composition_path, function_path]
    if observed_resources:
        cmd.append(f"--observed-resources={observed_resources}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    docs = [normalize(d) for d in yaml.safe_load_all(result.stdout)]
    docs.sort(key=lambda d: (d.get("apiVersion", ""), d.get("kind", "")))
    return docs


def assert_all_equivalent(renders: dict):
    """renders maps a label (e.g. "patch-and-transform") to that
    implementation's rendered docs. Asserts they're all equal, and reports
    which labels disagree if not."""
    labels = list(renders)
    reference_label, reference = labels[0], renders[labels[0]]
    for label in labels[1:]:
        assert renders[label] == reference, f"{label} != {reference_label}"


PATCH_AND_TRANSFORM = "./manifests/crossplane-compositions/function-patch-and-transform.yaml"
FUNCTION_PYTHON = "./manifests/crossplane-compositions/function-python.yaml"
IAMROLE_FUNCTION = "./tests/fixtures/function-iamrole-dev.yaml"
DNS_CERT_PYTHON_FUNCTION = "./tests/fixtures/function-dnsvalidatedcertificate-python-dev.yaml"
STATICWEBSITE_PYTHON_FUNCTION = "./tests/fixtures/function-staticwebsite-python-dev.yaml"


@pytest.mark.parametrize(
    "xr,observed_resources",
    [
        ("manifests/laz-testing-crossplane/iam-role-example.yaml", None),
        (
            "manifests/laz-testing-crossplane/iam-role-example.yaml",
            "tests/fixtures/iamrole-observed.yaml",
        ),
    ],
    ids=["cold-start", "role-arn-observed"],
)
def test_iamrole_equivalence(xr, observed_resources):
    assert_all_equivalent(
        {
            "patch-and-transform": render(
                xr,
                "./manifests/crossplane-compositions/composition-iamrole-patch-and-transform.yaml",
                PATCH_AND_TRANSFORM,
                observed_resources,
            ),
            "custom-packaged": render(
                xr,
                "./manifests/crossplane-compositions/composition-iamrole.yaml",
                IAMROLE_FUNCTION,
                observed_resources,
            ),
            "inline-python": render(
                xr,
                "./manifests/crossplane-compositions/composition-iamrole-inline-python.yaml",
                FUNCTION_PYTHON,
                observed_resources,
            ),
        }
    )


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
    assert_all_equivalent(
        {
            "patch-and-transform": render(
                xr,
                "./manifests/crossplane-compositions/composition-dnsvalidatedcertificate.yaml",
                PATCH_AND_TRANSFORM,
                observed_resources,
            ),
            "custom-packaged": render(
                xr,
                "./manifests/crossplane-compositions/composition-dnsvalidatedcertificate-python.yaml",
                DNS_CERT_PYTHON_FUNCTION,
                observed_resources,
            ),
            "inline-python": render(
                xr,
                "./manifests/crossplane-compositions/composition-dnsvalidatedcertificate-inline-python.yaml",
                FUNCTION_PYTHON,
                observed_resources,
            ),
        }
    )


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
    assert_all_equivalent(
        {
            "patch-and-transform": render(
                xr,
                "./manifests/crossplane-compositions/composition-staticwebsite.yaml",
                PATCH_AND_TRANSFORM,
            ),
            "custom-packaged": render(
                xr,
                "./manifests/crossplane-compositions/composition-staticwebsite-python.yaml",
                STATICWEBSITE_PYTHON_FUNCTION,
            ),
            "inline-python": render(
                xr,
                "./manifests/crossplane-compositions/composition-staticwebsite-inline-python.yaml",
                FUNCTION_PYTHON,
            ),
        }
    )
