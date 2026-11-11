"""Composes a LambdaFunction: a Lambda Function, its execution role
(delegated to the IAMRole composite), and an optional FunctionUrl --
mirrors composition-lambdafunction-yaml-patching.yaml's Patch-and-Transform
logic resource-for-resource.

Function is gated on status.roleArn; FunctionUrl is gated on
spec.functionUrlEnabled AND status.functionArn. Both read this composite's
OWN persisted status (set by a prior pass below), not a live read of the
nested resource's observed status -- every other method has to share that
same multi-pass shape to stay equivalent (see
kcl-scripts/lambdafunction.k's header comment for why).
"""

from crossplane.function import resource
from google.protobuf.json_format import MessageToDict

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

# Always attached, regardless of spec.managedPolicyArns -- a LambdaFunction
# needs this to write its own logs, full stop.
BASELINE_MANAGED_POLICY_ARN = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"


def compose(req, rsp):
    xr = MessageToDict(req.observed.composite.resource)
    spec = xr.get("spec", {})
    status_in = xr.get("status", {})

    function_name = spec["functionName"]

    # role -- delegates to its own Composition. Hardcoded: nothing in
    # LambdaFunction's own spec can set trustedService to anything but the
    # one service this role is actually for.
    resource.update(
        rsp.desired.resources["role"],
        {
            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
            "kind": "IAMRole",
            "spec": {
                "roleName": f"{function_name}-role",
                "trustedService": "lambda.amazonaws.com",
                "managedPolicyArns": [BASELINE_MANAGED_POLICY_ARN, *spec.get("managedPolicyArns", [])],
            },
        },
    )

    status = {}
    if "role" in req.observed.resources:
        observed_role = MessageToDict(req.observed.resources["role"].resource)
        observed_role_arn = observed_role.get("status", {}).get("roleArn")
        if observed_role_arn:
            status["roleArn"] = observed_role_arn

    # function -- gated on status.roleArn, surfaced by a prior pass.
    role_arn = status_in.get("roleArn")
    if role_arn:
        for_provider = {
            "role": role_arn,
            "runtime": spec["runtime"],
            "handler": spec["handler"],
            "s3Bucket": spec["code"]["s3Bucket"],
            "s3Key": spec["code"]["s3Key"],
        }
        if "description" in spec:
            for_provider["description"] = spec["description"]
        if "memorySize" in spec:
            for_provider["memorySize"] = spec["memorySize"]
        if "timeoutSeconds" in spec:
            for_provider["timeout"] = spec["timeoutSeconds"]
        if "environmentVariables" in spec:
            for_provider["environment"] = {"variables": spec["environmentVariables"]}

        resource.update(
            rsp.desired.resources["function"],
            {
                "apiVersion": "lambda.aws.m.upbound.io/v1beta1",
                "kind": "Function",
                "metadata": {"annotations": {"crossplane.io/external-name": function_name}},
                "spec": {"forProvider": for_provider, "providerConfigRef": PROVIDER_CONFIG},
            },
        )

        if "function" in req.observed.resources:
            observed_function = MessageToDict(req.observed.resources["function"].resource)
            observed_function_arn = observed_function.get("status", {}).get("atProvider", {}).get("arn")
            if observed_function_arn:
                status["functionArn"] = observed_function_arn

    # function-url -- gated on spec.functionUrlEnabled AND
    # status.functionArn. Hardcoded: nothing in LambdaFunction's own spec
    # can set authorizationType to "NONE" -- a public invoke URL isn't an
    # option.
    function_arn = status_in.get("functionArn")
    if spec.get("functionUrlEnabled") and function_arn:
        resource.update(
            rsp.desired.resources["function-url"],
            {
                "apiVersion": "lambda.aws.m.upbound.io/v1beta1",
                "kind": "FunctionUrl",
                "spec": {
                    "forProvider": {
                        "functionName": function_name,
                        "authorizationType": "AWS_IAM",
                    },
                    "providerConfigRef": PROVIDER_CONFIG,
                },
            },
        )

        if "function-url" in req.observed.resources:
            observed_function_url = MessageToDict(req.observed.resources["function-url"].resource)
            observed_url = observed_function_url.get("status", {}).get("atProvider", {}).get("functionUrl")
            if observed_url:
                status["functionUrl"] = observed_url

    if status:
        rsp.desired.composite.resource.update({"status": status})
