"""Proves that each of the six implementations we have per composite kind
(yaml-patching, custom-python, inline-python, go-templating, kcl,
externalized-kcl) produce equivalent output, across the reconcile-pass
scenarios that actually differ (cold start, partially observed, fully
observed, and -- for StaticWebsite -- the no-custom-domain case that
currently triggers a known bug all implementations faithfully reproduce).

Not that any one of them is correct or secure in isolation -- see
tests/behaviour/ for that. Shares tests/harness.py's render harness (see
that file's docstring for setup requirements).
"""

import pytest

from harness import assert_all_equivalent, render_all_methods


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


@pytest.mark.parametrize(
    "xr",
    [
        "tests/fixtures/lambda-function-example.yaml",
        "tests/fixtures/lambdafunction-xr-role-known.yaml",
        "tests/fixtures/lambdafunction-xr-fully-observed.yaml",
    ],
    ids=["cold-start", "role-arn-known", "fully-observed"],
)
def test_lambdafunction_equivalence(xr):
    assert_all_equivalent(render_all_methods(xr, "lambdafunction"))
