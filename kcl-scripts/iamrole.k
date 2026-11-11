# The pure composition logic for IAMRole, extracted out of
# ../manifests/crossplane-compositions/externalized-kcl so it can be tested
# with the `kcl test` CLI directly (no Docker, no crossplane render) -- the
# same role scripts/iamrole.py plays for inline-python. Faithfully ported
# from ../manifests/crossplane-compositions/kcl/composition-iamrole-kcl.yaml.
#
# This file must not call option(...) -- see staticwebsite.k's docstring for
# why.
import json

composeIamRole = lambda oxr: {str:any}, ocds: {str:any} -> [{str:any}] {
    spec = oxr.spec

    assumeRolePolicy = {
        Version = "2012-10-17"
        Statement = [{
            Effect = "Allow"
            Principal = {Service = spec.trustedService}
            Action = "sts:AssumeRole"
        }]
    }

    forProvider = {
        "assumeRolePolicy": json.encode(assumeRolePolicy)
        **({"description": spec.description} if spec?.description else {})
    }

    role = {
        apiVersion = "iam.aws.m.upbound.io/v1beta1"
        kind = "Role"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "role"
            "crossplane.io/external-name" = spec.roleName
        }
        spec = {
            forProvider = forProvider
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }

    policyAttachments = [{
        apiVersion = "iam.aws.m.upbound.io/v1beta1"
        kind = "RolePolicyAttachment"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "policy-attachment-${i}"
        }
        spec = {
            forProvider = {policyArn = arn, role = spec.roleName}
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    } for i, arn in (spec?.managedPolicyArns or [])]

    roleArn = ocds["role"]?.Resource?.status?.atProvider?.arn
    statusPatch = {"roleArn": roleArn} if roleArn else {}

    dxr = {**oxr, status = statusPatch}

    [role] + policyAttachments + [dxr]
}
