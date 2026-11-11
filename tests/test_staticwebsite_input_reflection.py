"""Proves that specific spec fields actually reach the specific output
fields they're supposed to, for every implementation -- not that the five
methods agree with each other (test_equivalence.py), and not that a fixed
set of outputs is secure (test_staticwebsite_security.py), but that
ever-changing input to this specific resource field actually happens. If all
five methods shared the same bug (e.g. silently ignoring spec.indexDocument
and hardcoding "index.html"), neither of those other test files would catch
it -- they'd all agree with each other on the wrong, but self-consistent and
secure, output.

tests/fixtures/staticwebsite-xr-input-reflection.yaml uses values not shared
with any other fixture, so a passing assertion here can't be coincidence.

Shares test_equivalence.py's render harness (same requirements -- see that
file's docstring).
"""

import pytest

from test_equivalence import METHODS, find_one, render_method

XR = "tests/fixtures/staticwebsite-xr-input-reflection.yaml"


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_bucket_reflects_name_and_region(method):
    docs = render_method(method, XR, "staticwebsite")
    bucket = find_one(docs, "Bucket")
    assert bucket["metadata"]["annotations"]["crossplane.io/external-name"] == "reflection-test-bucket"
    assert bucket["spec"]["forProvider"]["region"] == "eu-west-2"


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_distribution_reflects_index_document(method):
    docs = render_method(method, XR, "staticwebsite")
    distribution = find_one(docs, "Distribution")["spec"]["forProvider"]
    assert distribution["defaultRootObject"] == "home.html"


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_distribution_reflects_custom_domain_alias(method):
    docs = render_method(method, XR, "staticwebsite")
    distribution = find_one(docs, "Distribution")["spec"]["forProvider"]
    assert distribution["aliases"] == ["reflection.example.com"]
