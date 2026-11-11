"""Behaviour and cross-functional-requirement tests for the custom-packaged
lambdafunction function, mirroring tests/behaviour/test_lambdafunction_security.py
(which exercises this same logic, and the other implementations, via
`crossplane composition render`). These run directly against fn.py instead
-- no Docker, no render -- so they double as a fast local feedback loop for
this one implementation.
"""

import unittest

from crossplane.function import logging, resource
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import json_format

from lambdafunction_function import fn

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

BASE_SPEC = {
    "functionName": "laz-lambda-example",
    "runtime": "python3.12",
    "handler": "index.handler",
    "code": {"s3Bucket": "laz-lambda-artifacts", "s3Key": "example/function.zip"},
}

ROLE_KNOWN_STATUS = {"roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role"}

FULLY_OBSERVED_STATUS = {
    "roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role",
    "functionArn": "arn:aws:lambda:us-east-1:123456789012:function:laz-lambda-example",
}


def make_request(spec: dict, status: dict | None = None) -> fnv1.RunFunctionRequest:
    xr = {
        "apiVersion": "platform.cia-infra-test.io/v1alpha1",
        "kind": "LambdaFunction",
        "spec": spec,
    }
    if status:
        xr["status"] = status
    return fnv1.RunFunctionRequest(
        observed=fnv1.State(composite=fnv1.Resource(resource=resource.dict_to_struct(xr))),
    )


class TestFunctionRunner(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.maxDiff = 4000
        logging.configure(level=logging.Level.DISABLED)

    async def run_function(self, req: fnv1.RunFunctionRequest) -> dict:
        got = await fn.FunctionRunner().RunFunction(req, None)
        return json_format.MessageToDict(got)

    async def test_composes_only_the_role_on_cold_start(self) -> None:
        got = await self.run_function(make_request(BASE_SPEC))
        self.assertEqual(set(got["desired"]["resources"]), {"role"})

    async def test_role_trusts_only_lambda_regardless_of_input(self) -> None:
        # No spec field exists to set this to anything else -- this is the
        # hardcoded secure default, not an override-resistance test.
        got = await self.run_function(make_request(BASE_SPEC))
        role = got["desired"]["resources"]["role"]["resource"]
        self.assertEqual(role["kind"], "IAMRole")
        self.assertEqual(role["spec"]["trustedService"], "lambda.amazonaws.com")

    async def test_role_always_includes_the_baseline_managed_policy(self) -> None:
        got = await self.run_function(make_request(BASE_SPEC))
        role = got["desired"]["resources"]["role"]["resource"]
        self.assertIn(
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            role["spec"]["managedPolicyArns"],
        )

    async def test_role_appends_extra_managed_policy_arns_to_the_baseline(self) -> None:
        spec = {**BASE_SPEC, "managedPolicyArns": ["arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"]}
        got = await self.run_function(make_request(spec))
        role = got["desired"]["resources"]["role"]["resource"]
        self.assertIn(
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            role["spec"]["managedPolicyArns"],
        )
        self.assertIn("arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess", role["spec"]["managedPolicyArns"])

    async def test_omits_function_when_role_arn_not_yet_known(self) -> None:
        got = await self.run_function(make_request(BASE_SPEC))
        self.assertNotIn("function", got["desired"]["resources"])

    async def test_composes_function_once_role_arn_known(self) -> None:
        got = await self.run_function(make_request(BASE_SPEC, ROLE_KNOWN_STATUS))
        function = got["desired"]["resources"]["function"]["resource"]
        self.assertEqual(function["kind"], "Function")
        self.assertEqual(function["metadata"]["annotations"]["crossplane.io/external-name"], "laz-lambda-example")
        self.assertEqual(function["spec"]["forProvider"]["role"], ROLE_KNOWN_STATUS["roleArn"])
        self.assertEqual(function["spec"]["forProvider"]["runtime"], "python3.12")
        self.assertEqual(function["spec"]["forProvider"]["handler"], "index.handler")
        self.assertEqual(function["spec"]["forProvider"]["s3Bucket"], "laz-lambda-artifacts")
        self.assertEqual(function["spec"]["forProvider"]["s3Key"], "example/function.zip")

    async def test_omits_function_url_by_default_even_once_function_arn_known(self) -> None:
        got = await self.run_function(make_request(BASE_SPEC, FULLY_OBSERVED_STATUS))
        self.assertNotIn("function-url", got["desired"]["resources"])

    async def test_omits_function_url_when_requested_but_function_arn_not_yet_known(self) -> None:
        spec = {**BASE_SPEC, "functionUrlEnabled": True}
        got = await self.run_function(make_request(spec))
        self.assertNotIn("function-url", got["desired"]["resources"])

    async def test_function_url_auth_type_is_always_iam_when_enabled(self) -> None:
        # No spec field exists to set this to "NONE" -- this is the
        # hardcoded secure default, not an override-resistance test.
        spec = {**BASE_SPEC, "functionUrlEnabled": True}
        got = await self.run_function(make_request(spec, FULLY_OBSERVED_STATUS))
        function_url = got["desired"]["resources"]["function-url"]["resource"]
        self.assertEqual(function_url["kind"], "FunctionUrl")
        self.assertEqual(function_url["spec"]["forProvider"]["authorizationType"], "AWS_IAM")
        self.assertEqual(function_url["spec"]["forProvider"]["functionName"], "laz-lambda-example")

    async def test_reflects_memory_timeout_description_and_environment_variables(self) -> None:
        spec = {
            **BASE_SPEC,
            "description": "Example function",
            "memorySize": 256,
            "timeoutSeconds": 15,
            "environmentVariables": {"LOG_LEVEL": "debug"},
        }
        got = await self.run_function(make_request(spec, ROLE_KNOWN_STATUS))
        for_provider = got["desired"]["resources"]["function"]["resource"]["spec"]["forProvider"]
        self.assertEqual(for_provider["description"], "Example function")
        self.assertEqual(for_provider["memorySize"], 256)
        self.assertEqual(for_provider["timeout"], 15)
        self.assertEqual(for_provider["environment"]["variables"], {"LOG_LEVEL": "debug"})


if __name__ == "__main__":
    unittest.main()
