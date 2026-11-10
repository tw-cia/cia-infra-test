import json
import unittest

from crossplane.function import logging, resource
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import duration_pb2 as durationpb
from google.protobuf import json_format
from google.protobuf import struct_pb2 as structpb

from function import fn

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

ASSUME_ROLE_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
)


class TestFunctionRunner(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Allow larger diffs, since we diff large strings of JSON.
        self.maxDiff = 4000

        logging.configure(level=logging.Level.DISABLED)

    async def test_composes_role_and_policy_attachments(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "IAMRole",
                            "spec": {
                                "roleName": "laz-lambda-example-role",
                                "description": "Example Lambda execution role",
                                "trustedService": "lambda.amazonaws.com",
                                "managedPolicyArns": [
                                    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                                ],
                            },
                        }
                    ),
                ),
            ),
        )

        want = fnv1.RunFunctionResponse(
            meta=fnv1.ResponseMeta(ttl=durationpb.Duration(seconds=60)),
            desired=fnv1.State(
                resources={
                    "role": fnv1.Resource(
                        resource=resource.dict_to_struct(
                            {
                                "apiVersion": "iam.aws.m.upbound.io/v1beta1",
                                "kind": "Role",
                                "metadata": {
                                    "annotations": {
                                        "crossplane.io/external-name": "laz-lambda-example-role",
                                    },
                                },
                                "spec": {
                                    "forProvider": {
                                        "assumeRolePolicy": ASSUME_ROLE_POLICY,
                                        "description": "Example Lambda execution role",
                                    },
                                    "providerConfigRef": PROVIDER_CONFIG,
                                },
                            }
                        ),
                    ),
                    "policy-attachment-0": fnv1.Resource(
                        resource=resource.dict_to_struct(
                            {
                                "apiVersion": "iam.aws.m.upbound.io/v1beta1",
                                "kind": "RolePolicyAttachment",
                                "spec": {
                                    "forProvider": {
                                        "policyArn": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                                        "role": "laz-lambda-example-role",
                                    },
                                    "providerConfigRef": PROVIDER_CONFIG,
                                },
                            }
                        ),
                    ),
                },
            ),
            context=structpb.Struct(),
        )

        got = await fn.FunctionRunner().RunFunction(req, None)

        self.assertEqual(
            json_format.MessageToDict(want),
            json_format.MessageToDict(got),
            "-want, +got",
        )

    async def test_surfaces_role_arn_once_known(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "IAMRole",
                            "spec": {
                                "roleName": "laz-lambda-example-role",
                                "trustedService": "lambda.amazonaws.com",
                            },
                        }
                    ),
                ),
                resources={
                    "role": fnv1.Resource(
                        resource=resource.dict_to_struct(
                            {
                                "status": {
                                    "atProvider": {
                                        "arn": "arn:aws:iam::123456789012:role/laz-lambda-example-role",
                                    },
                                },
                            }
                        ),
                    ),
                },
            ),
        )

        want = fnv1.RunFunctionResponse(
            meta=fnv1.ResponseMeta(ttl=durationpb.Duration(seconds=60)),
            desired=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "status": {
                                "roleArn": "arn:aws:iam::123456789012:role/laz-lambda-example-role",
                            },
                        },
                    ),
                ),
                resources={
                    "role": fnv1.Resource(
                        resource=resource.dict_to_struct(
                            {
                                "apiVersion": "iam.aws.m.upbound.io/v1beta1",
                                "kind": "Role",
                                "metadata": {
                                    "annotations": {
                                        "crossplane.io/external-name": "laz-lambda-example-role",
                                    },
                                },
                                "spec": {
                                    "forProvider": {
                                        "assumeRolePolicy": ASSUME_ROLE_POLICY,
                                    },
                                    "providerConfigRef": PROVIDER_CONFIG,
                                },
                            }
                        ),
                    ),
                },
            ),
            context=structpb.Struct(),
        )

        got = await fn.FunctionRunner().RunFunction(req, None)

        self.assertEqual(
            json_format.MessageToDict(want),
            json_format.MessageToDict(got),
            "-want, +got",
        )


if __name__ == "__main__":
    unittest.main()
