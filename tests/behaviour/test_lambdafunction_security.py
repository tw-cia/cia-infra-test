"""Proves security-relevant and input-reflection properties of the rendered
LambdaFunction resources themselves, for every implementation -- not that
the implementations agree with each other (that's
tests/equivalence/test_equivalence.py), but that the delegated execution
role trusts nothing but Lambda, that a requested function URL can never be
publicly invocable, and that the baseline logging policy is always
attached regardless of spec.managedPolicyArns.

Shares tests/harness.py's render harness (same requirements -- see that
file's docstring).
"""

import pytest

from harness import METHODS, find_one, render_method

# Matches tests/fixtures/lambdafunction-xr-fully-observed.yaml -- the only
# scenario where Function and FunctionUrl both render (gated on
# status.roleArn / status.functionArn respectively).
FULLY_OBSERVED_XR = "tests/fixtures/lambdafunction-xr-fully-observed.yaml"
FULLY_OBSERVED_ROLE_ARN = "arn:aws:iam::123456789012:role/laz-lambda-example-role"

# Matches tests/fixtures/lambda-function-example.yaml -- exercises the
# managedPolicyArns fan-out at cold start (no gating involved).
COLD_START_XR = "tests/fixtures/lambda-function-example.yaml"

# Matches tests/fixtures/lambdafunction-xr-input-reflection.yaml -- values
# not shared with any other fixture, so a passing assertion proves the
# value flowed from spec to the rendered resource, not coincidence.
INPUT_REFLECTION_XR = "tests/fixtures/lambdafunction-xr-input-reflection.yaml"


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_role_trusts_only_lambda(method):
    """No spec field exists to set this to anything else -- this is the
    hardcoded secure default, not an override-resistance test."""
    docs = render_method(method, COLD_START_XR, "lambdafunction")
    role = find_one(docs, "IAMRole")
    assert role["spec"]["trustedService"] == "lambda.amazonaws.com"


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_role_always_includes_the_baseline_managed_policy(method):
    docs = render_method(method, COLD_START_XR, "lambdafunction")
    role = find_one(docs, "IAMRole")
    assert "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" in role["spec"]["managedPolicyArns"]


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_role_appends_extra_managed_policy_arns_to_the_baseline(method):
    # tests/fixtures/lambda-function-example.yaml requests one extra policy
    # beyond the baseline.
    docs = render_method(method, COLD_START_XR, "lambdafunction")
    role = find_one(docs, "IAMRole")
    assert "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess" in role["spec"]["managedPolicyArns"]


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_function_role_matches_the_delegated_role(method):
    """Not that the role exists with the right trust policy (the tests
    above), but that the Function actually uses *this* role's ARN, not a
    hardcoded or coincidentally-equal value."""
    docs = render_method(method, FULLY_OBSERVED_XR, "lambdafunction")
    function = find_one(docs, "Function")
    assert function["spec"]["forProvider"]["role"] == FULLY_OBSERVED_ROLE_ARN


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_function_url_omitted_by_default(method):
    """FunctionUrl isn't gated on anything role/function-arn-related alone
    -- even once both are known, it still shouldn't render unless
    explicitly requested."""
    docs = render_method(method, "tests/fixtures/lambdafunction-xr-role-known.yaml", "lambdafunction")
    assert not [d for d in docs if d.get("kind") == "FunctionUrl"]


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_function_url_auth_type_is_always_iam(method):
    """No spec field exists to set this to "NONE" -- this is the hardcoded
    secure default, not an override-resistance test."""
    docs = render_method(method, FULLY_OBSERVED_XR, "lambdafunction")
    function_url = find_one(docs, "FunctionUrl")
    assert function_url["spec"]["forProvider"]["authorizationType"] == "AWS_IAM"


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_function_url_targets_the_right_function(method):
    docs = render_method(method, FULLY_OBSERVED_XR, "lambdafunction")
    function = find_one(docs, "Function")
    function_name = function["metadata"]["annotations"]["crossplane.io/external-name"]

    function_url = find_one(docs, "FunctionUrl")
    assert function_url["spec"]["forProvider"]["functionName"] == function_name


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_reflects_function_name_runtime_and_handler(method):
    docs = render_method(method, INPUT_REFLECTION_XR, "lambdafunction")
    function = find_one(docs, "Function")
    assert function["metadata"]["annotations"]["crossplane.io/external-name"] == "reflection-test-function"
    assert function["spec"]["forProvider"]["runtime"] == "nodejs20.x"
    assert function["spec"]["forProvider"]["handler"] == "handler.main"


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_reflects_code_location(method):
    docs = render_method(method, INPUT_REFLECTION_XR, "lambdafunction")
    for_provider = find_one(docs, "Function")["spec"]["forProvider"]
    assert for_provider["s3Bucket"] == "reflection-test-artifacts"
    assert for_provider["s3Key"] == "reflection/function.zip"


@pytest.mark.parametrize("method", METHODS)
def test_lambdafunction_reflects_memory_timeout_and_environment_variables(method):
    docs = render_method(method, INPUT_REFLECTION_XR, "lambdafunction")
    for_provider = find_one(docs, "Function")["spec"]["forProvider"]
    assert for_provider["memorySize"] == 512
    assert for_provider["timeout"] == 30
    assert for_provider["environment"]["variables"] == {"STAGE": "reflection"}
