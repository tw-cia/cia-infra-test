# kcl test ./... -- written before kcl-scripts/lambdafunction.k exists (TDD).
# Mirrors the level of coverage in staticwebsite_test.k and iamrole_test.k:
# cold start, the IAMRole-ARN-known gate, the Function-ARN-known gate,
# input reflection, the hardcoded-secure-defaults that have no spec field at
# all (trustedService, the baseline managed policy, FunctionUrl's authType),
# and the managedPolicyArns fan-out passed down to the nested IAMRole XR.
import lambdafunction

lfByName = lambda items: [{str:any}] -> {str:{str:any}} {
    {item["metadata"]["annotations"]["krm.kcl.dev/composition-resource-name"]: item for item in items if "metadata" in item}
}

lfComposite = lambda items: [{str:any}] -> {str:any} {
    [item for item in items if not ("metadata" in item)][0]
}

BASE_SPEC = {
    "functionName": "laz-lambda-example"
    "runtime": "python3.12"
    "handler": "index.handler"
    "code": {"s3Bucket": "laz-lambda-artifacts", "s3Key": "example/function.zip"}
}

lfOxr = lambda spec: {str:any}, status: {str:any} -> {str:any} {
    {"spec": spec, "status": status}
}

test_composes_only_the_role_on_cold_start = lambda {
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, {}), {})
    byName = lfByName(items)
    assert sorted([k for k in byName]) == ["role"]
}

test_role_trusts_only_lambda_regardless_of_input = lambda {
    # No spec field exists to set this to anything else -- this is the
    # hardcoded secure default, not an override-resistance test.
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, {}), {})
    role = lfByName(items)["role"]
    assert role.kind == "IAMRole"
    assert role.spec.trustedService == "lambda.amazonaws.com"
}

test_role_always_includes_the_baseline_managed_policy = lambda {
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, {}), {})
    role = lfByName(items)["role"]
    assert "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" in role.spec.managedPolicyArns
}

test_role_appends_extra_managed_policy_arns_to_the_baseline = lambda {
    spec = {**BASE_SPEC, "managedPolicyArns": ["arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"]}
    items = lambdafunction.composeLambdaFunction(lfOxr(spec, {}), {})
    role = lfByName(items)["role"]
    assert "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" in role.spec.managedPolicyArns
    assert "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess" in role.spec.managedPolicyArns
}

test_omits_function_when_role_arn_not_yet_known = lambda {
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, {}), {})
    byName = lfByName(items)
    assert not ("function" in byName)
}

test_composes_function_once_role_arn_known = lambda {
    # Gated on the composite's OWN persisted status.roleArn (set by a prior
    # pass from ocds), not a live same-pass ocds read -- Patch-and-Transform
    # has no way to read another resource's observed status directly, only
    # by round-tripping it through the composite's own status first, so
    # every method has to agree on that same multi-pass shape.
    status = {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role"}
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, status), {})
    byName = lfByName(items)

    function = byName["function"]
    assert function.kind == "Function"
    assert function.metadata.annotations["crossplane.io/external-name"] == "laz-lambda-example"
    assert function.spec.forProvider.role == "arn:aws:iam::123456789012:role/laz-lambda-example-role"
    assert function.spec.forProvider.runtime == "python3.12"
    assert function.spec.forProvider.handler == "index.handler"
    assert function.spec.forProvider.s3Bucket == "laz-lambda-artifacts"
    assert function.spec.forProvider.s3Key == "example/function.zip"
}

test_surfaces_role_arn_in_own_status_once_known = lambda {
    ocds = {"role": {"Resource": {"status": {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role"}}}}
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, {}), ocds)
    composite = lfComposite(items)
    assert composite.status.roleArn == "arn:aws:iam::123456789012:role/laz-lambda-example-role"
}

test_surfaces_function_arn_once_observed = lambda {
    status = {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role"}
    ocds = {
        "role": {"Resource": {"status": {"roleArn": status.roleArn}}}
        "function": {"Resource": {"status": {"atProvider": {"arn": "arn:aws:lambda:us-east-1:123456789012:function:laz-lambda-example"}}}}
    }
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, status), ocds)
    composite = lfComposite(items)
    assert composite.status.functionArn == "arn:aws:lambda:us-east-1:123456789012:function:laz-lambda-example"
}

test_omits_function_url_by_default_even_once_function_arn_known = lambda {
    status = {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role", "functionArn": "arn:aws:lambda:us-east-1:123456789012:function:laz-lambda-example"}
    ocds = {
        "role": {"Resource": {"status": {"roleArn": status.roleArn}}}
        "function": {"Resource": {"status": {"atProvider": {"arn": status.functionArn}}}}
    }
    items = lambdafunction.composeLambdaFunction(lfOxr(BASE_SPEC, status), ocds)
    byName = lfByName(items)
    assert not ("function-url" in byName)
}

test_omits_function_url_when_requested_but_function_arn_not_yet_known = lambda {
    spec = {**BASE_SPEC, "functionUrlEnabled": True}
    items = lambdafunction.composeLambdaFunction(lfOxr(spec, {}), {})
    byName = lfByName(items)
    assert not ("function-url" in byName)
}

test_function_url_auth_type_is_always_iam_when_enabled = lambda {
    # No spec field exists to set this to "NONE" -- this is the hardcoded
    # secure default, not an override-resistance test.
    spec = {**BASE_SPEC, "functionUrlEnabled": True}
    status = {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role", "functionArn": "arn:aws:lambda:us-east-1:123456789012:function:laz-lambda-example"}
    ocds = {
        "role": {"Resource": {"status": {"roleArn": status.roleArn}}}
        "function": {"Resource": {"status": {"atProvider": {"arn": status.functionArn}}}}
    }
    items = lambdafunction.composeLambdaFunction(lfOxr(spec, status), ocds)
    functionUrl = lfByName(items)["function-url"]
    assert functionUrl.kind == "FunctionUrl"
    assert functionUrl.spec.forProvider.authorizationType == "AWS_IAM"
    assert functionUrl.spec.forProvider.functionName == "laz-lambda-example"
}

test_surfaces_function_url_once_observed = lambda {
    status = {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role", "functionArn": "arn:aws:lambda:us-east-1:123456789012:function:laz-lambda-example"}
    ocds = {
        "role": {"Resource": {"status": {"roleArn": status.roleArn}}}
        "function": {"Resource": {"status": {"atProvider": {"arn": status.functionArn}}}}
        "function-url": {"Resource": {"status": {"atProvider": {"functionUrl": "https://abc123.lambda-url.us-east-1.on.aws/"}}}}
    }
    spec = {**BASE_SPEC, "functionUrlEnabled": True}
    items = lambdafunction.composeLambdaFunction(lfOxr(spec, status), ocds)
    composite = lfComposite(items)
    assert composite.status.functionUrl == "https://abc123.lambda-url.us-east-1.on.aws/"
}

test_reflects_memory_timeout_description_and_environment_variables = lambda {
    spec = {
        **BASE_SPEC
        "description": "Example function"
        "memorySize": 256
        "timeoutSeconds": 15
        "environmentVariables": {"LOG_LEVEL": "debug"}
    }
    status = {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role"}
    items = lambdafunction.composeLambdaFunction(lfOxr(spec, status), {})
    forProvider = lfByName(items)["function"].spec.forProvider
    assert forProvider.description == "Example function"
    assert forProvider.memorySize == 256
    assert forProvider.timeout == 15
    assert forProvider.environment.variables == {"LOG_LEVEL": "debug"}
}
