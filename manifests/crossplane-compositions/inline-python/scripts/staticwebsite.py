from crossplane.function import resource
from google.protobuf.json_format import MessageToDict

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

# AWS managed "CachingOptimized" policy -- a fixed, global ID
# documented by AWS, not account-specific.
CACHING_OPTIMIZED_POLICY_ID = "658327ea-f89d-4fab-a63d-7e88639e58f6"

# Fixed, universal CloudFront alias-target hosted zone ID -- not
# account- or distribution-specific.
CLOUDFRONT_ALIAS_ZONE_ID = "Z2FDTNDATAQYW2"

def compose(req, rsp):
    xr = MessageToDict(req.observed.composite.resource)
    spec = xr.get("spec", {})
    status_in = xr.get("status", {})

    bucket_name = spec["bucket"]["name"]
    bucket_region = spec["bucket"]["region"]
    zone = spec.get("zone")

    # bucket
    resource.update(
        rsp.desired.resources["bucket"],
        {
            "apiVersion": "s3.aws.m.upbound.io/v1beta1",
            "kind": "Bucket",
            "metadata": {"annotations": {"crossplane.io/external-name": bucket_name}},
            "spec": {
                "forProvider": {"region": bucket_region},
                "providerConfigRef": PROVIDER_CONFIG,
            },
        },
    )
    status = {}
    if "bucket" in req.observed.resources:
        observed_bucket = MessageToDict(req.observed.resources["bucket"].resource)
        bucket_domain_name = (
            observed_bucket.get("status", {})
            .get("atProvider", {})
            .get("bucketRegionalDomainName")
        )
        if bucket_domain_name:
            status["bucketDomainName"] = bucket_domain_name

    # bucket-public-access-block
    resource.update(
        rsp.desired.resources["bucket-public-access-block"],
        {
            "apiVersion": "s3.aws.m.upbound.io/v1beta1",
            "kind": "BucketPublicAccessBlock",
            "spec": {
                "forProvider": {
                    "blockPublicAcls": True,
                    "blockPublicPolicy": True,
                    "ignorePublicAcls": True,
                    "restrictPublicBuckets": True,
                    "bucket": bucket_name,
                    "region": bucket_region,
                },
                "providerConfigRef": PROVIDER_CONFIG,
            },
        },
    )

    # origin-access-control
    resource.update(
        rsp.desired.resources["origin-access-control"],
        {
            "apiVersion": "cloudfront.aws.m.upbound.io/v1beta1",
            "kind": "OriginAccessControl",
            "spec": {
                "forProvider": {
                    "originAccessControlOriginType": "s3",
                    "signingBehavior": "always",
                    "signingProtocol": "sigv4",
                    "name": f"{bucket_name}-oac",
                },
                "providerConfigRef": PROVIDER_CONFIG,
            },
        },
    )

    # bucket-policy -- gated on status.distributionArn (Required)
    distribution_arn = status_in.get("distributionArn")
    if distribution_arn:
        policy = (
            '{"Version":"2012-10-17","Statement":[{"Sid":"AllowCloudFrontServicePrincipal",'
            '"Effect":"Allow","Principal":{"Service":"cloudfront.amazonaws.com"},'
            '"Action":"s3:GetObject","Resource":"arn:aws:s3:::%s/*",'
            '"Condition":{"StringEquals":{"AWS:SourceArn":"%s"}}}]}'
            % (bucket_name, distribution_arn)
        )
        resource.update(
            rsp.desired.resources["bucket-policy"],
            {
                "apiVersion": "s3.aws.m.upbound.io/v1beta1",
                "kind": "BucketPolicy",
                "spec": {
                    "forProvider": {
                        "bucket": bucket_name,
                        "region": bucket_region,
                        "policy": policy,
                    },
                    "providerConfigRef": PROVIDER_CONFIG,
                },
            },
        )

    # certificate -- delegates to its own Composition. Gated on
    # spec.zone.name and spec.zone.id (both Required), since the
    # custom domain is optional.
    certificate_arn = status_in.get("certificateArn")
    if zone and zone.get("name") and zone.get("id"):
        resource.update(
            rsp.desired.resources["certificate"],
            {
                "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                "kind": "DnsValidatedCertificate",
                "spec": {"domainName": zone["name"], "zone": {"id": zone["id"]}},
            },
        )
        if "certificate" in req.observed.resources:
            observed_certificate = MessageToDict(
                req.observed.resources["certificate"].resource
            )
            observed_certificate_arn = observed_certificate.get("status", {}).get(
                "certificateArn"
            )
            if observed_certificate_arn:
                status["certificateArn"] = observed_certificate_arn

    # distribution -- gated on status.bucketDomainName and (always,
    # regardless of whether a custom zone is set -- this is the bug
    # being faithfully replicated) status.certificateArn.
    bucket_domain_name_in = status_in.get("bucketDomainName")
    if bucket_domain_name_in and certificate_arn:
        if zone and zone.get("name"):
            viewer_certificate = {
                "sslSupportMethod": "sni-only",
                "minimumProtocolVersion": "TLSv1.2_2021",
                "acmCertificateArn": certificate_arn,
            }
        else:
            viewer_certificate = {"cloudfrontDefaultCertificate": True}

        for_provider = {
            "enabled": True,
            "isIpv6Enabled": True,
            "priceClass": "PriceClass_100",
            "restrictions": {"geoRestriction": {"restrictionType": "none"}},
            "viewerCertificate": viewer_certificate,
            "origin": [
                {
                    "originId": "s3-origin",
                    "originAccessControlIdSelector": {"matchControllerRef": True},
                    "domainName": bucket_domain_name_in,
                }
            ],
            "defaultCacheBehavior": {
                "targetOriginId": "s3-origin",
                "viewerProtocolPolicy": "redirect-to-https",
                "allowedMethods": ["GET", "HEAD"],
                "cachedMethods": ["GET", "HEAD"],
                "cachePolicyId": CACHING_OPTIMIZED_POLICY_ID,
            },
        }
        if "indexDocument" in spec:
            for_provider["defaultRootObject"] = spec["indexDocument"]
        if zone and zone.get("name"):
            for_provider["aliases"] = [zone["name"]]

        resource.update(
            rsp.desired.resources["distribution"],
            {
                "apiVersion": "cloudfront.aws.m.upbound.io/v1beta1",
                "kind": "Distribution",
                "spec": {"forProvider": for_provider, "providerConfigRef": PROVIDER_CONFIG},
            },
        )

        if "distribution" in req.observed.resources:
            observed_distribution = MessageToDict(
                req.observed.resources["distribution"].resource
            )
            at_provider = observed_distribution.get("status", {}).get("atProvider", {})
            if at_provider.get("domainName"):
                status["cloudfrontDomainName"] = at_provider["domainName"]
            if at_provider.get("arn"):
                status["distributionArn"] = at_provider["arn"]

    # domain-alias-record -- gated on spec.zone.name, spec.zone.id,
    # and status.cloudfrontDomainName (all Required).
    cloudfront_domain_name_in = status_in.get("cloudfrontDomainName")
    if zone and zone.get("name") and zone.get("id") and cloudfront_domain_name_in:
        resource.update(
            rsp.desired.resources["domain-alias-record"],
            {
                "apiVersion": "route53.aws.m.upbound.io/v1beta1",
                "kind": "Record",
                "spec": {
                    "forProvider": {
                        "type": "A",
                        "alias": {
                            "zoneId": CLOUDFRONT_ALIAS_ZONE_ID,
                            "evaluateTargetHealth": False,
                            "name": cloudfront_domain_name_in,
                        },
                        "name": zone["name"],
                        "zoneId": zone["id"],
                    },
                    "providerConfigRef": PROVIDER_CONFIG,
                },
            },
        )

    if status:
        rsp.desired.composite.resource.update({"status": status})
