import json

from crossplane.function import resource
from google.protobuf.json_format import MessageToDict

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

def compose(req, rsp):
    xr = MessageToDict(req.observed.composite.resource)
    spec = xr["spec"]
    role_name = spec["roleName"]

    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": spec["trustedService"]},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    for_provider = {"assumeRolePolicy": json.dumps(assume_role_policy)}
    if "description" in spec:
        for_provider["description"] = spec["description"]

    resource.update(
        rsp.desired.resources["role"],
        {
            "apiVersion": "iam.aws.m.upbound.io/v1beta1",
            "kind": "Role",
            "metadata": {
                "annotations": {"crossplane.io/external-name": role_name},
            },
            "spec": {
                "forProvider": for_provider,
                "providerConfigRef": PROVIDER_CONFIG,
            },
        },
    )

    for i, policy_arn in enumerate(spec.get("managedPolicyArns", [])):
        resource.update(
            rsp.desired.resources[f"policy-attachment-{i}"],
            {
                "apiVersion": "iam.aws.m.upbound.io/v1beta1",
                "kind": "RolePolicyAttachment",
                "spec": {
                    "forProvider": {
                        "policyArn": policy_arn,
                        "role": role_name,
                    },
                    "providerConfigRef": PROVIDER_CONFIG,
                },
            },
        )

    # Surface the role ARN on the XR once AWS has created it.
    if "role" in req.observed.resources:
        arn = (
            MessageToDict(req.observed.resources["role"].resource)
            .get("status", {})
            .get("atProvider", {})
            .get("arn")
        )
        if arn:
            rsp.desired.composite.resource.update(
                {"status": {"roleArn": arn}}
            )
