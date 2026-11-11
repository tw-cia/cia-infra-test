import json
import unittest

from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import duration_pb2 as durationpb
from google.protobuf import json_format
from google.protobuf import struct_pb2 as structpb

from iamrole import compose

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


class TestCompose(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = 4000
        logging.configure(level=logging.Level.DISABLED)

    def run_compose(self, req: fnv1.RunFunctionRequest) -> dict:
        rsp = response.to(req)
        compose(req, rsp)
        return json_format.MessageToDict(rsp)

    def test_composes_role_and_policy_attachments(self) -> None:
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

        got = self.run_compose(req)

        self.assertEqual(json_format.MessageToDict(want), got, "-want, +got")

    def test_role_name_matches_spec(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "IAMRole",
                            "spec": {
                                "roleName": "totally-different-role-name",
                                "trustedService": "lambda.amazonaws.com",
                            },
                        }
                    ),
                ),
            ),
        )

        got = self.run_compose(req)

        role = got["desired"]["resources"]["role"]["resource"]
        self.assertEqual(
            role["metadata"]["annotations"]["crossplane.io/external-name"],
            "totally-different-role-name",
        )

    def test_does_not_patch_status_when_role_not_yet_observed(self) -> None:
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
                # No "resources" set: nothing has been observed yet.
            ),
        )

        got = self.run_compose(req)

        self.assertNotIn("composite", got.get("desired", {}))

    def test_surfaces_role_arn_once_known(self) -> None:
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

        got = self.run_compose(req)

        self.assertEqual(
            got["desired"]["composite"]["resource"]["status"]["roleArn"],
            "arn:aws:iam::123456789012:role/laz-lambda-example-role",
        )


if __name__ == "__main__":
    unittest.main()
