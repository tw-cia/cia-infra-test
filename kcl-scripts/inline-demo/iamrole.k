# Same composition logic as ../iamrole.k, written the other way: no lambda,
# no oxr/ocds parameters -- option("params") called directly at module
# scope, and the result assigned to a bare top-level `items` instead of
# returned from a function. This is what the "plain kcl" method
# (../../manifests/crossplane-compositions/kcl/composition-iamrole-kcl.yaml)
# actually puts in its Composition source, and it's exactly the shape
# ../iamrole.k's docstring says not to use.
#
# Deliberately isolated in its own subdirectory with no _test.k file: `kcl
# test` compiles an entire directory as one package, evaluating every
# top-level statement in every .k file there even if nothing imports it. A
# module-scope option("params") call has nothing bound when run that way,
# so dropping this file into ../ directly makes option("params") resolve to
# None and fails every one of the 36 existing tests in that package, not
# just this file. A directory with no _test.k is never evaluated by `kcl
# test` at all, so this sits here harmlessly.
import json

oxr = option("params").oxr
ocds = option("params").ocds
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

items = [role] + policyAttachments + [dxr]
