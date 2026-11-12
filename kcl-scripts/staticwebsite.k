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
import schemas_compositions
import schemas_providers

# Every provider-backed resource here shares the same shape: a single
# composition-resource-name annotation, forProvider, and the same
# providerConfigRef. This factors that out; extraAnnotations covers the one
# outlier (bucket's external-name annotation).
awsResource = lambda apiVersion: str, kind: str, name: str, forProvider: schemas_providers.StaticWebsiteForProvider, extraAnnotations: {str:str} = {} -> {str:any} {
    {
        apiVersion = apiVersion
        kind = kind
        metadata.annotations = {"krm.kcl.dev/composition-resource-name" = name} | extraAnnotations
        spec = {
            forProvider = forProvider
            providerConfigRef = {kind = "ClusterProviderConfig", name = "pod-identity"}
        }
    }
}

composeStaticWebsite = lambda oxr: {str:any}, ocds: {str:any} -> [{str:any}] {
    spec: schemas_compositions.StaticWebsiteSpec = oxr.spec
    statusIn = oxr.status or {}

    bucketName = spec.bucket.name
    bucketRegion = spec.bucket.region
    zone = spec?.zone

    bucketForProvider: schemas_providers.BucketForProvider = {region = bucketRegion}
    bucket = awsResource("s3.aws.m.upbound.io/v1beta1", "Bucket", "bucket", bucketForProvider, {"crossplane.io/external-name" = bucketName})
    bucketDomainName = ocds["bucket"]?.Resource?.status?.atProvider?.bucketRegionalDomainName

    bucketPublicAccessBlockForProvider: schemas_providers.BucketPublicAccessBlockForProvider = {
        blockPublicAcls = True
        blockPublicPolicy = True
        ignorePublicAcls = True
        restrictPublicBuckets = True
        bucket = bucketName
        region = bucketRegion
    }
    bucketPublicAccessBlock = awsResource("s3.aws.m.upbound.io/v1beta1", "BucketPublicAccessBlock", "bucket-public-access-block", bucketPublicAccessBlockForProvider)

    originAccessControlForProvider: schemas_providers.OriginAccessControlForProvider = {
        originAccessControlOriginType = "s3"
        signingBehavior = "always"
        signingProtocol = "sigv4"
        name = "${bucketName}-oac"
    }
    originAccessControl = awsResource("cloudfront.aws.m.upbound.io/v1beta1", "OriginAccessControl", "origin-access-control", originAccessControlForProvider)

    distributionArn = statusIn?.distributionArn
    bucketPolicyForProvider: schemas_providers.BucketPolicyForProvider = {
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
                Condition = {
                    StringEquals = {"AWS:SourceArn" = distributionArn}
                }
            }]
        })
    }
    bucketPolicy = [awsResource("s3.aws.m.upbound.io/v1beta1", "BucketPolicy", "bucket-policy", bucketPolicyForProvider)] if distributionArn else []

    hasZone = zone?.name and zone?.id
    observedCertificateArn = ocds["certificate"]?.Resource?.status?.certificateArn
    certificate = [{
        apiVersion = "platform.cia-infra-test.io/v1alpha1"
        kind = "DnsValidatedCertificate"
        metadata.annotations = {"krm.kcl.dev/composition-resource-name" = "certificate"}
        spec = schemas_compositions.DnsValidatedCertificateSpec {
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

    distAtProvider = ocds["distribution"]?.Resource?.status?.atProvider

    # distributionForProvider's required fields (origin[0].domainName in
    # particular) are only guaranteed non-None once hasDistribution holds --
    # built inside this branch, not hoisted above it, so a schema-typed
    # construction with a still-unobserved bucketDomainNameIn never happens.
    distribution = [awsResource("cloudfront.aws.m.upbound.io/v1beta1", "Distribution", "distribution", schemas_providers.DistributionForProvider {
        enabled = True
        isIpv6Enabled = True
        priceClass = "PriceClass_100"
        restrictions = {
            geoRestriction = {restrictionType = "none"}
        }
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
    })] if hasDistribution else []

    cloudfrontDomainNameIn = statusIn?.cloudfrontDomainName
    hasDomainAliasRecord = hasZone and cloudfrontDomainNameIn

    # Same reasoning as distribution above -- alias.name needs
    # cloudfrontDomainNameIn to be non-None, which hasDomainAliasRecord
    # guarantees only inside this branch.
    domainAliasRecord = [awsResource("route53.aws.m.upbound.io/v1beta1", "Record", "domain-alias-record", schemas_providers.DomainAliasRecordForProvider {
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
    })] if hasDomainAliasRecord else []

    statusPatch = {k: v for k, v in {
        "bucketDomainName": bucketDomainName
        "certificateArn": observedCertificateArn if hasZone else None
        "cloudfrontDomainName": distAtProvider?.domainName if hasDistribution else None
        "distributionArn": distAtProvider?.arn if hasDistribution else None
    } if v != None}
    dxr = {**oxr, status = statusPatch}

    [bucket, bucketPublicAccessBlock, originAccessControl] + bucketPolicy + certificate + distribution + domainAliasRecord + [dxr]
}
