"""Proves security-relevant and input-reflection properties of the rendered
IAMRole resources themselves, for every implementation -- not that the
implementations agree with each other (that's
tests/equivalence/test_equivalence.py), but that the trust policy actually
restricts who can assume the role, and that every requested managed policy
is actually attached (not just the first one).

Shares tests/harness.py's render harness (same requirements -- see that
file's docstring).
"""

import pytest

from harness import METHODS, find_one, render_method

# Matches tests/fixtures/iam-role-example.yaml.
EXAMPLE_ROLE_NAME = "laz-lambda-example-role"
EXAMPLE_TRUSTED_SERVICE = "lambda.amazonaws.com"

# Matches tests/fixtures/iamrole-xr-multiple-policies.yaml -- deliberately
# distinct values (not shared with any other fixture) so a passing assertion
# proves these flowed from spec to the rendered resource, not coincidence.
MULTIPLE_POLICIES_XR = "tests/fixtures/iamrole-xr-multiple-policies.yaml"
MULTIPLE_POLICIES_ROLE_NAME = "reflection-test-role"
MULTIPLE_POLICIES_DESCRIPTION = "Role with more than one managed policy attached"
MULTIPLE_POLICIES_TRUSTED_SERVICE = "ec2.amazonaws.com"
MULTIPLE_POLICIES_ARNS = [
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonSNSReadOnlyAccess",
]


def find_all(docs: list[dict], kind: str) -> list[dict]:
    return [d for d in docs if d.get("kind") == kind]


@pytest.mark.parametrize("method", METHODS)
def test_iamrole_trust_policy_scoped_to_trusted_service(method):
    """The assume-role policy should trust nothing but spec.trustedService to
    assume this role -- one statement, one principal, sts:AssumeRole only.
    Not a wildcard principal, and not every service this repo happens to
    use elsewhere."""
    xr = "tests/fixtures/iam-role-example.yaml"
    docs = render_method(method, xr, "iamrole")

    role = find_one(docs, "Role")["spec"]["forProvider"]
    # normalize()'s _parse_json_strings already parsed this from a JSON
    # string into a dict, so this is the actual policy document, not text.
    document = role["assumeRolePolicy"]
    assert document["Version"] == "2012-10-17"
    assert len(document["Statement"]) == 1, "expected exactly one statement"

    statement = document["Statement"][0]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"Service": EXAMPLE_TRUSTED_SERVICE}, (
        "principal isn't scoped to the one trusted service"
    )
    assert statement["Action"] == "sts:AssumeRole"


@pytest.mark.parametrize("method", METHODS)
def test_iamrole_attaches_every_managed_policy_arn(method):
    """iam-role-example.yaml only ever exercises this fan-out at n=1, which
    can't distinguish "handles a list" from "handles exactly one element" --
    this fixture has two, so a passing assertion proves the loop, not a
    single hardcoded attachment."""
    docs = render_method(method, MULTIPLE_POLICIES_XR, "iamrole")

    attachments = find_all(docs, "RolePolicyAttachment")
    assert len(attachments) == len(MULTIPLE_POLICIES_ARNS), (
        f"expected one RolePolicyAttachment per managedPolicyArn, got {len(attachments)}"
    )

    attached_arns = {a["spec"]["forProvider"]["policyArn"] for a in attachments}
    assert attached_arns == set(MULTIPLE_POLICIES_ARNS)


@pytest.mark.parametrize("method", METHODS)
def test_iamrole_policy_attachments_target_the_right_role(method):
    """attaches_every_managed_policy_arn proves the right policies are
    attached -- this proves they're attached to *this* role, checked against
    the actual rendered Role, not a hardcoded constant."""
    docs = render_method(method, MULTIPLE_POLICIES_XR, "iamrole")

    role_name = find_one(docs, "Role")["metadata"]["annotations"]["crossplane.io/external-name"]

    attachments = find_all(docs, "RolePolicyAttachment")
    for attachment in attachments:
        assert attachment["spec"]["forProvider"]["role"] == role_name


@pytest.mark.parametrize("method", METHODS)
def test_iamrole_reflects_role_name_and_description(method):
    docs = render_method(method, MULTIPLE_POLICIES_XR, "iamrole")

    role = find_one(docs, "Role")
    assert role["metadata"]["annotations"]["crossplane.io/external-name"] == MULTIPLE_POLICIES_ROLE_NAME
    assert role["spec"]["forProvider"]["description"] == MULTIPLE_POLICIES_DESCRIPTION


@pytest.mark.parametrize("method", METHODS)
def test_iamrole_reflects_trusted_service(method):
    docs = render_method(method, MULTIPLE_POLICIES_XR, "iamrole")

    document = find_one(docs, "Role")["spec"]["forProvider"]["assumeRolePolicy"]
    assert document["Statement"][0]["Principal"] == {"Service": MULTIPLE_POLICIES_TRUSTED_SERVICE}
