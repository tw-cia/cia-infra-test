# kcl test ./... -- mirrors scripts/tests/test_staticwebsite.py,
# tests/test_staticwebsite_security.py, and
# tests/test_staticwebsite_input_reflection.py, which exercise this same
# logic (and the other implementations) via `crossplane composition render`.
# This runs directly against composeStaticWebsite() instead -- no Docker, no
# render -- for a fast local feedback loop on this one implementation.
import json
import staticwebsite

swByName = lambda items: [{str:any}] -> {str:{str:any}} {
    {item["metadata"]["annotations"]["krm.kcl.dev/composition-resource-name"]: item for item in items if "metadata" in item}
}

swComposite = lambda items: [{str:any}] -> {str:any} {
    [item for item in items if not ("metadata" in item)][0]
}

SW_BASE_SPEC = {
    "bucket": {"name": "laz-static-website-customdomain-demo", "region": "ap-southeast-1"}
}

# Matches tests/fixtures/staticwebsite-xr-fully-observed.yaml -- the only
# scenario where bucket-policy and the Distribution both render (gated on
# status.distributionArn / status.certificateArn respectively).
FULLY_OBSERVED_SPEC = {
    "bucket": {"name": "laz-static-website-customdomain-demo", "region": "ap-southeast-1"}
    "zone": {"name": "static.trololo.demotw.com", "id": "Z00921083AT1Z6WZY8LYW"}
}
FULLY_OBSERVED_STATUS = {
    "bucketDomainName": "laz-static-website-customdomain-demo.s3.ap-southeast-1.amazonaws.com"
    "distributionArn": "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE"
    "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
    "cloudfrontDomainName": "d111111abcdef8.cloudfront.net"
}

# Matches tests/fixtures/staticwebsite-xr-input-reflection.yaml -- values not
# shared with any other scenario here, so a passing assertion proves the
# value flowed from spec to the rendered resource, not coincidence.
INPUT_REFLECTION_SPEC = {
    "bucket": {"name": "reflection-test-bucket", "region": "eu-west-2"}
    "zone": {"name": "reflection.example.com", "id": "ZDISTINCTZONEID123"}
    "indexDocument": "home.html"
}
INPUT_REFLECTION_STATUS = {
    "bucketDomainName": "reflection-test-bucket.s3.eu-west-2.amazonaws.com"
    "certificateArn": "arn:aws:acm:us-east-1:999999999999:certificate/reflection-test-cert"
}

swOxr = lambda spec: {str:any}, status: {str:any} -> {str:any} {
    {"spec": spec, "status": status}
}

test_composes_bucket_resources_on_cold_start = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr({**SW_BASE_SPEC, "zone": {"name": "static.trololo.demotw.com", "id": "Z00921083AT1Z6WZY8LYW"}}, {}), {})
    byName = swByName(items)
    assert sorted([k for k in byName]) == sorted(["bucket", "bucket-public-access-block", "origin-access-control", "certificate"])
    assert byName["bucket"].metadata.annotations["crossplane.io/external-name"] == "laz-static-website-customdomain-demo"
    assert byName["certificate"].kind == "DnsValidatedCertificate"
}

test_omits_distribution_when_no_custom_domain_even_with_bucket_domain_known = lambda {
    # The known bug (see composition-staticwebsite-yaml-patching.yaml's
    # header comment): Distribution's viewerCertificate.acmCertificateArn
    # gate is unconditional, so a StaticWebsite with no custom zone can never
    # actually get a Distribution. This test exists to prove this port
    # faithfully reproduces that, not to celebrate it.
    items = staticwebsite.composeStaticWebsite(swOxr(SW_BASE_SPEC, {"bucketDomainName": "laz-static-website-customdomain-demo.s3.ap-southeast-1.amazonaws.com"}), {})
    byName = swByName(items)
    assert not ("distribution" in byName)
}

test_composes_distribution_and_bucket_policy_once_fully_observed = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    byName = swByName(items)
    assert "distribution" in byName
    assert "bucket-policy" in byName
    assert "domain-alias-record" in byName
    assert byName["distribution"].spec.forProvider.viewerCertificate.acmCertificateArn == "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
    policy = byName["bucket-policy"].spec.forProvider.policy
    assert "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE" in policy
}

test_bucket_policy_grants_cloudfront_only = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    policy = swByName(items)["bucket-policy"].spec.forProvider
    assert policy.bucket == "laz-static-website-customdomain-demo"

    document = json.decode(policy.policy)
    assert document.Version == "2012-10-17"
    assert len(document.Statement) == 1

    statement = document.Statement[0]
    assert statement.Effect == "Allow"
    assert statement.Principal == {"Service": "cloudfront.amazonaws.com"}
    assert statement.Resource == "arn:aws:s3:::laz-static-website-customdomain-demo/*"
    assert statement.Condition == {"StringEquals": {"AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE"}}
}

test_bucket_policy_grants_get_object_only = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    policy = swByName(items)["bucket-policy"].spec.forProvider
    document = json.decode(policy.policy)
    actions = [s.Action for s in document.Statement]
    assert actions == ["s3:GetObject"]
}

test_requests_certificate_for_the_custom_domain = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    byName = swByName(items)
    assert byName["certificate"].spec.domainName == "static.trololo.demotw.com"

    viewerCertificate = byName["distribution"].spec.forProvider.viewerCertificate
    assert viewerCertificate.acmCertificateArn == "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
    assert not ("cloudfrontDefaultCertificate" in viewerCertificate)
}

test_distribution_enforces_tls_1_2_minimum = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    viewerCertificate = swByName(items)["distribution"].spec.forProvider.viewerCertificate
    assert viewerCertificate.minimumProtocolVersion == "TLSv1.2_2021"
}

test_blocks_all_public_access = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    block = swByName(items)["bucket-public-access-block"].spec.forProvider
    assert block.blockPublicAcls == True
    assert block.blockPublicPolicy == True
    assert block.ignorePublicAcls == True
    assert block.restrictPublicBuckets == True
}

test_public_access_block_targets_the_right_bucket = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    byName = swByName(items)
    bucket = byName["bucket"]
    block = byName["bucket-public-access-block"].spec.forProvider
    assert block.bucket == bucket.metadata.annotations["crossplane.io/external-name"]
    assert block.region == bucket.spec.forProvider.region
}

test_origin_access_control_is_configured_correctly = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    oac = swByName(items)["origin-access-control"].spec.forProvider
    assert oac.originAccessControlOriginType == "s3"
    assert oac.signingBehavior == "always"
    assert oac.signingProtocol == "sigv4"
}

test_distribution_selects_its_own_origin_access_control = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS), {})
    origin = swByName(items)["distribution"].spec.forProvider.origin[0]
    assert origin.originAccessControlIdSelector == {"matchControllerRef": True}
}

test_bucket_reflects_name_and_region = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(INPUT_REFLECTION_SPEC, INPUT_REFLECTION_STATUS), {})
    bucket = swByName(items)["bucket"]
    assert bucket.metadata.annotations["crossplane.io/external-name"] == "reflection-test-bucket"
    assert bucket.spec.forProvider.region == "eu-west-2"
}

test_distribution_reflects_index_document = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(INPUT_REFLECTION_SPEC, INPUT_REFLECTION_STATUS), {})
    distribution = swByName(items)["distribution"].spec.forProvider
    assert distribution.defaultRootObject == "home.html"
}

test_distribution_reflects_custom_domain_alias = lambda {
    items = staticwebsite.composeStaticWebsite(swOxr(INPUT_REFLECTION_SPEC, INPUT_REFLECTION_STATUS), {})
    distribution = swByName(items)["distribution"].spec.forProvider
    assert distribution.aliases == ["reflection.example.com"]
}
