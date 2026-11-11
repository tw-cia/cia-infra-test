"""Proves that each of the three implementations we have per composite kind
(yaml-patching, custom-python, inline-python) produce equivalent output,
across the reconcile-pass scenarios that actually differ (cold start,
partially observed, fully observed, and -- for StaticWebsite -- the
no-custom-domain case that currently triggers a known bug all
implementations faithfully reproduce).

Requires function-iamrole:dev, function-dnsvalidatedcertificate:dev, and
function-staticwebsite:dev to already be built locally and loaded into the
Docker daemon `crossplane composition render` talks to, and the `jsonnet`
CLI to be on PATH -- see .github/workflows/function-iamrole.yml's
equivalence-test job, or set this up yourself:

    docker build functions/iamrole --tag function-iamrole:dev
    docker build functions/dnsvalidatedcertificate --tag function-dnsvalidatedcertificate:dev
    docker build functions/staticwebsite --tag function-staticwebsite:dev
    brew install jsonnet  # or your platform's equivalent
"""

import json
import subprocess
import tempfile

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


def evaluate_jsonnet(jsonnet_path: str) -> str:
    """Evaluates a .jsonnet Composition the same way Argo CD's repo-server
    would, and writes the resulting JSON manifest to a temp file -- `render`
    needs an actual file path, not evaluated content in memory."""
    result = subprocess.run(["jsonnet", jsonnet_path], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(result.stdout)
        return f.name


def assert_all_equivalent(renders: dict):
    """renders maps a label (e.g. "yaml-patching") to that implementation's
    rendered docs. Asserts they're all equal, and reports which labels
    disagree if not."""
    labels = list(renders)
    reference_label, reference = labels[0], renders[labels[0]]
    for label in labels[1:]:
        assert renders[label] == reference, f"{label} != {reference_label}"


YAML_PATCHING = "./manifests/crossplane-compositions/yaml-patching"
INLINE_PYTHON = "./manifests/crossplane-compositions/inline-python"
CUSTOM_PYTHON = "./manifests/crossplane-compositions/custom-python"

# Patch-and-Transform doesn't need function-auto-ready -- it has built-in
# auto-ready detection. Every custom/inline-python implementation does, so
# their function fixture directories each bundle it alongside the
# implementation's own function.
PATCH_AND_TRANSFORM = f"{YAML_PATCHING}/function-patch-and-transform.yaml"
FUNCTION_PYTHON = "./tests/fixtures/functions-python"

# The one piece of per-kind mapping that's unavoidable: each custom-python
# kind is backed by its own dev-built image, so needs its own function
# fixture directory.
CUSTOM_PYTHON_FUNCTIONS = {
    "iamrole": "./tests/fixtures/functions-iamrole",
    "staticwebsite": "./tests/fixtures/functions-staticwebsite",
    "dnsvalidatedcertificate": "./tests/fixtures/functions-dnsvalidatedcertificate",
}


def composition_path(method_dir: str, kind: str, ext: str = "yaml") -> str:
    """Every Composition's filename is composition-<kind>-<method>.<ext>,
    where <method> is just the method directory's own name -- so this is
    the only place a kind needs to turn into a file path."""
    method = method_dir.rsplit("/", 1)[-1]
    return f"{method_dir}/composition-{kind}-{method}.{ext}"


def render_all_methods(xr: str, kind: str, observed_resources: str | None = None) -> dict:
    """Renders the same XR through all three method directories for the
    given composite kind. Feed straight into assert_all_equivalent."""
    return {
        "yaml-patching": render(
            xr, composition_path(YAML_PATCHING, kind), PATCH_AND_TRANSFORM, observed_resources
        ),
        "custom-python": render(
            xr, composition_path(CUSTOM_PYTHON, kind), CUSTOM_PYTHON_FUNCTIONS[kind], observed_resources
        ),
        "inline-python": render(
            xr,
            evaluate_jsonnet(composition_path(INLINE_PYTHON, kind, ext="jsonnet")),
            FUNCTION_PYTHON,
            observed_resources,
        ),
    }


@pytest.mark.parametrize(
    "xr,observed_resources",
    [
        ("tests/fixtures/iam-role-example.yaml", None),
        (
            "tests/fixtures/iam-role-example.yaml",
            "tests/fixtures/iamrole-observed.yaml",
        ),
    ],
    ids=["cold-start", "role-arn-observed"],
)
def test_iamrole_equivalence(xr, observed_resources):
    assert_all_equivalent(render_all_methods(xr, "iamrole", observed_resources))


@pytest.mark.parametrize(
    "xr,observed_resources",
    [
        ("tests/fixtures/dns-validated-certificate-example.yaml", None),
        (
            "tests/fixtures/dns-validated-certificate-example.yaml",
            "tests/fixtures/dns-validated-certificate-observed.yaml",
        ),
        ("tests/fixtures/dns-validated-certificate-xr-observed.yaml", None),
    ],
    ids=["cold-start", "first-observed", "status-already-recorded"],
)
def test_dns_validated_certificate_equivalence(xr, observed_resources):
    assert_all_equivalent(render_all_methods(xr, "dnsvalidatedcertificate", observed_resources))


@pytest.mark.parametrize(
    "xr",
    [
        "tests/fixtures/static-website-customdomain-example.yaml",
        "tests/fixtures/staticwebsite-xr-no-zone.yaml",
        "tests/fixtures/staticwebsite-xr-partial-observed.yaml",
        "tests/fixtures/staticwebsite-xr-fully-observed.yaml",
    ],
    ids=["cold-start", "no-custom-domain-bug", "certificate-not-yet-known", "fully-observed"],
)
def test_staticwebsite_equivalence(xr):
    assert_all_equivalent(render_all_methods(xr, "staticwebsite"))
