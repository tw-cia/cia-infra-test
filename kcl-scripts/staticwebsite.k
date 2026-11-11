# The pure composition logic for StaticWebsite, extracted out of
# ../manifests/crossplane-compositions/externalized-kcl so it can be tested
# with the `kcl test` CLI directly (no Docker, no crossplane render) -- the
# same role scripts/staticwebsite.py plays for inline-python. Faithfully
# ported from ../manifests/crossplane-compositions/kcl/composition-staticwebsite-kcl.yaml,
# bug and all (viewerCertificate.acmCertificateArn is gated on
# status.certificateArn alone, not on whether a custom zone is even set, so a
# StaticWebsite with no custom zone can never actually get a Distribution).
#
# This file must not call option(...) -- that's only resolvable inside the
# function-kcl runtime. The Composition's .jsonnet file appends a glue line
# (`items = compose(option("params").oxr, option("params").ocds)`) after
# importstr-ing this file in, keeping option() out of anything `kcl test`
# compiles.
import json

composeStaticWebsite = lambda oxr: {str:any}, ocds: {str:any} -> [{str:any}] {
    spec = oxr.spec
    statusIn = oxr.status or {}

    bucketName = spec.bucket.name
    bucketRegion = spec.bucket.region
    zone = spec?.zone

    bucket = {
        apiVersion = "s3.aws.m.upbound.io/v1beta1"
        kind = "Bucket"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "bucket"
            "crossplane.io/external-name" = bucketName
        }
        spec = {
            forProvider = {region = bucketRegion}
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }
    bucketDomainName = ocds["bucket"]?.Resource?.status?.atProvider?.bucketRegionalDomainName

    bucketPublicAccessBlock = {
        apiVersion = "s3.aws.m.upbound.io/v1beta1"
        kind = "BucketPublicAccessBlock"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "bucket-public-access-block"
        }
        spec = {
            forProvider = {
                blockPublicAcls = True
                blockPublicPolicy = True
                ignorePublicAcls = True
                restrictPublicBuckets = True
                bucket = bucketName
                region = bucketRegion
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }

    originAccessControl = {
        apiVersion = "cloudfront.aws.m.upbound.io/v1beta1"
        kind = "OriginAccessControl"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "origin-access-control"
        }
        spec = {
            forProvider = {
                originAccessControlOriginType = "s3"
                signingBehavior = "always"
                signingProtocol = "sigv4"
                name = "${bucketName}-oac"
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }

    distributionArn = statusIn?.distributionArn
    bucketPolicy = [{
        apiVersion = "s3.aws.m.upbound.io/v1beta1"
        kind = "BucketPolicy"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "bucket-policy"
        }
        spec = {
            forProvider = {
                bucket = bucketName
                region = bucketRegion
                policy = json.encode({
                    Version = "2012-10-17"
                    Statement = [{
                        Sid = "AllowCloudFrontServicePrincipal"
                        Effect = "Allow"
                        Principal = {Service = "cloudfront.amazonaws.com"}
                        Action = "s3:GetObject"
                        Resource = "arn:aws:s3:::${bucketName}/*"
                        Condition = {StringEquals = {"AWS:SourceArn" = distributionArn}}
                    }]
                })
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }] if distributionArn else []

    hasZone = zone?.name and zone?.id
    observedCertificateArn = ocds["certificate"]?.Resource?.status?.certificateArn
    certificate = [{
        apiVersion = "platform.cia-infra-test.io/v1alpha1"
        kind = "DnsValidatedCertificate"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "certificate"
        }
        spec = {
            domainName = zone.name
            zone = {id = zone.id}
        }
    }] if hasZone else []

    certificateArn = statusIn?.certificateArn
    bucketDomainNameIn = statusIn?.bucketDomainName
    hasDistribution = bucketDomainNameIn and certificateArn
    viewerCertificate = ({
        sslSupportMethod = "sni-only"
        minimumProtocolVersion = "TLSv1.2_2021"
        acmCertificateArn = certificateArn
    } if zone?.name else {cloudfrontDefaultCertificate = True}) if hasDistribution else {}

    distributionForProvider = {
        enabled = True
        isIpv6Enabled = True
        priceClass = "PriceClass_100"
        restrictions = {geoRestriction = {restrictionType = "none"}}
        viewerCertificate = viewerCertificate
        origin = [{
            originId = "s3-origin"
            originAccessControlIdSelector = {matchControllerRef = True}
            domainName = bucketDomainNameIn
        }]
        defaultCacheBehavior = {
            targetOriginId = "s3-origin"
            viewerProtocolPolicy = "redirect-to-https"
            allowedMethods = ["GET", "HEAD"]
            cachedMethods = ["GET", "HEAD"]
            # AWS managed "CachingOptimized" policy -- a fixed, global ID
            # documented by AWS, not account-specific.
            cachePolicyId = "658327ea-f89d-4fab-a63d-7e88639e58f6"
        }
        **({"defaultRootObject": spec.indexDocument} if spec?.indexDocument else {})
        **({"aliases": [zone.name]} if zone?.name else {})
    }
    distAtProvider = ocds["distribution"]?.Resource?.status?.atProvider
    distribution = [{
        apiVersion = "cloudfront.aws.m.upbound.io/v1beta1"
        kind = "Distribution"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "distribution"
        }
        spec = {
            forProvider = distributionForProvider
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }] if hasDistribution else []

    cloudfrontDomainNameIn = statusIn?.cloudfrontDomainName
    hasDomainAliasRecord = hasZone and cloudfrontDomainNameIn
    domainAliasRecord = [{
        apiVersion = "route53.aws.m.upbound.io/v1beta1"
        kind = "Record"
        metadata.annotations = {
            "krm.kcl.dev/composition-resource-name" = "domain-alias-record"
        }
        spec = {
            forProvider = {
                type = "A"
                alias = {
                    # Fixed, universal CloudFront alias-target hosted zone ID
                    # -- not account- or distribution-specific.
                    zoneId = "Z2FDTNDATAQYW2"
                    evaluateTargetHealth = False
                    name = cloudfrontDomainNameIn
                }
                name = zone.name
                zoneId = zone.id
            }
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }] if hasDomainAliasRecord else []

    statusPatch = {
        **({"bucketDomainName": bucketDomainName} if bucketDomainName else {})
        **({"certificateArn": observedCertificateArn} if hasZone and observedCertificateArn else {})
        **({"cloudfrontDomainName": distAtProvider.domainName} if hasDistribution and distAtProvider?.domainName else {})
        **({"distributionArn": distAtProvider.arn} if hasDistribution and distAtProvider?.arn else {})
    }
    dxr = {**oxr, status = statusPatch}

    [bucket, bucketPublicAccessBlock, originAccessControl] + bucketPolicy + certificate + distribution + domainAliasRecord + [dxr]
}
