# The pure composition logic for DnsValidatedCertificate, extracted out of
# ../manifests/crossplane-compositions/externalized-kcl so it can be tested
# with the `kcl test` CLI directly (no Docker, no crossplane render) -- the
# same role scripts/dnsvalidatedcertificate.py plays for inline-python.
# Faithfully ported from
# ../manifests/crossplane-compositions/kcl/composition-dnsvalidatedcertificate-kcl.yaml.
#
# This file must not call option(...) -- see staticwebsite.k's docstring for
# why.

composeCertificate = lambda oxr: {str:any}, ocds: {str:any} -> [{str:any}] {
    spec = oxr.spec
    statusIn = oxr.status or {}

    domainName = spec.domainName
    zoneId = spec.zone.id

    certificate = {
        apiVersion = "acm.aws.m.upbound.io/v1beta1"
        kind = "Certificate"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "certificate"
        }
        spec = {
            forProvider = {
                region = "us-east-1"
                validationMethod = "DNS"
                domainName = domainName
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }

    atProvider = ocds["certificate"]?.Resource?.status?.atProvider
    validationOptions = atProvider?.domainValidationOptions or []
    firstOption = validationOptions[0] if validationOptions else None

    statusPatch = {
        **({"certificateArn": atProvider.arn} if atProvider?.arn else {})
        **({"certValidationRecordName": firstOption.resourceRecordName} if firstOption?.resourceRecordName else {})
        **({"certValidationRecordValue": firstOption.resourceRecordValue} if firstOption?.resourceRecordValue else {})
    }

    dxr = {**oxr, status = statusPatch}

    validationRecordName = statusIn?.certValidationRecordName
    validationRecordValue = statusIn?.certValidationRecordValue
    certValidationRecord = [{
        apiVersion = "route53.aws.m.upbound.io/v1beta1"
        kind = "Record"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "cert-validation-record"
        }
        spec = {
            forProvider = {
                type = "CNAME"
                ttl = 300
                name = validationRecordName
                records = [validationRecordValue]
                zoneId = zoneId
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }] if validationRecordName and validationRecordValue else []

    certificateArn = statusIn?.certificateArn
    certificateValidation = [{
        apiVersion = "acm.aws.m.upbound.io/v1beta1"
        kind = "CertificateValidation"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "certificate-validation"
        }
        spec = {
            forProvider = {
                region = "us-east-1"
                certificateArn = certificateArn
                validationRecordFqdns = [validationRecordName]
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }] if certificateArn and validationRecordName else []

    [certificate] + certValidationRecord + certificateValidation + [dxr]
}
