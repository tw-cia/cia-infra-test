# The pure composition logic for LambdaFunction, extracted out of
# ../manifests/crossplane-compositions/externalized-kcl so it can be tested
# with the `kcl test` CLI directly (no Docker, no crossplane render) -- the
# same role staticwebsite.k/dnsvalidatedcertificate.k/iamrole.k play for
# their own kinds.
#
# Delegates to the IAMRole XR for its execution role, the same nested-XR
# pattern staticwebsite.k uses for DnsValidatedCertificate. Two things are
# hardcoded secure defaults with no corresponding spec field at all, so
# there is nothing a caller can set to override them: the delegated role's
# trustedService (always lambda.amazonaws.com) and, if a FunctionUrl is
# requested, its authorizationType (always AWS_IAM, never NONE).
#
# Function/FunctionUrl are gated on statusIn (this composite's OWN
# persisted status from a prior pass), not a live same-pass read of ocds --
# matching staticwebsite.k's certificateArn/bucketDomainName gating. This
# isn't just stylistic consistency: Patch-and-Transform (one of the other
# five methods this has to agree with) has no way to read another
# resource's observed status directly, only by round-tripping it through
# the composite's own status first, so every method has to share this same
# multi-pass shape to stay equivalent.
#
# This file must not call option(...) -- see staticwebsite.k's docstring for
# why.

composeLambdaFunction = lambda oxr: {str:any}, ocds: {str:any} -> [{str:any}] {
    spec = oxr.spec
    statusIn = oxr.status or {}

    functionName = spec.functionName

    role = {
        apiVersion = "platform.cia-infra-test.io/v1alpha1"
        kind = "IAMRole"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "role"
        }
        spec = {
            roleName = "${functionName}-role"
            # Hardcoded: nothing in LambdaFunction's own spec can set this to
            # anything but the one service this role is actually for.
            trustedService = "lambda.amazonaws.com"
            managedPolicyArns = [
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ] + (spec?.managedPolicyArns or [])
        }
    }

    roleArn = statusIn?.roleArn
    code = spec.code

    forProvider = {
        role = roleArn
        runtime = spec.runtime
        handler = spec.handler
        s3Bucket = code.s3Bucket
        s3Key = code.s3Key
        **({"description": spec.description} if spec?.description else {})
        **({"memorySize": spec.memorySize} if spec?.memorySize else {})
        **({"timeout": spec.timeoutSeconds} if spec?.timeoutSeconds else {})
        **({"environment": {"variables": spec.environmentVariables}} if spec?.environmentVariables else {})
    }

    function = [{
        apiVersion = "lambda.aws.m.upbound.io/v1beta1"
        kind = "Function"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "function"
            "crossplane.io/external-name" = functionName
        }
        spec = {
            forProvider = forProvider
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }] if roleArn else []

    functionArn = statusIn?.functionArn
    functionUrl = [{
        apiVersion = "lambda.aws.m.upbound.io/v1beta1"
        kind = "FunctionUrl"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "function-url"
        }
        spec = {
            forProvider = {
                functionName = functionName
                # Hardcoded: nothing in LambdaFunction's own spec can set
                # this to "NONE" -- a public invoke URL isn't an option.
                authorizationType = "AWS_IAM"
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }] if (spec?.functionUrlEnabled and functionArn) else []

    observedRoleArn = ocds["role"]?.Resource?.status?.roleArn
    observedFunctionArn = ocds["function"]?.Resource?.status?.atProvider?.arn
    observedFunctionUrl = ocds["function-url"]?.Resource?.status?.atProvider?.functionUrl
    statusPatch = {
        **({"roleArn": observedRoleArn} if observedRoleArn else {})
        **({"functionArn": observedFunctionArn} if observedFunctionArn else {})
        **({"functionUrl": observedFunctionUrl} if observedFunctionUrl else {})
    }
    dxr = {**oxr, status = statusPatch}

    [role] + function + functionUrl + [dxr]
}
